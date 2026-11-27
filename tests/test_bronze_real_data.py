"""用真實的展示版資料核對 Bronze 筆數。資料不進 Git，沒下載時跳過。

來源行數用 Python 的 gzip 另外數，不用 Spark 自己核對自己。
"""

import gzip
from pathlib import Path

from pyspark.sql import functions as F

from common.spark import read_table
from ingest.bronze import CORRUPT_COLUMN, SOURCE_FILES, load_bronze


def data_lines(path: Path) -> int:
    """檔案的行數減掉表頭。"""
    with gzip.open(path, "rt", newline="") as f:
        return sum(1 for _ in f) - 1


def test_bronze_count_equals_source_lines_and_rerun_is_stable(spark, real_cfg):
    expected = {table: data_lines(Path(real_cfg.source_root) / rel) for table, rel in SOURCE_FILES.items()}
    assert expected == {"bronze.patients": 100, "bronze.admissions": 275}

    assert load_bronze(spark, real_cfg, "batch_001") == expected
    assert load_bronze(spark, real_cfg, "batch_001") == expected


def test_real_data_has_no_corrupt_lines(spark, real_cfg):
    load_bronze(spark, real_cfg, "batch_001")
    for table in SOURCE_FILES:
        assert read_table(spark, real_cfg, table).where(F.col(CORRUPT_COLUMN).isNotNull()).count() == 0
