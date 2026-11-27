"""用真實的展示版資料核對品質規則和 silver.admission。沒下載資料時跳過。

完成標準：error 0 筆、warn 20 筆（docs/mimic-demo-findings.md：語言填 ? 的有 20 筆）。
"""

import pytest
from pyspark.sql import functions as F

from common.spark import read_table
from ingest.bronze import load_bronze
from quality.rules import apply_rules, patient_rules
from transform.silver import ADMISSION_TIMESTAMPS, build_silver_admission, cast_patients


@pytest.fixture(scope="module")
def counts(spark, real_cfg):
    load_bronze(spark, real_cfg, "batch_001")
    return build_silver_admission(spark, real_cfg, "batch_001")


def test_admissions_error_0_warn_20(counts):
    assert counts == {
        "bronze": 275,
        "duplicates_removed": 0,
        "rejected_records": 0,
        "silver": 275,
        "error_rejects": 0,
        "warn_rejects": 20,
    }


def test_patients_have_no_errors(spark, real_cfg, counts):
    bronze = read_table(spark, real_cfg, "bronze.patients")
    passed, rejects = apply_rules(bronze, patient_rules(), source_table="bronze.patients", key="subject_id")
    assert rejects.count() == 0
    assert passed.count() == 100


def test_no_value_is_lost_by_casting(spark, real_cfg, counts):
    """已知限制的核對：轉不過去的值會變成 null 而且不記 reject，所以確認真實資料一筆都沒有。"""
    bronze = read_table(spark, real_cfg, "bronze.admissions").alias("b")
    silver = read_table(spark, real_cfg, "silver.admission").alias("s")
    joined = bronze.join(silver, "hadm_id")
    for column in [*ADMISSION_TIMESTAMPS, "hospital_expire_flag"]:
        lost = joined.where(F.col(f"b.{column}").isNotNull() & F.col(f"s.{column}").isNull())
        assert lost.count() == 0, column

    patients = cast_patients(read_table(spark, real_cfg, "bronze.patients"))
    raw = read_table(spark, real_cfg, "bronze.patients")
    for column in ["anchor_age", "anchor_year", "dod"]:
        assert patients.where(F.col(column).isNull()).count() == raw.where(F.col(column).isNull()).count(), column
