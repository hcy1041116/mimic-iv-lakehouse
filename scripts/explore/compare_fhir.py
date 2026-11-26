"""Compare MIMIC-IV demo HIS tables with the MIMIC-IV on FHIR demo (stdlib only)."""

import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

hosp, fhir, pick = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]


def ndjson(name):
    with gzip.open(fhir / f"{name}.ndjson.gz", "rt") as f:
        for line in f:
            yield json.loads(line)


def csv_rows(name):
    with gzip.open(hosp / f"{name}.csv.gz", "rt", newline="") as f:
        yield from csv.DictReader(f)


his_patients = {r["subject_id"]: r for r in csv_rows("patients")}
pats = list(ndjson("MimicPatient"))
fhir_ids = {}
for p in pats:
    for ident in p.get("identifier", []):
        if ident.get("system", "").endswith("/patient"):
            fhir_ids[ident["value"]] = p
print("FHIR patients:", len(pats), "| HIS patients:", len(his_patients),
      "| same subject_id:", len(set(fhir_ids) & set(his_patients)))

print("\nmeta keys across resource files:")
for name in ["MimicPatient", "MimicEncounter", "MimicCondition", "MimicObservationLabevents",
             "MimicMedicationRequest"]:
    keys, n = Counter(), 0
    for r in ndjson(name):
        n += 1
        keys.update(r.get("meta", {}).keys())
    print(f"  {name:28s} {n:7d} resources, meta keys: {dict(keys)}")

print(f"\n=== HIS patients row for {pick}")
print(" ", his_patients.get(pick))
print(f"=== HIS admissions for {pick}")
for r in csv_rows("admissions"):
    if r["subject_id"] == pick:
        print("  ", {k: r[k] for k in ["hadm_id", "admittime", "dischtime", "admission_type",
                                       "marital_status", "race", "language", "deathtime"]})
print(f"=== FHIR Patient for {pick}")
print(json.dumps(fhir_ids.get(pick), indent=1, ensure_ascii=False)[:2500])

fp = fhir_ids.get(pick)
if fp:
    ref = f"Patient/{fp['id']}"
    encs = [e for e in ndjson("MimicEncounter") if e.get("subject", {}).get("reference") == ref]
    print(f"\n=== FHIR Encounters for {pick}: {len(encs)}")
    if encs:
        print(json.dumps(encs[0], indent=1, ensure_ascii=False)[:1500])

print("\n=== Observation (labevents) code systems:")
systems = Counter()
sample = None
for o in ndjson("MimicObservationLabevents"):
    for c in o.get("code", {}).get("coding", []):
        systems[c.get("system")] += 1
    sample = sample or o
print(" ", systems.most_common(5))
print(json.dumps(sample, indent=1, ensure_ascii=False)[:1800])

print("\n=== Condition code systems:")
print(" ", Counter(c.get("system") for r in ndjson("MimicCondition")
                   for c in r.get("code", {}).get("coding", [])).most_common(5))
