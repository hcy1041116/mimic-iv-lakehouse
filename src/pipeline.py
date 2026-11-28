"""整條 MVP 管線：來源 CSV → Bronze → 品質檢查 → Silver → Gold，最後核對每一層的筆數。

本機：      uv run python src/pipeline.py --env local --batch batch_001
Databricks：notebooks/run_pipeline 呼叫同一個 run()
"""

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from common.config import Config, load_config
from common.spark import ensure_schemas, get_spark, write_table
from ingest.bronze import SOURCE_FILES, load_bronze
from transform.gold import build_gold_patient_summary
from transform.silver import build_silver_admission, build_silver_patient


def run(spark: SparkSession, cfg: Config, batch_id: str) -> list[dict]:
    """依序跑完每一層，把核對結果寫進 ops.row_count；有任何一項對不上就丟出錯誤。"""
    ensure_schemas(spark, cfg)

    # 1. Bronze：來源 CSV 原樣落地（src/ingest/bronze.py）
    bronze = load_bronze(spark, cfg, batch_id)
    # 2. 品質檢查 → silver.admission（src/quality/rules.py、src/transform/silver.py）
    admission = build_silver_admission(spark, cfg, batch_id)
    # 3. 品質檢查 → silver.patient：挑最後一次住院、組病人表（src/transform/silver_patient.py）
    patient = build_silver_patient(spark, cfg, batch_id)
    # 4. Gold：每位病人住了幾次院（sql/gold_patient_summary.sql）
    gold = build_gold_patient_summary(spark, cfg)

    # 5. 核對每一層的筆數，寫進 ops.row_count
    checks = reconciliation_checks(spark, cfg, bronze, admission, patient, gold)
    record_checks(spark, cfg, batch_id, checks)
    assert_all_ok(checks)
    return checks


def source_rows(spark: SparkSession, cfg: Config, table: str) -> int:
    """來源檔的行數減掉表頭。用 text 格式數，不經過 CSV 解析。"""
    return spark.read.text(f"{cfg.source_root}/{SOURCE_FILES[table]}").count() - 1


def reconciliation_checks(spark, cfg, bronze, admission, patient, gold) -> list[dict]:
    """每一項核對：expected 是從上一層推出來應該有的筆數，actual 是這一層實際的筆數。"""

    def after_quality(counts: dict) -> int:
        return counts["bronze"] - counts["rejected_records"] - counts["duplicates_removed"]

    return [
        {
            "check_name": "bronze.patients = 來源行數 − 表頭",
            "expected": source_rows(spark, cfg, "bronze.patients"),
            "actual": bronze["bronze.patients"],
        },
        {
            "check_name": "bronze.admissions = 來源行數 − 表頭",
            "expected": source_rows(spark, cfg, "bronze.admissions"),
            "actual": bronze["bronze.admissions"],
        },
        {
            "check_name": "silver.admission = bronze − 擋下 − 去重",
            "expected": after_quality(admission),
            "actual": admission["silver"],
        },
        {
            "check_name": "silver.patient = bronze − 擋下 − 去重",
            "expected": after_quality(patient),
            "actual": patient["silver"],
        },
        {
            "check_name": "gold.patient_summary 列數 = silver.patient 列數",
            "expected": gold["silver_patients"],
            "actual": gold["gold_rows"],
        },
        {
            "check_name": "gold 住院次數加總 = silver.admission 筆數",
            "expected": gold["silver_admissions"],
            "actual": gold["admission_count_total"],
        },
    ]


def record_checks(spark: SparkSession, cfg: Config, batch_id: str, checks: list[dict]) -> None:
    """一次執行 × 一個核對點一列，累加寫入（保留每次執行的紀錄）。"""
    rows = [(batch_id, c["check_name"], c["expected"], c["actual"]) for c in checks]
    df = (
        spark.createDataFrame(rows, "batch_id string, check_name string, expected bigint, actual bigint")
        .withColumn("ok", F.col("expected") == F.col("actual"))
        .withColumn("run_at", F.current_timestamp())
    )
    write_table(df, cfg, "ops.row_count", mode="append")


def assert_all_ok(checks: list[dict]) -> None:
    failed = [c for c in checks if c["expected"] != c["actual"]]
    if failed:
        lines = [f"{c['check_name']}：應該 {c['expected']}，實際 {c['actual']}" for c in failed]
        raise RuntimeError("筆數核對沒過：\n" + "\n".join(lines))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="跑完整條 MVP 管線")
    parser.add_argument("--env", default="local", choices=["local", "databricks"])
    parser.add_argument("--batch", default="batch_001")
    args = parser.parse_args(argv)

    cfg = load_config(args.env)
    spark = get_spark(cfg)
    if cfg.platform == "local":
        spark.sparkContext.setLogLevel("ERROR")
    for c in run(spark, cfg, args.batch):
        print(f"OK  {c['check_name']}：{c['actual']}")


if __name__ == "__main__":
    main()
