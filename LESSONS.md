# LESSONS

踩過的坑。每條寫：現象、原因、做法。

## 2026-11-27 Spark 4 的 cast 遇到轉不過去的值，會讓整個工作失敗

- 現象：`F.col("admittime").cast("timestamp_ntz")` 碰到 `2150-13-40 10:00:00`，直接丟出 `DateTimeException`，整個查詢失敗。Spark 3 的時候，同樣的寫法是回傳 null。
- 原因：Spark 4 預設打開 ANSI 模式（`spark.sql.ansi.enabled`），型別轉換失敗就報錯，不再默默變成 null。Databricks serverless 也是 Spark 4。
- 做法：
  - Silver 轉型別一律用 `try_cast`，轉不過去的值會變成 null，管線不會因為一筆髒資料停下來。
  - 會被轉成 null 的情況，要嘛有品質規則先擋下（`admittime_invalid`），要嘛記成已知限制，並用真實資料的測試確認一筆都沒有（`tests/test_silver_real_data.py`）。
  - 只在確定資料一定乾淨的地方才用 `cast`，例如測試裡自己造的資料。
