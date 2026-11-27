# Databricks Free Edition 的限制

2026-11-26 整理。標「原文有寫」的，來自官方限制頁 [Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)（2026-11-16 更新，這次讀了原文）。標「要實測」的，限制頁沒寫，第一次登入時試。

| 項目 | 內容 | 來源程度 |
|---|---|---|
| 運算 | 只有 serverless，不能自訂 cluster | 原文有寫 |
| 額度 | 每天有運算額度，沒有公布數字。超過的話當天停用（極端時整個月停用），資料和設定不會刪 | 原文有寫 |
| RDD、SparkContext | serverless 不支援，只能用 DataFrame API | 前身 ADR-0007 寫的，這次沒重新確認 |
| Python | 3.12.3，和本機一樣 | 實測（2026-11-26，serverless notebook 的 `sys.version`） |
| Spark | 4.2.0，和本機的 PySpark 一樣 | 實測（2026-11-26，`spark.version`） |
| session 時區預設值 | `Etc/UTC`，和 `UTC` 是同一個時區 | 實測（2026-11-26）。程式還是會明確設成 UTC（ADR-0003） |
| Job | 可以用，整個帳號同時最多 5 個 job task | 原文有寫 |
| Lakeflow pipeline | 每種 pipeline 同時只能有一個在跑 | 原文有寫 |
| SQL warehouse | 一個，大小限 2X-Small | 原文有寫 |
| 對外網路 | 只能連少數信任的網域，清單沒公布 | 原文有寫 |
| 從 PhysioNet 直接下載 | 大概不行，所以資料從本機上傳到 Volume | 我的推論 |
| 自己建 catalog | 可以：`CREATE CATALOG IF NOT EXISTS mimic_demo` 成功 | 實測（2026-11-26） |
| Volume | 可以：建了 managed volume `mimic_demo.landing.mimic_iv_demo`，從網頁上傳兩個檔案，大小和本機一樣。`dbutils.fs.ls` 列出的路徑開頭是 `dbfs:/Volumes/...` | 實測（2026-11-26） |
| Git folder | 可以：公開的 GitHub repo 直接建成 Git folder，不用登入，也不用 token。對外網路雖然有限制，Git folder 還是連得到 GitHub | 實測（2026-11-27） |
| Git folder 裡 notebook 的工作目錄 | notebook 所在的資料夾，所以 `Path.cwd().parent / "src"` 找得到程式 | 實測（2026-11-27，`notebooks/run_bronze.py`） |
| 程式設定 session 時區 | serverless 允許 `spark.conf.set("spark.sql.session.timeZone", "UTC")` | 實測（2026-11-27） |
| Delta 寫進 Unity Catalog | `saveAsTable` 加 `replaceWhere` 可以建新表，同一批重跑時只取代那一批，筆數不變 | 實測（2026-11-27，跑兩次都是 100 筆和 275 筆） |
| `TIMESTAMP_NTZ`、`try_cast` | 都可以用：`silver.admission` 的時間欄位是 `TimestampNTZType`，275 筆、warn 20 筆，和本機一樣 | 實測（2026-11-27） |
| 自己的雲端儲存體、外部位置 | 不支援「自訂 workspace 儲存位置」。外部位置限制頁沒提，大概練不到 | 前半原文有寫，後半是我的推論 |
| 用途 | 只能非商業用途；作品集不算商業用途 | 前半原文有寫，後半是我的推論 |
| 帳號 | 長期不用可能被刪，沒有 SLA | 原文有寫 |
| 不支援的功能 | R 和 Scala、Online tables、Clean rooms、所有舊版功能等 | 原文有寫 |

## 第一次登入要實測的

1. 在 serverless notebook 跑 `spark.version`、`import sys; sys.version`、`spark.conf.get("spark.sql.session.timeZone")`，確認上面兩條「前身 ADR-0007 寫的」。（2026-11-26 完成，見上表）
2. `CREATE CATALOG <名稱>`：成功就用自己的 catalog，失敗就改用 `workspace`。（2026-11-26 完成：成功，用 `mimic_demo`）
3. 建一個 Volume，上傳一個檔案。（2026-11-26 完成）
4. 建 Git folder 連到 GitHub repo。要先有 repo（建 repo 要先問使用者）。private repo 需要 GitHub token，token 不能進 repo，也不能印出來。（2026-11-27 完成：公開 repo，不用 token）

結果寫回這份文件，把「要實測」改成實測結果。
