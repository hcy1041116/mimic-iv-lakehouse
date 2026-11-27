# MIMIC-IV 展示版：實測發現

2026-11-26 在本機實測，資料是 MIMIC-IV Clinical Database Demo 2.2 的 `hosp` 和 MIMIC-IV on FHIR Demo 2.1.0。數字都可以用 `scripts/explore/` 的程式重新產生（只用 Python 標準函式庫，參數是資料夾路徑）：

```
python3 -I scripts/explore/profile_hosp.py data/mimic-iv-demo-2.2/hosp
python3 -I scripts/explore/compare_fhir.py data/mimic-iv-demo-2.2/hosp data/mimic-iv-fhir-demo-2.1.0/fhir 10003400
python3 -I scripts/explore/fhir_mapping_checks.py data/mimic-iv-demo-2.2/hosp data/mimic-iv-fhir-demo-2.1.0/fhir
```

這些是後續品質規則和轉換設計的素材，不是決定。

## 資料表和筆數

| 表 | 筆數 | 一列是什麼 |
|---|---|---|
| `patients` | 100 | 一位病人。沒有姓名、沒有生日，只有性別、`anchor_year` 那年的年齡 `anchor_age`、死亡日 `dod` |
| `admissions` | 275 | 一次住院。婚姻、種族、語言、保險記在這裡，不在 `patients` |
| `diagnoses_icd` | 4,506 | 一次住院的一個診斷，ICD-9 有 2,193 筆、ICD-10 有 2,313 筆 |
| `labevents` | 107,727 | 一個檢驗結果 |
| `d_labitems` | 1,622 | 檢驗項目對照表：只有院內代碼 `itemid`、名稱、檢體、類別，**沒有 LOINC** |
| `prescriptions` | 18,087 | 一筆處方 |

## 和 FHIR 版對照

同一批 100 位病人。`patients`、`admissions`、`diagnoses_icd`、`labevents` 和 FHIR 的 Patient、Encounter、Condition、Observation 筆數一一相同。`prescriptions` 18,087 筆對 MedicationRequest 17,552 筆，差 535 筆，原因還沒查。

## 真實的資料問題

| 問題 | 筆數 |
|---|---|
| 處方的停藥時間早於開始時間 | 753 |
| 處方劑量不是數字，例如 `1-2`、`5-10`、`25,000` | 1,001（5.5%） |
| 處方的 NDC 藥品代碼空白或填 `0` | 2,631（14.5%） |
| 檢驗結果是文字、沒有數值，例如 `NEG`、`ART.`、`___` | 2,893（2.7%） |
| 檢驗的文字值和數值都空白 | 9,588（8.9%） |
| 檢驗沒有單位 | 14,042（13.0%） |
| 同一個檢驗名稱用了兩種單位，例如 MCHC 有 `%` 和 `g/dL` | 8 個名稱 |
| 名稱相同、但對到多個 `itemid` 的檢驗項目 | 207 組，包括 `Delete`、`Voided Specimen` 這種名稱 |
| 檢驗不屬於任何一次住院（`hadm_id` 空白） | 28,420（26.4%） |
| 住院資料的語言填 `?` | 20 |
| 同一位病人在不同次住院時，婚姻狀態不同 | 8 人 |
| 同一位病人在不同次住院時，種族不同（例如先 `UNKNOWN` 後 `WHITE`） | 4 人 |
| 同一位病人在不同次住院時，保險不同 | 5 人 |

查過但沒有問題的：出院早於入院、死亡旗標和死亡時間不一致、診斷代碼不在對照表、檢驗代碼不在對照表、參照到不存在的病人或住院，都是 0 筆。

## 官方轉 FHIR 時做的決定

- **人口資料取最後一次住院的值**：上面那幾位婚姻或種族會變的病人，FHIR Patient 上的值逐一核對，都是時間上最後一次住院的值。
- **生日是補出來的**：`patients` 只有「`anchor_year` 時幾歲」，FHIR 卻有完整生日，例如 10003400 是 `2062-06-05`。年份等於 2134 − 72，月和日在來源表裡找不到。
- **加了時區**：來源的時間沒有時區，FHIR 版一律加上 `-04:00`。
- **代碼沒有標準化**：檢驗用 MIMIC 自訂的代碼系統（`mimic-d-labitems`），診斷用自訂的 ICD-9、ICD-10 代碼系統網址，都不是 LOINC 或標準的 ICD 網址。
- **住院類別可能對錯了**：`admission_type` 對到 `Encounter.class` 時，`URGENT` 38 筆和 `ELECTIVE` 13 筆被標成 `AMB`（門診）。例如 10003400 的 `23559586` 住了 29 天、在院內過世，class 是 `AMB`。依 HL7 v3 ActCode，住院是 `IMP`。這是我們依代碼定義的判斷，官方可能有別的理由。
- **一樣沒有 `meta.lastUpdated`**，`meta` 裡只有 `profile`。
- **姓名是佔位字**，例如 `Patient_10003400`。
- **種族換成了美國 OMB 類別**（2026-11-27 實測）：FHIR Patient 的 `us-core-race` 不是原始值，而是對到的類別。例如 `HISPANIC/LATINO - CUBAN`、`PORTUGUESE`、`WHITE - BRAZILIAN` 都變成 `White`，`BLACK/CAPE VERDEAN` 變成 `Black or African American`，`UNKNOWN`、`OTHER`、`UNABLE TO OBTAIN` 變成 `unknown`，`PATIENT DECLINED TO ANSWER` 變成 `asked but unknown`。婚姻則是一對一換成代碼：`MARRIED` → `M`、`SINGLE` → `S`、`DIVORCED` → `D`、`WIDOWED` → `W`，空白 → `UNK`。

## 日期

所有日期都被平移到 2110–2202 年，每位病人平移的量不同：`anchor_year` 介於 2110 和 2201，住院和處方的時間在 2110–2201，檢驗的 `charttime`、`storetime` 到 2202。`anchor_year_group`（例如 `2011 - 2013`）才是這位病人真實就醫的年代區間。
