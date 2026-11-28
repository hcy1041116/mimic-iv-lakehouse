# MIMIC-IV Lakehouse

這個專案用 MIMIC-IV 展示版的醫院資料表，建一條 Bronze → Silver → Gold 的 Lakehouse 管線。同一份 PySpark + Delta 程式，在本機和 Databricks Free Edition 上都能跑，兩邊跑出的筆數一樣。

資料是一家美國教學醫院去識別化後的真實病歷，以醫院系統匯出的關聯式表發布。內容有真實的髒資料：語言填 `?`、婚姻空白，同一位病人在不同次住院登記的種族也可能不一樣。

## 管線

```
PhysioNet 下載的 CSV（patients、admissions）
  │
  ▼  Bronze：原樣落地，每一格存原始字串，加上來源檔、批次、載入時間
bronze.patients (100)          bronze.admissions (275)
  │                              │
  ▼  品質規則：error 擋下、warn 記錄，違規的資料寫進 quality.reject（規則 × 資料）
  │                              ▼
  │                            silver.admission (275)：時間轉成 TIMESTAMP_NTZ
  ▼                              │
silver.patient (100)  ◄──────────┘  每位病人取最後一次住院的婚姻、種族、語言
  │
  ▼  Gold：SQL
gold.patient_summary (100)：每位病人住了幾次院

ops.row_count：每次執行、每一層的筆數核對，有一項對不上就讓整次執行失敗
```

用展示版資料跑出來的結果：

| 核對 | 筆數 |
|---|---|
| Bronze = 來源行數 − 表頭 | patients 100、admissions 275 |
| Silver = Bronze − 被 error 擋下 − 完全重複 | admission 275、patient 100 |
| quality.reject | error 0、warn 20（語言填 `?`） |
| Gold 列數 = 病人數；住院次數加總 = 住院筆數 | 100；275 |
| 同一批連跑兩次 | 除了載入時間，每張表逐列相同 |

## 在本機跑

需要：Linux 或 WSL2、Java 17、[uv](https://docs.astral.sh/uv/)（Python 3.12 會由 uv 安裝）。

1. 下載資料。MIMIC-IV Clinical Database Demo 2.2 是公開資料（ODbL 授權），不用申請：

   ```bash
   mkdir -p data/mimic-iv-demo-2.2/hosp
   for f in patients admissions; do
     curl -fL -o data/mimic-iv-demo-2.2/hosp/$f.csv.gz \
       https://physionet.org/files/mimic-iv-demo/2.2/hosp/$f.csv.gz
   done
   ```

   有一個測試會拿官方的 FHIR 版來比對，那個測試要另外下載 MIMIC-IV on FHIR Demo 2.1.0 的 `fhir/MimicPatient.ndjson.gz`，放在 `data/mimic-iv-fhir-demo-2.1.0/fhir/`。沒有下載的話，那個測試會自動跳過。

2. 執行：

   ```bash
   uv sync
   uv run python src/pipeline.py --env local --batch batch_001   # 跑完整條管線，表寫在 output/lakehouse/
   uv run pytest                                                 # 測試
   uv run ruff check .
   ```

## 在 Databricks Free Edition 跑

1. 在 SQL 或 notebook 建 catalog、schema 和 Volume：

   ```sql
   CREATE CATALOG IF NOT EXISTS mimic_demo;
   CREATE SCHEMA IF NOT EXISTS mimic_demo.landing;
   CREATE VOLUME IF NOT EXISTS mimic_demo.landing.mimic_iv_demo;
   ```

2. 把兩個 CSV 上傳到 `/Volumes/mimic_demo/landing/mimic_iv_demo/mimic-iv-demo-2.2/hosp/`。
3. Workspace → Create → Git folder，貼上這個 repo 的網址。
4. 打開 `notebooks/run_pipeline`，運算資源選 Serverless，按 Run all。

`bronze`、`silver`、`gold`、`quality`、`ops` 這幾個 schema 由程式建立。serverless 的環境版本固定在 `pyproject.toml`。

## 專案結構

| 路徑 | 內容 |
|---|---|
| `conf/` | 各環境的設定：表存在哪、來源檔在哪、時區 |
| `src/pipeline.py` | 整條管線的入口：依序跑每一層，最後核對筆數 |
| `src/common/` | 讀設定、把邏輯表名（例如 `silver.patient`）換成各環境的實際位置、Spark session |
| `src/ingest/` | Bronze |
| `src/quality/` | 品質規則和 reject |
| `src/transform/` | Silver 和 Gold |
| `sql/` | Gold 的 SQL |
| `notebooks/` | Databricks 的入口 notebook |
| `tests/` | pytest，用 `tests/fixtures/` 的手工小樣本和真實的展示版資料 |
| `scripts/explore/` | 探索資料的腳本，只用標準函式庫 |

## 設計決定和紀錄

- [ADR-0001](docs/adr/0001-mimic-iv-demo-as-source.md)：資料來源用 MIMIC-IV 展示版的醫院資料表
- [ADR-0002](docs/adr/0002-logical-table-names-and-env-config.md)：邏輯表名加各環境的設定，換平台只多一份設定
- [ADR-0003](docs/adr/0003-timestamp-ntz-and-utc-session.md)：時間存成 `TIMESTAMP_NTZ`，session 時區固定 UTC
- [ADR-0004](docs/adr/0004-bronze-csv-as-raw-strings.md)：Bronze 把 CSV 存成每欄的原始字串
- [ADR-0005](docs/adr/0005-single-reject-table.md)：所有來源共用一張 reject 表，違規的資料存成 JSON
- [GLOSSARY.md](GLOSSARY.md)：專案裡的名詞，例如「版本」和「最後一次住院」的差別
- [docs/mimic-demo-findings.md](docs/mimic-demo-findings.md)：實測的筆數、髒資料，以及官方轉 FHIR 時的做法
- [docs/databricks-free-edition.md](docs/databricks-free-edition.md)：Free Edition 的限制和實測結果
- [LESSONS.md](LESSONS.md)：踩過的坑

## 範圍

目前完成的是 MVP：`patients`、`admissions` 兩張表，跑一個批次，Silver 和 Gold 每次整張重建。還沒做的：其他醫院資料表（診斷、檢驗、處方）、增量處理、醫院資料表 → FHIR 的轉換。

## 資料授權

只使用公開的 [MIMIC-IV Clinical Database Demo](https://physionet.org/content/mimic-iv-demo/2.2/) 和 [MIMIC-IV on FHIR Demo](https://physionet.org/content/mimic-iv-fhir-demo/2.1.0/)（ODbL）。資料檔不放進這個 repo。完整版 MIMIC-IV 需要 PhysioNet 認證，這個專案沒有使用。
