"""The command line: every documented way to run the program. `run` starts no daemon for this case,
so each section runs the program itself.

  1 -h / --help                usage, exit 0
  2 unknown option             error, exit != 0, no IPC
  3 SWAYSOCK not set           error, exit != 0
  4 --once --dry-run           prints the exact commands of one pass, changes nothing
  5 --once                     runs them, then exits
  6 daemon --dry-run           prints a pass per event, changes nothing
  7 daemon without options     splits and cleans up, logs nothing
"""
import os
import subprocess
import sys
import time

from lib import PROGRAM, check, cmd, finish, parents, result, spawn, tree, wid


def run(*args, env=None):
    return subprocess.run([sys.executable, "-B", PROGRAM, *args], capture_output=True, text=True, env=env,
                          timeout=20)


def shape(node):
    """The tree without sizes: layouts and window titles, to see whether anything changed."""
    if not node["nodes"]:
        return node["name"]
    return [node["layout"], [shape(c) for c in node["nodes"]]]


def ws_shape():
    return [shape(ws) for output in tree()["nodes"] for ws in output["nodes"] if not ws["name"].startswith("__")]


print("== 1 --help")
for flag in ("-h", "--help"):
    p = run(flag)
    result(p.returncode == 0 and p.stdout.startswith("Usage: sway-autotile") and "--dry-run" in p.stdout,
           f"1 {flag}: usage on stdout, exit 0 (rc {p.returncode})")

print("== 2 unknown option")
p = run("--bogus")
result(p.returncode != 0 and "unknown option(s): --bogus" in p.stderr and not p.stdout,
       f"2 --bogus: error, exit {p.returncode}: {p.stderr.strip()!r}")

print("== 3 SWAYSOCK not set")
env = {k: v for k, v in os.environ.items() if k not in ("SWAYSOCK", "I3SOCK")}
p = run("--once", "--dry-run", env=env)
result(p.returncode != 0 and "SWAYSOCK is not set" in p.stderr,
       f"3 no SWAYSOCK: error, exit {p.returncode}: {p.stderr.strip()!r}")

# A leftover wrapper around a, and b focused with a sibling: one pass should unwrap a and split b.
spawn("a")
spawn("b")                                   # no daemon: splith[a, b]
cmd(f"[con_id={wid('a')}] split v")          # wraps a in a one-child splitv
cmd(f"[con_id={wid('b')}] focus")
a, b = wid("a"), wid("b")
expected = f"[con_id={a}] split none; [con_id={b}] splitv\n"

print("== 4 --once --dry-run")
before = ws_shape()
p = run("--once", "--dry-run")
result(p.returncode == 0 and not p.stderr, f"4 exit 0 (rc {p.returncode}, stderr {p.stderr[-200:]!r})")
result(p.stdout == expected, f"4 prints {expected.strip()!r} (got {p.stdout!r})")
result(ws_shape() == before, "4 the tree is unchanged")

print("== 5 --once")
p = run("--once")
result(p.returncode == 0 and not p.stdout and not p.stderr,
       f"5 exit 0, quiet (rc {p.returncode}, out {p.stdout!r}, err {p.stderr[-200:]!r})")
t = check("5 after --once")
par = parents(t)
result(par[a]["type"] == "workspace", "5 a's wrapper is gone")
result(par[b]["type"] == "con" and par[b]["layout"] == "splitv" and len(par[b]["nodes"]) == 1,
       "5 b has its splitv wrapper")

print("== 6 daemon --dry-run")
daemon = subprocess.Popen([sys.executable, "-B", PROGRAM, "--dry-run"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True)
time.sleep(1)
before = ws_shape()
cmd(f"[con_id={a}] focus", settle=0.8)       # b's wrapper is now a leftover, a wants a split
after = ws_shape()
daemon.terminate()
out, err = daemon.communicate(timeout=10)
expected = f"[con_id={b}] split none; [con_id={a}] splitv\n"
result(out == expected, f"6 prints {expected.strip()!r} for the focus event (got {out!r})")
result(after == before, "6 the tree is unchanged")
result(not err, f"6 nothing on stderr ({err[-200:]!r})")

print("== 7 daemon without options")
daemon = subprocess.Popen([sys.executable, "-B", PROGRAM], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True)
time.sleep(1)
cmd(f"[con_id={b}] focus", settle=0.8)       # a has focus already: focus b, then a, for two focus events
cmd(f"[con_id={a}] focus", settle=0.8)
t = check("7 after focusing b, then a")
par = parents(t)
result(par[b]["type"] == "workspace" and par[a]["type"] == "con" and par[a]["layout"] == "splitv",
       "7 b unwrapped, a wrapped")
result(daemon.poll() is None, "7 the daemon is still running")
daemon.terminate()
out, err = daemon.communicate(timeout=10)
result(not out and not err, f"7 logs nothing (out {out!r}, err {err[-200:]!r})")

finish()
