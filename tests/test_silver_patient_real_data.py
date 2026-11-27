"""用真實的展示版資料核對 silver.patient。沒下載資料時跳過。

完成標準：100 列；人口資料等於最後一次住院的值；婚姻和官方 FHIR Patient 一致。
期待值用 Python 標準函式庫從原始 CSV、FHIR 檔另外算，不用 Spark 自己核對自己。
官方 FHIR 的種族換成了美國 OMB 類別（例如 HISPANIC/LATINO - CUBAN → White），
要經過對照才能比，那是 FHIR 那一層的事，所以種族只和原始 CSV 比。
"""

import csv
import gzip
import json
from pathlib import Path

import pytest

from common.spark import read_table
from ingest.bronze import SOURCE_FILES, load_bronze
from transform.silver import build_silver_admission, build_silver_patient

FHIR_PATIENTS = "mimic-iv-fhir-demo-2.1.0/fhir/MimicPatient.ndjson.gz"
# MIMIC 的婚姻 → FHIR Patient.maritalStatus 的代碼（實測 100 位病人都是這樣對）
MARITAL_CODE = {"MARRIED": "M", "SINGLE": "S", "DIVORCED": "D", "WIDOWED": "W", None: "UNK"}


@pytest.fixture(scope="module")
def silver_patient(spark, real_cfg):
    load_bronze(spark, real_cfg, "batch_001")
    build_silver_admission(spark, real_cfg, "batch_001")
    counts = build_silver_patient(spark, real_cfg, "batch_001")
    return counts, {row["subject_id"]: row for row in read_table(spark, real_cfg, "silver.patient").collect()}


@pytest.fixture(scope="module")
def latest_from_csv(real_cfg):
    """每位病人 admittime 最晚的那一次住院，直接從原始 CSV 算。"""
    path = Path(real_cfg.source_root) / SOURCE_FILES["bronze.admissions"]
    latest = {}
    with gzip.open(path, "rt", newline="") as f:
        for row in csv.DictReader(f):
            current = latest.get(row["subject_id"])
            if current is None or row["admittime"] > current["admittime"]:
                latest[row["subject_id"]] = row
    return latest


def test_one_row_per_patient(silver_patient):
    counts, rows = silver_patient
    assert counts["bronze"] == counts["silver"] == len(rows) == 100
    assert counts["rejected_records"] == 0


def test_demographics_equal_latest_admission_in_csv(silver_patient, latest_from_csv):
    _, rows = silver_patient
    for subject_id, row in rows.items():
        expected = latest_from_csv[subject_id]
        for column in ["marital_status", "race", "language"]:
            assert row[column] == (expected[column] or None), (subject_id, column)


def test_marital_status_matches_official_fhir(silver_patient, real_cfg):
    path = Path(real_cfg.source_root) / FHIR_PATIENTS
    if not path.exists():
        pytest.skip("沒有下載 MIMIC-IV on FHIR 展示版")
    with gzip.open(path, "rt") as f:
        fhir = {p["identifier"][0]["value"]: p for p in map(json.loads, f)}

    _, rows = silver_patient
    for subject_id, row in rows.items():
        code = fhir[subject_id]["maritalStatus"]["coding"][0]["code"]
        assert MARITAL_CODE[row["marital_status"]] == code, subject_id
