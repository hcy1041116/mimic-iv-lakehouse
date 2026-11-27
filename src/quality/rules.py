"""品質規則和 reject 紀錄。

- error：擋下，不進 Silver；warn：只記錄，照樣往下走
- reject 的 grain 是「規則 × 資料」：一筆資料違反兩條規則，就有兩筆 reject
- 整列完全一樣的重複資料先 distinct 掉，不算 reject；同一個鍵但內容不同的才算 error
"""

from dataclasses import dataclass

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

from ingest.bronze import CORRUPT_COLUMN

ERROR = "error"
WARN = "warn"


@dataclass(frozen=True)
class Rule:
    name: str
    severity: str
    violated: Column  # 這一列違反規則時為 true


def missing(key: str) -> Rule:
    return Rule(f"{key}_missing", ERROR, F.col(key).isNull())


def duplicate(key: str) -> Rule:
    count_per_key = F.count(F.lit(1)).over(Window.partitionBy(key))
    return Rule(f"{key}_duplicate", ERROR, F.col(key).isNotNull() & (count_per_key > 1))


def line_malformed() -> Rule:
    return Rule("line_malformed", ERROR, F.col(CORRUPT_COLUMN).isNotNull())


# 規則寫成函式：Column 要在 Spark session 建好之後才能產生，不能在 import 時就建
def patient_rules() -> list[Rule]:
    return [
        line_malformed(),
        missing("subject_id"),
        duplicate("subject_id"),
        Rule("gender_invalid", ERROR, ~F.coalesce(F.col("gender").isin("M", "F"), F.lit(False))),
    ]


def admission_rules() -> list[Rule]:
    return [
        line_malformed(),
        missing("hadm_id"),
        duplicate("hadm_id"),
        Rule("admittime_invalid", ERROR, F.col("admittime").try_cast("timestamp_ntz").isNull()),
        Rule("language_unknown", WARN, F.coalesce(F.col("language") == "?", F.lit(False))),
    ]


def source_columns(bronze: DataFrame) -> list[str]:
    """Bronze 裡來自來源檔的欄位：中繼欄位都以底線開頭。"""
    return [c for c in bronze.columns if not c.startswith("_")]


def apply_rules(
    bronze: DataFrame, rules: list[Rule], *, source_table: str, key: str
) -> tuple[DataFrame, DataFrame]:
    """先 distinct，再逐條檢查。回傳（通過的資料, reject 紀錄）。

    通過的資料 = 沒有違反任何 error 規則的列（違反 warn 的照樣留著）。
    reject 紀錄的 `record` 是這一列來源欄位的 JSON，留作證據。
    """
    columns = source_columns(bronze)
    deduped = bronze.dropDuplicates(columns + [CORRUPT_COLUMN])

    flags = [f"_violates_{rule.name}" for rule in rules]
    flagged = deduped
    for flag, rule in zip(flags, rules):
        flagged = flagged.withColumn(flag, rule.violated)

    rejects = None
    for flag, rule in zip(flags, rules):
        found = flagged.where(F.col(flag)).select(
            F.col("_batch_id").alias("batch_id"),
            F.lit(source_table).alias("source_table"),
            F.lit(rule.name).alias("rule"),
            F.lit(rule.severity).alias("severity"),
            F.col(key).alias("record_key"),
            F.to_json(F.struct(*columns, CORRUPT_COLUMN)).alias("record"),
        )
        rejects = found if rejects is None else rejects.unionByName(found)

    error_flags = [flag for flag, rule in zip(flags, rules) if rule.severity == ERROR]
    any_error = F.lit(False)
    for flag in error_flags:
        any_error = any_error | F.col(flag)
    passed = flagged.where(~any_error).drop(*flags)
    return passed, rejects
