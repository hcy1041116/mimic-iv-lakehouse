# 0001 資料來源用 MIMIC-IV 展示版的醫院資料表

- 狀態：accepted（2026-11-26）

前身 `fhir-lakehouse` 用 Synthea 產生 FHIR 資料，卡在三件事：Synthea 不是 FHIR 伺服器，版本、更新時間、增量都要另外寫模擬器去假造；資料太乾淨，error 級的品質規則全部是 0 筆；台灣醫院做資料工程，實際碰到的來源比較可能是醫院系統（HIS）的資料表，而不是 FHIR（推論，依據見 [background.md](../background.md)）。所以這個專案改用 MIMIC-IV Clinical Database Demo 2.2 的 `hosp` 資料表當來源。它是美國一家教學醫院去識別化後的真實病歷，以醫院系統匯出的關聯式表發布，100 位病人，ODbL 開放授權，不用申請。同一批病人有官方轉好的 MIMIC-IV on FHIR Demo 2.1.0，之後做「醫院資料表 → FHIR」時拿來對答案。實測結果見 [mimic-demo-findings.md](../mimic-demo-findings.md)。

## 考慮過的選項

- **維持 Synthea FHIR**：資料量大（1000 多人），但上面三個問題都還在。
- **MIMIC-IV on FHIR 展示版當主來源**：管線設計幾乎不用改，資料也是真的；但起點仍是 FHIR，不是醫院系統的資料表，而且 `meta` 一樣沒有 `lastUpdated`。改為「對答案」用。
- **OpenMRS 展示資料**：表結構是真的醫院系統，約 5,000 人；但資料是示範用的，還要把整套系統架起來才能產生異動。
- **健保申報 XML**：台灣在地，格式公開；但沒有資料，要自己產，而且是申報資料，不是臨床資料。

換來源之前，還考慮過轉向做 FHIR 介接程式，參考 `swiftruru/rx-fhir`（建立處方、送到 FHIR 伺服器、驗證格式）。沒有採用，理由有三：那對應的是介接工程師的職缺，不是資料工程；技術是 TypeScript 和 Electron，不是 Python 和 Spark；照著做一份，看起來就是仿作。它對齊的 TW Core 規範（台灣的 FHIR 規範），留到「醫院資料表 → FHIR」階段再參考。

## 後果

- **只用展示版。** 完整版（約 30 萬人）要 PhysioNet 認證。PhysioNet 2025 年的說明提到，完整版的資料使用協議禁止把資料分享給第三方，包括透過 API 傳送，或放在線上平台使用（只看到搜尋摘要，[原文](https://physionet.org/news/post/llm-responsible-use/)沒有讀）。依此判斷，完整版就算申請到，大概也不能放上 Databricks Free Edition（推論，要讀協議原文才能確定；PhysioNet 官方提供的雲端管道是 GCP 和 AWS）。也不能給 agent 讀：agent 透過線上 API 運作，讀檔就等於把內容送出去。展示版公開，面試官可以自己下載重跑。
- **只有 100 人。** 檢驗有 10 萬多筆，夠用來展示管線；但看不出效能問題。用 Spark 和 Databricks 是為了展示目標職缺要的技能，設計上要能放大到完整版的規模（約展示版的 3,000 倍）。要測效能，之後可以把展示版的病人複製成很多份。
- **版本和時間是資料本來就有的，不用模擬。** 同一位病人每次住院都記一次婚姻、種族、保險，值會變；檢驗有採檢時間 `charttime` 和結果存入時間 `storetime`，可以做「結果晚到」的情境。但展示版是一次發布的靜態資料，沒有之後的更新。要做增量，仍要自己把資料切成幾批，例如照 `admittime` 或 `storetime` 切；真實的醫院系統靠的是表上的修改時間欄位，或資料庫的異動紀錄。怎麼切之後再決定。
- **日期被平移到 2110–2202 年，每位病人平移的量不同。** 「日期不能在未來」這類規則不適用；跨病人比較日曆時間沒有意義。
- **前身的決定。** 10 月 grill 定案的五條原則不變，寫在 AGENTS.md 的「10 月定案」，只依 CSV 和 MIMIC 調整細節，偏離要先問。五條是：Bronze 原樣保存加中繼欄位、來源 id 當鍵、error／warn 和 severity、版本比較順序、先檢查品質再選版本。前身 ADR 裡的其他做法預計保留，用到時依新資料確認，再寫成本專案的 ADR：
  - 邏輯表名加各環境 config：程式只寫邏輯表名，換平台只改 config
  - Spark session 時區固定 UTC：本機 Spark 預設 `Asia/Taipei`，Databricks 預設 UTC，不固定的話，同一份程式在兩邊取出的日期可能差一天
  - Silver 依版本 MERGE，Gold 全量重建

  細節見 `~/projects/fhir-lakehouse/docs/adr/` 和它的 `GLOSSARY.md`。前身的 0002（Synthea 產資料）和 0009（匯出模擬器）不再適用。
- **平台用 Databricks Free Edition，不用 Azure Databricks。** Azure Databricks 是課程用的平台，但會持續產生費用；Free Edition 做得到這個專案要的事，限制見 [databricks-free-edition.md](../databricks-free-edition.md)。代價是課程裡「自己的儲存體加外部位置」的做法，在 Free Edition 上大概練不到。之後可以花一天把同一份程式部署到 Azure，做完就刪掉整個 resource group。
- **開發在本機，驗收在 Free Edition。** 平常用 pytest 加本機 Spark。Free Edition 的對外網路只能連少數信任的網域，所以資料從本機上傳到 Volume。
