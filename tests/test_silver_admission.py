"""silver.admission 用手工小樣本測：型別、通過的筆數、reject 表、重跑一致。

用 tests/fixtures/admissions_dirty.csv（9 行，每行的意思見 test_quality.py）。
"""

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from pyspark.sql.types import IntegerType, StringType, TimestampNTZType

from common.spark import read_table
from ingest.bronze import ingest_file
from transform.silver import build_silver_admission

FIXTURE = str(Path(__file__).parent / "fixtures" / "admissions_dirty.csv")


@pytest.fixture(scope="module")
def own_cfg(cfg, tmp_path_factory):
    """這個檔案自己的 lakehouse，不和其他測試共用 bronze.admissions。"""
    return replace(cfg, lakehouse_root=str(tmp_path_factory.mktemp("silver_admission")))


@pytest.fixture(scope="module")
def counts(spark, own_cfg):
    ingest_file(spark, own_cfg, "bronze.admissions", FIXTURE, "batch_001")
    return build_silver_admission(spark, own_cfg, "batch_001")


def test_counts_reconcile(counts):
    assert counts == {
        "bronze": 9,
        "duplicates_removed": 1,
        "rejected_records": 6,
        "silver": 2,
        "error_rejects": 6,
        "warn_rejects": 1,
    }
    assert counts["bronze"] == counts["silver"] + counts["rejected_records"] + counts["duplicates_removed"]


def test_column_types(spark, own_cfg, counts):
    schema = read_table(spark, own_cfg, "silver.admission").schema
    assert schema["admittime"].dataType == TimestampNTZType()
    assert schema["edregtime"].dataType == TimestampNTZType()
    assert schema["hospital_expire_flag"].dataType == IntegerType()
    assert schema["hadm_id"].dataType == StringType()
    assert "_corrupt_record" not in schema.fieldNames()
    assert "_batch_id" in schema.fieldNames()


def test_values_are_kept_exactly(spark, own_cfg, counts):
    row = read_table(spark, own_cfg, "silver.admission").where("hadm_id = '20000002'").first()
    assert row["admittime"] == datetime(2152, 3, 1, 8, 0)
    assert row["edregtime"] == datetime(2152, 3, 1, 6, 10)
    assert row["language"] == "?"
    assert row["hospital_expire_flag"] == 0


def test_rerun_same_batch_gives_same_result(spark, own_cfg, counts):
    assert build_silver_admission(spark, own_cfg, "batch_001") == counts
    assert read_table(spark, own_cfg, "quality.reject").count() == counts["error_rejects"] + counts["warn_rejects"]
