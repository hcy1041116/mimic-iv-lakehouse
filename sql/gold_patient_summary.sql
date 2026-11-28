-- gold.patient_summary：每位病人住了幾次院（HCY 實作）
--
-- 可以用的表（程式會先把 Silver 表註冊成 temp view，課程第 37 課教的那種）：
--   silver_patient    一位病人一列：subject_id, gender, anchor_age, anchor_year, anchor_year_group,
--                     dod, marital_status, race, language, _batch_id
--   silver_admission  一次住院一列：subject_id, hadm_id, admittime, dischtime, ...（還有其他欄位）
--
-- 輸出欄位（名稱、順序都要一樣）：
--   subject_id, gender, anchor_age, admission_count
--
-- 規則：
--   - 每位病人一列，silver_patient 裡的每一位都要有
--   - admission_count 是這位病人在 silver_admission 裡有幾次住院
--   - 沒有任何住院的病人也要有一列，admission_count 是 0
--
-- 測試：uv run pytest tests/test_gold.py
WITH cnt AS (
    SELECT subject_id, count(*) AS admission_count 
    FROM silver_admission
    GROUP BY subject_id
)

SELECT p.subject_id, p.gender, p.anchor_age, coalesce(a.admission_count, 0) as admission_count
FROM silver_patient p LEFT JOIN cnt a ON p.subject_id = a.subject_id;