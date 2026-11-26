# 0003 時間存成 TIMESTAMP_NTZ，Spark session 時區固定 UTC

- 狀態：accepted（2026-11-26）

MIMIC 的時間字串沒有時區，例如 `2140-10-22 22:04:00`。Spark 一般的 `TIMESTAMP` 型別代表「某個時刻」，把沒有時區的字串轉進來時，會用 session 時區去解讀。本機 Spark 預設的 session 時區是 `Asia/Taipei`（前身實測，見前身的 LESSONS.md），Databricks Free Edition 預設是 `Etc/UTC`（2026-11-26 實測）。不固定的話，同一份程式在兩邊算出來的日期可能差一天。

## 考慮過的選項

- **`TIMESTAMP` 加上 session 固定 UTC**：前身的做法。可以動，但等於假裝來源是 UTC，其實來源根本沒有時區。
- **`TIMESTAMP_NTZ`**：不帶時區的時間型別，存的就是牆上時鐘的那個時間，不做任何換算。這個型別最接近來源的原意。

## 決定

時間欄位在 Silver 轉成 `TIMESTAMP_NTZ`；Bronze 照樣存字串。session 時區還是固定 UTC，當作保險，防止有地方不小心用到一般的 `TIMESTAMP`。

## 後果

- 本機實測：`TIMESTAMP_NTZ` 寫進 Delta 再讀出來，型別和值都不變（`tests/test_smoke_delta.py`）。
- Databricks 上能不能寫，第 3 步實測（我的推論是可以）。
- 官方 FHIR 版一律加上 `-04:00`。之後做 FHIR 轉換時，要在那一層決定加不加時區，Silver 不加。
