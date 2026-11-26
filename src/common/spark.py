"""取得 Spark session，以及用邏輯表名讀寫 Delta 表。

local 由這裡自己建帶 Delta 的 session；databricks 直接用平台提供的 session。
只用 DataFrame API，不用 RDD 和 SparkContext（Databricks serverless 不支援）。
"""

from pyspark.sql import DataFrame, SparkSession

from common.config import Config, table_location


def get_spark(cfg: Config) -> SparkSession:
    """回傳這個環境的 Spark session，session 時區設成 config 指定的值。"""
    if cfg.platform == "local":
        from delta import configure_spark_with_delta_pip

        builder = (
            SparkSession.builder.master("local[*]")
            .appName("mimic-iv-lakehouse")
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config(
                "spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog",
            )
        )
        spark = configure_spark_with_delta_pip(builder).getOrCreate()
    else:
        spark = SparkSession.builder.getOrCreate()

    spark.conf.set("spark.sql.session.timeZone", cfg.session_timezone)
    return spark


def read_table(spark: SparkSession, cfg: Config, logical_name: str) -> DataFrame:
    location = table_location(cfg, logical_name)
    if cfg.platform == "local":
        return spark.read.format("delta").load(location)
    return spark.read.table(location)


def write_table(
    df: DataFrame,
    cfg: Config,
    logical_name: str,
    mode: str = "overwrite",
    replace_where: str | None = None,
) -> None:
    """寫成 Delta 表。給了 `replace_where` 時，只取代符合條件的那些列，例如同一個批次。"""
    location = table_location(cfg, logical_name)
    writer = df.write.format("delta").mode(mode)
    if replace_where is not None:
        writer = writer.option("replaceWhere", replace_where)
    if cfg.platform == "local":
        writer.save(location)
    else:
        writer.saveAsTable(location)
