"""整條管線：核對沒過時要報錯；真實資料連跑兩次，結果要一模一樣。"""

import pytest

from common.spark import read_table
from pipeline import assert_all_ok, run

# 連跑兩次要逐列相同的表。ops.row_count 是執行紀錄，本來就會一直累加，不比
TABLES = [
    "bronze.patients",
    "bronze.admissions",
    "quality.reject",
    "silver.admission",
    "silver.patient",
    "gold.patient_summary",
]


def test_mismatch_raises_and_names_the_check():
    checks = [
        {"check_name": "a", "expected": 1, "actual": 1},
        {"check_name": "b", "expected": 275, "actual": 274},
    ]
    with pytest.raises(RuntimeError, match="b：應該 275，實際 274"):
        assert_all_ok(checks)


def test_all_ok_does_not_raise():
    assert_all_ok([{"check_name": "a", "expected": 1, "actual": 1}])


def snapshot(spark, cfg):
    """每張表的全部列（拿掉每次執行都不同的載入時間），排序後可以直接比。"""
    result = {}
    for table in TABLES:
        df = read_table(spark, cfg, table)
        df = df.drop("_ingested_at") if "_ingested_at" in df.columns else df
        result[table] = sorted(tuple(row) for row in df.collect())
    return result


def test_rerun_same_batch_gives_identical_tables(spark, real_cfg):
    first_checks = run(spark, real_cfg, "batch_001")
    first = snapshot(spark, real_cfg)
    second_checks = run(spark, real_cfg, "batch_001")
    second = snapshot(spark, real_cfg)

    assert first_checks == second_checks
    for table in TABLES:
        assert first[table] == second[table], table
    assert {table: len(rows) for table, rows in first.items()} == {
        "bronze.patients": 100,
        "bronze.admissions": 275,
        "quality.reject": 20,
        "silver.admission": 275,
        "silver.patient": 100,
        "gold.patient_summary": 100,
    }

    log = read_table(spark, real_cfg, "ops.row_count")
    assert log.count() == 12  # 兩次執行 × 6 個核對點
    assert log.where("NOT ok").count() == 0
