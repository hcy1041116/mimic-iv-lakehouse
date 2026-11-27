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

## 2026-11-27 `F.col('rank' == 1)`：括號包錯位置

- 現象：`where(F.col('rank' == 1))` 一執行就報錯，訊息埋在一大串 Java 堆疊的最後：`Method col([class java.lang.Boolean]) does not exist`。
- 原因：Python 先算括號裡面的 `'rank' == 1`。字串和數字比較的結果是 `False`，所以實際上變成 `F.col(False)`。
- 做法：
  - `F.col("欄位名")` 的括號裡只放欄位名，比較寫在括號外面：`F.col("rank") == 1`。
  - 看 PySpark 的錯誤時，直接找最後幾行 `E` 開頭的訊息。`java.lang.Boolean` 這類型別名稱，就是在告訴你函式收到了什麼。

## 2026-11-27 Databricks 執行 Git folder 裡的 notebook，會自己改檔案

- 現象：在 Git folder 裡什麼都沒改，只按了 Run all，Git 視窗就列出兩個「已修改」的檔案。之後 Pull 時，`run_pipeline.py` 就 conflict。
  - `notebooks/run_pipeline.py`：檔案最後的換行被拿掉了（diff 顯示 `\ No newline at end of file`）
  - `pyproject.toml`：多了一段 `[tool.databricks.environment]`、`environment_version = '6'`，最後也沒有換行
- 原因：Databricks 用自己的格式重新存 notebook，而且會把 serverless 的環境版本記進 Git folder 裡的 `pyproject.toml`。Databricks 檔案的 version history 是 workspace 自己的存檔紀錄，和 Git 無關：被改寫後的內容就是它的起點（`pyproject.toml` 的 version history 甚至是空的，只有 Pending version），看不到 GitHub 原本的版本。要知道和 GitHub 差在哪，只能看 Git 視窗的 diff。上一條「改過 Git folder 裡的 notebook，Pull 時會 conflict」，很可能也是這個原因。
- 做法：
  - repo 裡的檔案直接存成 Databricks 存出來的樣子：`notebooks/` 底下的檔案最後不加換行；`pyproject.toml` 寫好 `environment_version = '6'`，最後也不加換行。這樣執行完不會再出現「已修改」。
  - 順便把 serverless 的環境版本固定在 repo 裡，別人重跑時用的是同一版。
  - 用工具整個重寫這些檔案時，要記得最後不能加換行。
  - Pull 前還是先看一眼 Git 視窗，有自己沒改的修改就先 Discard。
