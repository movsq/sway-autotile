"""Compare a run's geometry with the autotiling-rs baseline.

Usage: compare.py seq BASELINE.jsonl RUN.jsonl
       compare.py resize BASELINE.json RUN.json
Prints one line; exit 1 on any difference.
"""
import json
import sys

kind, base_path, run_path = sys.argv[1:4]
if kind == "seq":
    base = [json.loads(line) for line in open(base_path)]
    run = [json.loads(line) for line in open(run_path)]
    if [b["act"] for b in base] != [r["act"] for r in run]:
        print(f"FAIL {run_path}: different action sequence than the baseline (sequences.py changed?)")
        sys.exit(1)
    diff = [(b["step"], b["act"]) for b, r in zip(base, run) if b["geom"] != r["geom"]]
    opens = sum(b["act"].startswith("open") for b in base)
    if diff:
        print(f"FAIL {run_path}: geometry differs from autotiling-rs at {diff[:3]}")
        sys.exit(1)
    print(f"PASS {run_path}: {len(run)} steps, {opens} windows opened, geometry = autotiling-rs at every step")
else:
    base, run = json.load(open(base_path)), json.load(open(run_path))
    diff = [k for k in base if base[k] != run.get(k)]
    if diff:
        print(f"FAIL {run_path}: differs from autotiling-rs in {diff}: {[(base[k], run.get(k)) for k in diff]}")
        sys.exit(1)
    print(f"PASS {run_path}: H and V cases = autotiling-rs")
