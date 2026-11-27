"""Silver 病人表：一位病人一列，人口資料取自最後一次住院（GLOSSARY「目前狀態」）。

這個檔案的兩個函式由 HCY 實作（學習模式）。只跑這兩個函式的測試：

    uv run pytest tests/test_silver_patient.py
"""

from pyspark.sql import DataFrame

# silver.patient 的欄位，照這個順序
PATIENT_COLUMNS = [
    "subject_id",
    "gender",
    "anchor_age",
    "anchor_year",
    "anchor_year_group",
    "dod",
    "marital_status",
    "race",
    "language",
    "_batch_id",
]


def select_latest_admission(admissions: DataFrame) -> DataFrame:
    """每位病人只留最後一次住院（GLOSSARY「最後一次住院」）。

    Args:
        admissions: silver.admission。一列是一次住院，已經通過品質檢查；
            `admittime` 是 TIMESTAMP_NTZ，不會是空白。

    Returns:
        欄位和 `admissions` 完全一樣（名稱、順序都一樣），但一位病人（`subject_id`）
        只有一列：`admittime` 最晚的那一次住院。

    規則：
        - 只比 `admittime`。輸入的列沒有固定順序，不能靠「排在最後面的那一列」；
          `hadm_id` 的大小也和時間先後無關。
        - 整列照取：最後一次住院的婚姻是空白，結果就是空白，不往前面的住院找值。
        - 同一位病人有兩次住院的 `admittime` 一樣時，挑哪一筆都可以（已知限制，真實資料 0 筆）。
    """
    raise NotImplementedError("由 HCY 實作")


def build_patient(patients: DataFrame, latest_admissions: DataFrame) -> DataFrame:
    """組成 silver.patient（GLOSSARY「目前狀態」）。

    Args:
        patients: 通過品質檢查、型別已轉好的病人（`cast_patients` 的輸出），一位病人一列。
        latest_admissions: `select_latest_admission` 的輸出，一位病人一列。

    Returns:
        欄位照 `PATIENT_COLUMNS` 的順序：
        - `subject_id` 到 `dod`，以及 `_batch_id`：取自 `patients`（兩邊都有 `_batch_id`）
        - `marital_status`、`race`、`language`：取自最後一次住院
        每位通過檢查的病人都要有一列；沒有任何住院的病人也留著，那三欄是空白。
    """
    raise NotImplementedError("由 HCY 實作")
