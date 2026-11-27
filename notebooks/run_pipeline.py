# Databricks notebook source
# MAGIC %md
# MAGIC # MVP 管線：在 Databricks 上跑
# MAGIC
# MAGIC 用 Git folder 打開這本 notebook，運算資源選 **Serverless**，按 **Run all**。
# MAGIC
# MAGIC - 讀的是 `conf/databricks.toml` 指定的 Volume：`mimic_demo.landing.mimic_iv_demo`
# MAGIC - 寫進 `mimic_demo` 底下的 `bronze`、`quality`、`silver`
# MAGIC - 程式和本機跑的是同一份 `src/`；這本 notebook 只負責把它接起來

# COMMAND ----------

# 把 repo 的 src/ 加進 import 路徑。Git folder 裡的 notebook，工作目錄是 notebook 所在的資料夾
import sys
from pathlib import Path

SRC = Path.cwd().parent / "src"
if not (SRC / "common").is_dir():
    raise RuntimeError(f"找不到 {SRC}/common：這本 notebook 要從 repo 的 notebooks/ 資料夾打開")
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# COMMAND ----------

from common.config import load_config
from common.spark import ensure_schemas, get_spark, read_table
from ingest.bronze import CORRUPT_COLUMN, SOURCE_FILES, load_bronze
from transform.silver import build_silver_admission, build_silver_patient

BATCH_ID = "batch_001"

cfg = load_config("databricks")
spark = get_spark(cfg)
ensure_schemas(spark, cfg)
print("session 時區：", spark.conf.get("spark.sql.session.timeZone"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze

# COMMAND ----------

counts = load_bronze(spark, cfg, BATCH_ID)
print(counts)

# COMMAND ----------

# 核對：Bronze 這一批的筆數 = 來源行數 − 1（表頭）。行數用 text 格式另外數，不經過 CSV 解析
for table, relative in SOURCE_FILES.items():
    source_rows = spark.read.text(f"{cfg.source_root}/{relative}").count() - 1
    corrupt = read_table(spark, cfg, table).where(f"{CORRUPT_COLUMN} IS NOT NULL").count()
    status = "OK" if counts[table] == source_rows and corrupt == 0 else "不符"
    print(f"{status}  {table}: Bronze {counts[table]} 筆，來源 {source_rows} 筆，格子數不對 {corrupt} 筆")
    assert counts[table] == source_rows and corrupt == 0

# COMMAND ----------

# MAGIC %md
# MAGIC ## 品質檢查 → silver.admission

# COMMAND ----------

silver_counts = build_silver_admission(spark, cfg, BATCH_ID)
print(silver_counts)

# 核對：Bronze = Silver + 被 error 擋下的資料 + 去重掉的完全重複列
c = silver_counts
ok = c["bronze"] == c["silver"] + c["rejected_records"] + c["duplicates_removed"]
print("OK" if ok else "不符", " bronze = silver + rejected_records + duplicates_removed")
assert ok

# 時間欄位的型別：要是 TimestampNTZType
print("admittime 型別：", read_table(spark, cfg, "silver.admission").schema["admittime"].dataType)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 品質檢查 → silver.patient（人口資料取自最後一次住院）

# COMMAND ----------

patient_counts = build_silver_patient(spark, cfg, BATCH_ID)
print(patient_counts)

c = patient_counts
ok = c["bronze"] == c["silver"] + c["rejected_records"] + c["duplicates_removed"]
print("OK" if ok else "不符", " bronze = silver + rejected_records + duplicates_removed")
assert ok

# COMMAND ----------

display(read_table(spark, cfg, "quality.reject").groupBy("source_table", "rule", "severity").count())