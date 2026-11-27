"""品質規則用手工小樣本測：缺值、重複 id、代碼格式錯誤、時間不合法、格子數不對都被擋下。

tests/fixtures/admissions_dirty.csv 的 9 行資料（hadm_id）：
1. 20000001 正常
2. 20000002 語言是 ?：warn，照樣通過
3. （空白）hadm_id 缺值：error
4. 20000004 和第 5 行同一個 hadm_id、婚姻不同：兩筆都 error
5. 20000004
6. 20000001 和第 1 行整列完全一樣：distinct 掉，不算 reject
7. 20000006 admittime 是 2150-13-40：error
8. 20000007 admittime 空白：error
9. 20000008 格子太少：error
"""

from pathlib import Path

import pytest

from ingest.bronze import read_source
from quality.rules import admission_rules, apply_rules, patient_rules

FIXTURES = Path(__file__).parent / "fixtures"


def summarize(rejects):
    rows = [(r["record_key"], r["rule"], r["severity"]) for r in rejects.collect()]
    return sorted(rows, key=lambda row: (row[0] or "", row[1]))


@pytest.fixture(scope="module")
def admissions(spark):
    bronze = read_source(spark, str(FIXTURES / "admissions_dirty.csv"), "batch_001")
    return apply_rules(bronze, admission_rules(), source_table="bronze.admissions", key="hadm_id")


def test_admission_rejects_are_one_per_rule_and_record(admissions):
    _, rejects = admissions
    assert summarize(rejects) == [
        (None, "hadm_id_missing", "error"),
        ("20000002", "language_unknown", "warn"),
        ("20000004", "hadm_id_duplicate", "error"),
        ("20000004", "hadm_id_duplicate", "error"),
        ("20000006", "admittime_invalid", "error"),
        ("20000007", "admittime_invalid", "error"),
        ("20000008", "line_malformed", "error"),
    ]


def test_only_records_without_errors_pass_and_warn_still_passes(admissions):
    passed, _ = admissions
    assert sorted(r["hadm_id"] for r in passed.collect()) == ["20000001", "20000002"]


def test_exact_duplicate_is_removed_not_rejected(admissions):
    passed, rejects = admissions
    assert [r["hadm_id"] for r in passed.collect()].count("20000001") == 1
    assert all(r["record_key"] != "20000001" for r in rejects.collect())


def test_reject_keeps_the_record_as_evidence(admissions):
    _, rejects = admissions
    bad_time = next(r for r in rejects.collect() if r["record_key"] == "20000006")
    assert '"admittime":"2150-13-40 10:00:00"' in bad_time["record"]
    malformed = next(r for r in rejects.collect() if r["record_key"] == "20000008")
    assert '"_corrupt_record":"10000007,20000008,2150-01-01 10:00:00"' in malformed["record"]
    assert {r["batch_id"] for r in rejects.collect()} == {"batch_001"}


def test_patient_rules(spark):
    # patients_dirty.csv：10000001 正常（另有一行完全一樣）、10000002 性別 X、subject_id 空白、10000004 格子太少
    bronze = read_source(spark, str(FIXTURES / "patients_dirty.csv"), "batch_001")
    passed, rejects = apply_rules(bronze, patient_rules(), source_table="bronze.patients", key="subject_id")

    assert [r["subject_id"] for r in passed.collect()] == ["10000001"]
    assert summarize(rejects) == [
        (None, "subject_id_missing", "error"),
        ("10000002", "gender_invalid", "error"),
        ("10000004", "line_malformed", "error"),
    ]
