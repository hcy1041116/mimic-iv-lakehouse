# 0002 邏輯表名加各環境的 config

- 狀態：accepted（2026-11-26）

同一份程式要在本機（PySpark + Delta）和 Databricks Free Edition 上跑，之後可能還要搬到 Azure Databricks 或 Fabric。兩邊存表的方式不一樣：本機沒有 metastore，用路徑最簡單；Databricks 用 Unity Catalog，表名是 `catalog.schema.table`。所以程式裡只寫邏輯表名「層.表」，例如 `silver.patient`，由 `conf/<env>.toml` 決定它實際在哪裡。這是前身 ADR-0007 的做法，換成 MIMIC 後照用。

## 考慮過的選項

- **全部用路徑**：本機可以，但 Unity Catalog 不建議用路徑管理表。
- **全部用表名**：Databricks 可以，但本機要另外架 Hive metastore，否則 Spark 重開後表名就不見了。

## 後果

- 層只有 `bronze`、`silver`、`gold`、`quality`、`ops` 五種，其他寫法一律報錯。
- 讀寫表都要經過 `src/common/spark.py` 的 `read_table`、`write_table`，不能直接寫 `spark.table()` 或寫死路徑。
- 本機的表寫在 `output/lakehouse/<層>/<表>`，`output/` 不進 Git。測試改寫到暫存資料夾。
- Databricks 的 catalog 先用內建的 `workspace`，第 0 步實測 `CREATE CATALOG` 成功的話，再改 `conf/databricks.toml` 一行。
- 換平台時，多加一份 config。如果新平台存表的方式和這兩種都不同，`table_location` 要多一種寫法。
