"""Bronze 用手工小樣本測：髒資料照樣落地、值不被改、重跑同一批不疊加。

tests/fixtures/patients_dirty.csv 的 5 行資料：
1. 正常，dod 空白
2. 代碼格式錯誤：gender X、anchor_age abc、dod 2161-02-30
3. subject_id 空白
4. 格子太少（只有 3 格）
5. 和第 1 行完全一樣（重複 id）
"""

from pathlib import Path

import pytest
from pyspark.sql.types import StringType

from common.spark import read_table
from ingest.bronze import CORRUPT_COLUMN, ingest_file, read_source

FIXTURE = str(Path(__file__).parent / "fixtures" / "patients_dirty.csv")
SOURCE_COLUMNS = ["subject_id", "gender", "anchor_age", "anchor_year", "anchor_year_group", "dod"]


@pytest.fixture(scope="module")
def rows(spark):
    return read_source(spark, FIXTURE, "batch_001").collect()


def test_every_line_lands(rows):
    assert len(rows) == 5


def test_source_columns_are_strings_named_after_header(spark):
    df = read_source(spark, FIXTURE, "batch_001")
    assert df.columns[: len(SOURCE_COLUMNS)] == SOURCE_COLUMNS
    assert all(df.schema[c].dataType == StringType() for c in SOURCE_COLUMNS)


def test_bad_codes_are_kept_as_written(rows):
    row = next(r for r in rows if r["subject_id"] == "10000002")
    assert (row["gender"], row["anchor_age"], row["dod"]) == ("X", "abc", "2161-02-30")


def test_blank_values_become_null(rows):
    assert sum(r["subject_id"] is None for r in rows) == 1
    assert next(r for r in rows if r["subject_id"] == "10000001")["dod"] is None


def test_duplicate_ids_are_both_kept(rows):
    assert sum(r["subject_id"] == "10000001" for r in rows) == 2


def test_short_line_is_kept_whole_in_corrupt_record(rows):
    corrupt = [r[CORRUPT_COLUMN] for r in rows if r[CORRUPT_COLUMN] is not None]
    assert corrupt == ["10000004,F,33"]


def test_metadata_columns(rows):
    assert {r["_batch_id"] for r in rows} == {"batch_001"}
    assert all(r["_source_file"].endswith("fixtures/patients_dirty.csv") for r in rows)
    assert all(r["_ingested_at"] is not None for r in rows)


def test_rerun_same_batch_replaces_instead_of_appending(spark, cfg):
    assert ingest_file(spark, cfg, "bronze.patients_fixture", FIXTURE, "batch_001") == 5
    assert ingest_file(spark, cfg, "bronze.patients_fixture", FIXTURE, "batch_001") == 5

    assert ingest_file(spark, cfg, "bronze.patients_fixture", FIXTURE, "batch_002") == 5
    assert read_table(spark, cfg, "bronze.patients_fixture").count() == 10
