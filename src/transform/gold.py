"""Gold：給分析用的表，用 sql/ 底下的 SQL 從 Silver 算出來，每次整張重建。

SQL 裡只寫 temp view 的名字（`silver_patient`、`silver_admission`），不寫實際的表名或路徑，
所以同一份 SQL 在本機和 Databricks 都能跑：表在哪裡由這裡的程式依 config 決定。
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from common.config import REPO_ROOT, Config
from common.spark import read_table, write_table

SQL_DIR = REPO_ROOT / "sql"
SUMMARY_COLUMNS = ["subject_id", "gender", "anchor_age", "admission_count"]


def patient_summary(spark: SparkSession, silver_patient: DataFrame, silver_admission: DataFrame) -> DataFrame:
    """把兩張 Silver 表註冊成 temp view，執行 sql/gold_patient_summary.sql。"""
    silver_patient.createOrReplaceTempView("silver_patient")
    silver_admission.createOrReplaceTempView("silver_admission")
    return spark.sql((SQL_DIR / "gold_patient_summary.sql").read_text())


def build_gold_patient_summary(spark: SparkSession, cfg: Config) -> dict[str, int]:
    """silver.patient + silver.admission → gold.patient_summary。回傳核對用的筆數。

    核對：Gold 的列數 = 病人數；住院次數加總 = silver.admission 的筆數。
    """
    patients = read_table(spark, cfg, "silver.patient")
    admissions = read_table(spark, cfg, "silver.admission")
    write_table(patient_summary(spark, patients, admissions), cfg, "gold.patient_summary")

    gold = read_table(spark, cfg, "gold.patient_summary")
    return {
        "silver_patients": patients.count(),
        "gold_rows": gold.count(),
        "silver_admissions": admissions.count(),
        "admission_count_total": gold.agg(F.sum("admission_count")).first()[0] or 0,
    }
