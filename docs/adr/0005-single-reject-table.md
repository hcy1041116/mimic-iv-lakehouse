# 0005 所有來源共用一張 reject 表，違規的資料存成 JSON

- 狀態：accepted（2026-11-27）

品質規則分 error（擋下，不進 Silver）和 warn（只記錄，照樣往下走），reject 的 grain 是「規則 × 資料」（10 月定案）。所有來源表共用一張 `quality.reject`，欄位是 `batch_id`、`source_table`、`rule`、`severity`、`record_key`、`record`。`record` 是違規那一列來源欄位的 JSON，包括 `_corrupt_record`，留作證據。

## 考慮過的選項

- **每張來源表一張 reject 表，欄位和來源一樣**：查起來直覺。但每加一張來源表就要多一張 reject 表，也沒辦法一次查「這一批總共擋下多少」。
- **只存主鍵**：最省空間。但主鍵本身空白的那一筆就找不到了，轉不過去的值（例如 `2150-13-40`）也看不到。

## 後果

- 整列完全一樣的重複資料先 distinct 掉，不算 reject。同一個主鍵但內容不同的，每一筆都算 error，因為不知道哪一筆才對。
- 多了一條規則 `line_malformed`（error）：格子數不對的行在 Bronze 照樣落地（ADR-0004），到這裡擋下。沒有這條規則的話，缺欄位的那一行會帶著一堆 null 進到 Silver。
- 同一批、同一張來源表重跑時，那部分的 reject 整批取代，不會疊加。
- 筆數核對：Bronze = Silver + 被 error 擋下的不同資料 + 去重掉的完全重複列。被擋下的筆數是從 reject 表另外數的（`record` 去重後的筆數），不是用減法湊出來的。
- 轉型別用 `try_cast`。只有 `admittime` 有規則把關，其他欄位轉不過去會變成 null，不記 reject（已知限制）。真實資料的測試確認一筆都沒有。
