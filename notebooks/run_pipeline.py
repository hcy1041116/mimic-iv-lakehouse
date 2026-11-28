# Databricks notebook source
# MAGIC %md
# MAGIC # MVP 管線：在 Databricks 上跑
# MAGIC
# MAGIC 用 Git folder 打開這本 notebook，運算資源選 **Serverless**，按 **Run all**。
# MAGIC
# MAGIC - 跑的是 `src/pipeline.py` 的 `run()`，和本機 `uv run python src/pipeline.py` 是同一份程式
# MAGIC - 讀 `conf/databricks.toml` 指定的 Volume：`mimic_demo.landing.mimic_iv_demo`
# MAGIC - 寫進 `mimic_demo` 底下的 `bronze`、`quality`、`silver`、`gold`、`ops`
# MAGIC - 每一層的筆數核對寫進 `ops.row_count`，有任何一項對不上，這一格就會報錯

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
from common.spark import get_spark, read_table
from pipeline import run

BATCH_ID = "batch_001"

cfg = load_config("databricks")
spark = get_spark(cfg)

for check in run(spark, cfg, BATCH_ID):
    print(f"OK  {check['check_name']}：{check['actual']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 每次執行的筆數核對（ops.row_count，最新的在最上面）

# COMMAND ----------

display(read_table(spark, cfg, "ops.row_count").orderBy("run_at", ascending=False))

# COMMAND ----------

display(read_table(spark, cfg, "quality.reject").groupBy("source_table", "rule", "severity").count())