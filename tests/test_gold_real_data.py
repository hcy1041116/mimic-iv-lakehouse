"""用真實的展示版資料核對 gold.patient_summary。沒下載資料時跳過。

完成標準：100 列；住院次數加總 = silver.admission 的筆數（275）。
"""

from ingest.bronze import load_bronze
from transform.gold import build_gold_patient_summary
from transform.silver import build_silver_admission, build_silver_patient


def test_gold_reconciles_with_silver(spark, real_cfg):
    load_bronze(spark, real_cfg, "batch_001")
    build_silver_admission(spark, real_cfg, "batch_001")
    build_silver_patient(spark, real_cfg, "batch_001")

    assert build_gold_patient_summary(spark, real_cfg) == {
        "silver_patients": 100,
        "gold_rows": 100,
        "silver_admissions": 275,
        "admission_count_total": 275,
    }
