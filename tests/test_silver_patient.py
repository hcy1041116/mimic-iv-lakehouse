"""select_latest_admission 和 build_patient 的測試（函式由 HCY 實作）。

測試資料直接寫在這裡，欄位只放用得到的幾欄。三位病人：
- 10000001：住院 3 次，婚姻 SINGLE → MARRIED → MARRIED，種族 UNKNOWN → WHITE。
  最後一次（2140-10-22）的 hadm_id 反而最小，而且不是排在最後面的那一列
- 10000002：住院 2 次，最後一次的婚姻是空白
- 10000003：只住院 1 次
"""

from datetime import date, datetime

import pytest

from transform.silver_patient import (
    PATIENT_COLUMNS,
    build_patient,
    select_latest_admission,
)

ADMISSION_SCHEMA = (
    "subject_id string, hadm_id string, admittime timestamp_ntz, "
    "marital_status string, race string, language string, insurance string, _batch_id string"
)
ADMISSIONS = [
    ("10000001", "20000107", datetime(2140, 10, 3, 9, 6), "MARRIED", "WHITE", "ENGLISH", "Medicare", "batch_001"),
    ("10000001", "20000101", datetime(2140, 10, 22, 22, 4), "MARRIED", "WHITE", "ENGLISH", "Medicaid", "batch_001"),
    ("10000002", "20000209", datetime(2150, 1, 1, 10, 0), "MARRIED", "ASIAN", "ENGLISH", "Other", "batch_001"),
    ("10000002", "20000201", datetime(2151, 2, 1, 10, 0), None, "ASIAN", "ENGLISH", "Other", "batch_001"),
    ("10000003", "20000301", datetime(2160, 5, 5, 5, 5), "WIDOWED", "WHITE", "?", "Medicare", "batch_001"),
    ("10000001", "20000105", datetime(2137, 6, 19, 17, 35), "SINGLE", "UNKNOWN", "ENGLISH", "Medicare", "batch_001"),
]

PATIENT_SCHEMA = (
    "subject_id string, gender string, anchor_age int, anchor_year int, "
    "anchor_year_group string, dod date, _batch_id string"
)
PATIENTS = [
    ("10000001", "F", 52, 2140, "2011 - 2013", None, "batch_001"),
    ("10000002", "M", 60, 2150, "2014 - 2016", date(2152, 1, 1), "batch_001"),
    ("10000003", "F", 70, 2160, "2017 - 2019", None, "batch_001"),
]

# build_patient 的測試不依賴 select_latest_admission：直接給「每人最後一次住院」
LATEST = [ADMISSIONS[1], ADMISSIONS[3], ADMISSIONS[4]]


@pytest.fixture(scope="module")
def admissions(spark):
    return spark.createDataFrame(ADMISSIONS, ADMISSION_SCHEMA)


@pytest.fixture(scope="module")
def patients(spark):
    return spark.createDataFrame(PATIENTS, PATIENT_SCHEMA)


@pytest.fixture(scope="module")
def latest(spark):
    return spark.createDataFrame(LATEST, ADMISSION_SCHEMA)


def by_subject(df):
    return {row["subject_id"]: row for row in df.collect()}


# ---- select_latest_admission ----


def test_one_row_per_patient(admissions):
    rows = select_latest_admission(admissions).collect()
    assert sorted(row["subject_id"] for row in rows) == ["10000001", "10000002", "10000003"]


def test_latest_is_by_admittime_not_row_order_or_hadm_id(admissions):
    row = by_subject(select_latest_admission(admissions))["10000001"]
    assert row["hadm_id"] == "20000101"
    assert row["admittime"] == datetime(2140, 10, 22, 22, 4)


def test_latest_row_is_taken_whole_even_when_marital_is_blank(admissions):
    row = by_subject(select_latest_admission(admissions))["10000002"]
    assert row["hadm_id"] == "20000201"
    assert row["marital_status"] is None


def test_single_admission_is_its_own_latest(admissions):
    assert by_subject(select_latest_admission(admissions))["10000003"]["hadm_id"] == "20000301"


def test_columns_are_unchanged(admissions):
    assert select_latest_admission(admissions).columns == admissions.columns


# ---- build_patient ----


def test_patient_columns_in_order(patients, latest):
    assert build_patient(patients, latest).columns == PATIENT_COLUMNS


def test_one_row_per_patient_in_silver_patient(patients, latest):
    assert build_patient(patients, latest).count() == 3


def test_demographics_come_from_latest_admission(patients, latest):
    rows = by_subject(build_patient(patients, latest))
    assert (rows["10000001"]["marital_status"], rows["10000001"]["race"]) == ("MARRIED", "WHITE")
    assert rows["10000002"]["marital_status"] is None
    assert rows["10000003"]["language"] == "?"


def test_patient_fields_come_from_patients(patients, latest):
    row = by_subject(build_patient(patients, latest))["10000002"]
    assert (row["gender"], row["anchor_age"], row["dod"]) == ("M", 60, date(2152, 1, 1))
    assert row["_batch_id"] == "batch_001"
