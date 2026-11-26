"""Profile data-quality issues in the MIMIC-IV demo hosp tables (stdlib only)."""

import csv
import gzip
import sys
from collections import Counter
from pathlib import Path

hosp = Path(sys.argv[1])


def rows(name):
    with gzip.open(hosp / f"{name}.csv.gz", "rt", newline="") as f:
        yield from csv.DictReader(f)


def pct(n, d):
    return f"{n}/{d} ({n / d:.1%})" if d else f"{n}/0"


patients = list(rows("patients"))
pids = {r["subject_id"] for r in patients}
print("== patients")
print("  gender:", Counter(r["gender"] for r in patients))
print("  dod filled:", pct(sum(1 for r in patients if r["dod"]), len(patients)))
years = sorted(int(r["anchor_year"]) for r in patients)
print("  anchor_year range:", years[0], "-", years[-1])
print("  anchor_age range:", min(int(r["anchor_age"]) for r in patients), "-",
      max(int(r["anchor_age"]) for r in patients))

adm = list(rows("admissions"))
hadms = {r["hadm_id"] for r in adm}
print("== admissions")
print("  per patient:", Counter(Counter(r["subject_id"] for r in adm).values()).most_common(5))
print("  language:", Counter(r["language"] for r in adm).most_common(6))
print("  marital_status:", Counter(r["marital_status"] for r in adm).most_common(6))
print("  race distinct:", len({r["race"] for r in adm}), "e.g.",
      Counter(r["race"] for r in adm).most_common(4))
print("  dischtime < admittime:", sum(1 for r in adm if r["dischtime"] < r["admittime"]))
print("  deathtime filled but expire_flag=0:",
      sum(1 for r in adm if r["deathtime"] and r["hospital_expire_flag"] == "0"))
print("  expire_flag=1 but deathtime empty:",
      sum(1 for r in adm if not r["deathtime"] and r["hospital_expire_flag"] == "1"))
print("  edregtime empty:", pct(sum(1 for r in adm if not r["edregtime"]), len(adm)))

dx = list(rows("diagnoses_icd"))
dict_dx = {(r["icd_code"], r["icd_version"]) for r in rows("d_icd_diagnoses")}
print("== diagnoses_icd")
print("  icd_version:", Counter(r["icd_version"] for r in dx))
print("  code not in dictionary:", sum(1 for r in dx if (r["icd_code"], r["icd_version"]) not in dict_dx))
print("  hadm_id not in admissions:", sum(1 for r in dx if r["hadm_id"] not in hadms))

lab_items = {r["itemid"]: r for r in rows("d_labitems")}
labs = list(rows("labevents"))
n = len(labs)
print("== labevents")
print("  hadm_id empty (not during an admission):", pct(sum(1 for r in labs if not r["hadm_id"]), n))
text_only = [r for r in labs if r["value"] and not r["valuenum"]]
print("  value is text, valuenum empty:", pct(len(text_only), n))
print("    top text values:", Counter(r["value"] for r in text_only).most_common(8))
print("  value AND valuenum empty:", pct(sum(1 for r in labs if not r["value"] and not r["valuenum"]), n))
print("  valueuom empty:", pct(sum(1 for r in labs if not r["valueuom"]), n))
print("  itemid not in d_labitems:", sum(1 for r in labs if r["itemid"] not in lab_items))
print("  storetime < charttime:", sum(1 for r in labs if r["storetime"] and r["storetime"] < r["charttime"]))
print("  flag:", Counter(r["flag"] for r in labs))
print("  subject not in patients:", sum(1 for r in labs if r["subject_id"] not in pids))
# same lab label measured in several units?
units = {}
for r in labs:
    if r["valueuom"]:
        units.setdefault(lab_items.get(r["itemid"], {}).get("label", "?"), set()).add(r["valueuom"])
multi = {k: v for k, v in units.items() if len(v) > 1}
print("  lab labels with >1 unit:", len(multi), "e.g.", list(multi.items())[:3])
labels = Counter(v["label"] for v in lab_items.values())
print("  d_labitems labels used by >1 itemid:", sum(1 for c in labels.values() if c > 1),
      "e.g.", [k for k, c in labels.most_common(3)])

rx = list(rows("prescriptions"))
m = len(rx)
print("== prescriptions")
print("  ndc empty or 0:", pct(sum(1 for r in rx if r["ndc"] in ("", "0")), m))
print("  stoptime empty:", pct(sum(1 for r in rx if not r["stoptime"]), m))
print("  stoptime < starttime:", sum(1 for r in rx if r["stoptime"] and r["stoptime"] < r["starttime"]))


def is_num(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


odd = [r["dose_val_rx"] for r in rx if r["dose_val_rx"] and not is_num(r["dose_val_rx"])]
print("  dose_val_rx not a number:", pct(len(odd), m), "e.g.", Counter(odd).most_common(6))
print("  same drug, different spelling e.g.:",
      sorted({r["drug"] for r in rx if r["drug"].lower().startswith("acetaminophen")})[:6])
