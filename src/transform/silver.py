"""Silver：Bronze 經過品質檢查後，轉成正確的型別。

- 時間轉成 TIMESTAMP_NTZ（ADR-0003），日期轉成 DATE，數字轉成 INT
- 業務鍵（`subject_id`、`hadm_id`）照來源的字串保存，不轉型別、不產生代理鍵
- 用 try_cast：轉不過去的值變成 null。只有 `admittime` 有品質規則把關，其他欄位轉不過去不會記 reject（已知限制；真實資料 0 筆）
- 只留 `_batch_id` 一個中繼欄位，Silver 整張重寫
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from common.config import Config
from common.spark import read_table, write_table
from ingest.bronze import CORRUPT_COLUMN
from quality.rules import (
    ERROR,
    WARN,
    admission_rules,
    apply_rules,
    patient_rules,
    source_columns,
)
from transform.silver_patient import build_patient, select_latest_admission

ADMISSION_TIMESTAMPS = ["admittime", "dischtime", "deathtime", "edregtime", "edouttime"]
DROPPED_METADATA = ["_corrupt_record", "_source_file", "_ingested_at"]


def cast_admissions(passed: DataFrame) -> DataFrame:
    out = passed
    for column in ADMISSION_TIMESTAMPS:
        out = out.withColumn(column, F.col(column).try_cast("timestamp_ntz"))
    out = out.withColumn("hospital_expire_flag", F.col("hospital_expire_flag").try_cast("int"))
    return out.drop(*DROPPED_METADATA)


def cast_patients(passed: DataFrame) -> DataFrame:
    return (
        passed.withColumn("anchor_age", F.col("anchor_age").try_cast("int"))
        .withColumn("anchor_year", F.col("anchor_year").try_cast("int"))
        .withColumn("dod", F.col("dod").try_cast("date"))
        .drop(*DROPPED_METADATA)
    )


def write_rejects(rejects: DataFrame, cfg: Config, source_table: str, batch_id: str) -> None:
    """同一批、同一張來源表的 reject 整批取代，重跑不會疊加。"""
    write_table(
        rejects,
        cfg,
        "quality.reject",
        replace_where=f"batch_id = '{batch_id}' AND source_table = '{source_table}'",
    )


def summarize(
    spark: SparkSession, cfg: Config, bronze: DataFrame, source_table: str, batch_id: str, silver_table: str
) -> dict[str, int]:
    """各階段的筆數。

    `rejected_records` 從 reject 表另外數（被 error 擋下的不同資料有幾筆），
    所以「bronze = silver + rejected_records + duplicates_removed」是真的核對，不是用減法湊出來的。
    """
    saved = read_table(spark, cfg, "quality.reject").where(
        (F.col("batch_id") == batch_id) & (F.col("source_table") == source_table)
    )
    errors = saved.where(F.col("severity") == ERROR)
    bronze_rows = bronze.count()
    return {
        "bronze": bronze_rows,
        "duplicates_removed": bronze_rows
        - bronze.dropDuplicates(source_columns(bronze) + [CORRUPT_COLUMN]).count(),
        "rejected_records": errors.select("record").distinct().count(),
        "silver": read_table(spark, cfg, silver_table).count(),
        "error_rejects": errors.count(),
        "warn_rejects": saved.where(F.col("severity") == WARN).count(),
    }


def build_silver_admission(spark: SparkSession, cfg: Config, batch_id: str) -> dict[str, int]:
    """bronze.admissions 的這一批 → 品質檢查 → silver.admission。回傳各階段的筆數。"""
    source_table = "bronze.admissions"
    bronze = read_table(spark, cfg, source_table).where(F.col("_batch_id") == batch_id)
    passed, rejects = apply_rules(bronze, admission_rules(), source_table=source_table, key="hadm_id")

    write_rejects(rejects, cfg, source_table, batch_id)
    write_table(cast_admissions(passed), cfg, "silver.admission")
    return summarize(spark, cfg, bronze, source_table, batch_id, "silver.admission")


def build_silver_patient(spark: SparkSession, cfg: Config, batch_id: str) -> dict[str, int]:
    """bronze.patients 的這一批 → 品質檢查 → 加上最後一次住院的人口資料 → silver.patient。

    要先跑 build_silver_admission：最後一次住院是從 silver.admission 挑的（先檢查品質，再挑最新）。
    """
    source_table = "bronze.patients"
    bronze = read_table(spark, cfg, source_table).where(F.col("_batch_id") == batch_id)
    passed, rejects = apply_rules(bronze, patient_rules(), source_table=source_table, key="subject_id")

    write_rejects(rejects, cfg, source_table, batch_id)
    latest = select_latest_admission(read_table(spark, cfg, "silver.admission"))
    write_table(build_patient(cast_patients(passed), latest), cfg, "silver.patient")
    return summarize(spark, cfg, bronze, source_table, batch_id, "silver.patient")
