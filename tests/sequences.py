"""Seeded random open/focus/close sequence; writes every window's geometry after each step.

Usage: sequences.py SEED OUT [--check]
The sequence for a seed must never change: baseline/seq-SEED.jsonl was recorded with autotiling-rs
alone, and `run` compares the autotiler under test against it step by step.
"""
import json
import random
import sys

from lib import check, cmd, finish, geom_by_title, spawn, tree, wid

# seed: (steps, probability boundary for focus vs close)
SEEDS = {1: (30, 0.85), 2: (30, 0.85), 3: (30, 0.85),
         4: (35, 0.7), 5: (35, 0.7), 6: (35, 0.7), 7: (35, 0.7), 8: (35, 0.7), 9: (35, 0.7)}

seed, out = int(sys.argv[1]), sys.argv[2]
invariant = "--check" in sys.argv[3:]
steps, focus_p = SEEDS[seed]
rng = random.Random(seed)
opened, alive = 0, []
with open(out, "w") as log:
    for step in range(steps):
        r = rng.random()
        if not alive or (r < 0.4 and len(alive) < 9):
            opened += 1
            title = f"w{opened}"
            spawn(title, settle=0.7)
            alive.append(title)
            act = f"open {title}"
        elif r < focus_p:
            title = rng.choice(alive)
            cmd(f"[con_id={wid(title)}] focus", settle=0.5)
            act = f"focus {title}"
        else:
            title = rng.choice(alive)
            cmd(f"[con_id={wid(title)}] kill", settle=0.7)
            alive.remove(title)
            act = f"close {title}"
        t = check(f"seed {seed} step {step} {act}") if invariant else tree()
        log.write(json.dumps({"step": step, "act": act, "geom": geom_by_title(t)}) + "\n")
finish()
