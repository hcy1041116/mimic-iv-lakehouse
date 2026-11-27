# LESSONS

踩過的坑。每條寫：現象、原因、做法。

## 2026-11-27 Spark 4 的 cast 遇到轉不過去的值，會讓整個工作失敗

- 現象：`F.col("admittime").cast("timestamp_ntz")` 碰到 `2150-13-40 10:00:00`，直接丟出 `DateTimeException`，整個查詢失敗。Spark 3 的時候，同樣的寫法是回傳 null。
- 原因：Spark 4 預設打開 ANSI 模式（`spark.sql.ansi.enabled`），型別轉換失敗就報錯，不再默默變成 null。Databricks serverless 也是 Spark 4。
- 做法：
  - Silver 轉型別一律用 `try_cast`，轉不過去的值會變成 null，管線不會因為一筆髒資料停下來。
  - 會被轉成 null 的情況，要嘛有品質規則先擋下（`admittime_invalid`），要嘛記成已知限制，並用真實資料的測試確認一筆都沒有（`tests/test_silver_real_data.py`）。
  - 只在確定資料一定乾淨的地方才用 `cast`，例如測試裡自己造的資料。

## 2026-11-27 改過 Git folder 裡的 notebook，Pull 時會 conflict

- 現象：在 Databricks 的 Git folder 裡打開 `run_bronze` 時動到了內容。之後 GitHub 上把它改名成 `run_pipeline`，按 Pull 就出現 conflict，兩個檔案同時留在 Git folder 裡。
- 原因：Git folder 是 GitHub 的一份影本。影本上有還沒 commit 的修改，GitHub 上又改了同一個檔案（這次是改名），Git 不知道該聽哪一邊。
- 做法：
  - 打開 Git 視窗，對不想留的修改按 **Discard changes**，影本就會回到和 GitHub 一樣。
  - 把 Git folder 當成唯讀：要試東西，在 Git folder 外面另外開一本 notebook。
  - Pull 之前先看 Git 視窗；如果列出自己不記得改過的檔案，先處理掉再 Pull。
  - 真的弄亂了，就刪掉 Git folder 重建。程式在 GitHub 上，表在 catalog 裡，Volume 裡的檔案也不受影響。
