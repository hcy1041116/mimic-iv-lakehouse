"""Check how the official MIMIC-IV on FHIR demo mapped two things from the hosp tables.

1. admissions.admission_type -> Encounter.class
2. per-admission demographics (marital status, race) -> the single value on Patient

Usage: python3 -I fhir_mapping_checks.py <hosp dir> <fhir dir>
"""

import csv
import gzip
import json
import sys
from collections import Counter, defaultdict

hosp, fhir = sys.argv[1], sys.argv[2]

with gzip.open(f"{hosp}/admissions.csv.gz", "rt", newline="") as f:
    adm = sorted(csv.DictReader(f), key=lambda a: a["admittime"])

with gzip.open(f"{fhir}/MimicEncounter.ndjson.gz", "rt") as f:
    encs = [json.loads(line) for line in f]
enc_by_hadm = {i["value"]: e for e in encs for i in e.get("identifier", [])}

print("== admission_type -> FHIR Encounter.class")
pairs = Counter(
    (a["admission_type"], enc_by_hadm.get(a["hadm_id"], {}).get("class", {}).get("code"))
    for a in adm
)
for (adm_type, cls), n in sorted(pairs.items()):
    print(f"  {adm_type:28s} -> {cls}: {n}")

for col in ["race", "marital_status", "language", "insurance"]:
    values = defaultdict(set)
    for a in adm:
        values[a["subject_id"]].add(a[col])
    changed = sum(1 for v in values.values() if len(v) > 1)
    print(f"== patients whose {col} differs across admissions: {changed}")

with gzip.open(f"{fhir}/MimicPatient.ndjson.gz", "rt") as f:
    patients = {p["identifier"][0]["value"]: p for p in map(json.loads, f)}

print("== which admission's value the FHIR Patient kept (admissions in time order)")
history = defaultdict(list)
for a in adm:
    history[a["subject_id"]].append((a["admittime"][:10], a["marital_status"] or "(blank)", a["race"]))
for sid, rows in history.items():
    if len({r[1] for r in rows}) > 1 or len({r[2] for r in rows}) > 1:
        p = patients[sid]
        marital = p.get("maritalStatus", {}).get("coding", [{}])[0].get("code")
        race_ext = [e for e in p.get("extension", []) if e["url"].endswith("us-core-race")]
        race = race_ext[0]["extension"][-1].get("valueString") if race_ext else None
        print(f"  {sid} | FHIR marital: {marital} | FHIR race: {race}")
        for r in rows:
            print("     ", r)
