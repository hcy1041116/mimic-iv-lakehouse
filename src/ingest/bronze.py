"""Bronze：來源 CSV 原樣落地成 Delta 表。

- 每欄都存成原始字串，不轉型別；型別到 Silver 才轉
- 格子數不對的行照樣落地，整行原文放在 `_corrupt_record`
- 加中繼欄位：`_source_file`、`_batch_id`、`_ingested_at`
- 同一批重跑時，只取代那一批的資料，不會疊加
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

from common.config import Config
from common.spark import read_table, write_table

# 邏輯表名 → 來源檔相對於 source_root 的路徑。兩個平台的資料夾結構一樣，只有 source_root 不同
SOURCE_FILES = {
    "bronze.patients": "mimic-iv-demo-2.2/hosp/patients.csv.gz",
    "bronze.admissions": "mimic-iv-demo-2.2/hosp/admissions.csv.gz",
}
CORRUPT_COLUMN = "_corrupt_record"


def read_source(spark: SparkSession, path: str, batch_id: str) -> DataFrame:
    """讀一個有表頭的 CSV：欄位名照表頭，全部是字串，再加上中繼欄位。"""
    columns = spark.read.option("header", True).csv(path).columns
    schema = StructType(
        [StructField(name, StringType()) for name in columns]
        + [StructField(CORRUPT_COLUMN, StringType())]
    )
    return (
        spark.read.schema(schema)
        .option("header", True)
        .option("mode", "PERMISSIVE")
        .option("columnNameOfCorruptRecord", CORRUPT_COLUMN)
        .csv(path)
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_batch_id", F.lit(batch_id))
        .withColumn("_ingested_at", F.current_timestamp())
    )


def ingest_file(spark: SparkSession, cfg: Config, table: str, path: str, batch_id: str) -> int:
    """把一個來源檔寫進一張 Bronze 表的這一批，回傳這一批的筆數。"""
    df = read_source(spark, path, batch_id)
    write_table(df, cfg, table, replace_where=f"_batch_id = '{batch_id}'")
    return read_table(spark, cfg, table).where(F.col("_batch_id") == batch_id).count()


def load_bronze(spark: SparkSession, cfg: Config, batch_id: str) -> dict[str, int]:
    """把 SOURCE_FILES 的每個檔寫進 Bronze，回傳每張表這一批的筆數。"""
    return {
        table: ingest_file(spark, cfg, table, f"{cfg.source_root}/{relative}", batch_id)
        for table, relative in SOURCE_FILES.items()
    }
