"""sql/gold_patient_summary.sql 的測試（SQL 由 HCY 實作）。

測試資料：4 位病人
- 10000001：住院 3 次
- 10000002：住院 2 次
- 10000003：住院 1 次
- 10000004：沒有任何住院 → admission_count 要是 0
"""

import pytest

from transform.gold import SUMMARY_COLUMNS, patient_summary

PATIENTS = [
    ("10000001", "F", 52),
    ("10000002", "M", 60),
    ("10000003", "F", 70),
    ("10000004", "M", 45),
]
ADMISSIONS = [
    ("10000001", "20000105"),
    ("10000002", "20000209"),
    ("10000001", "20000107"),
    ("10000003", "20000301"),
    ("10000001", "20000101"),
    ("10000002", "20000201"),
]


@pytest.fixture(scope="module")
def summary(spark):
    patients = spark.createDataFrame(PATIENTS, "subject_id string, gender string, anchor_age int")
    admissions = spark.createDataFrame(ADMISSIONS, "subject_id string, hadm_id string")
    return patient_summary(spark, patients, admissions)


def counts(summary):
    return {row["subject_id"]: row["admission_count"] for row in summary.collect()}


def test_columns_in_order(summary):
    assert summary.columns == SUMMARY_COLUMNS


def test_one_row_per_patient(summary):
    assert sorted(counts(summary)) == ["10000001", "10000002", "10000003", "10000004"]


def test_admission_count_per_patient(summary):
    assert counts(summary) == {"10000001": 3, "10000002": 2, "10000003": 1, "10000004": 0}


def test_total_equals_number_of_admissions(summary):
    assert sum(counts(summary).values()) == len(ADMISSIONS)


def test_patient_fields_are_kept(summary):
    row = next(r for r in summary.collect() if r["subject_id"] == "10000002")
    assert (row["gender"], row["anchor_age"]) == ("M", 60)
