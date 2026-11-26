"""The command line: every documented way to run the program. `run` starts no daemon for this case,
so each section runs the program itself.

  1 -h / --help                usage, exit 0
  2 unknown option             error, exit != 0, no IPC
  3 SWAYSOCK not set           error, exit != 0
  4 --once --dry-run           prints the exact commands of one pass, changes nothing
  5 --once                     runs them, then exits
  6 daemon --dry-run           prints a pass per event, changes nothing
  7 daemon without options     splits and cleans up, logs nothing
  8 daemon startup             the first open halves an already focused tile
  9 --config FILE              a valid file (on, off, comments, --config=FILE): runs as without it
 10 --config errors            missing file, no path, unknown key, bad value, line without `=`:
                               error naming the file and line, exit != 0, also without SWAYSOCK
 11 default config file        found in $XDG_CONFIG_HOME, else ~/.config; no file at all: defaults
 12 SWAY_AUTOTILE_<KEY>        overrides the file and the default; empty counts as unset; a bad value
                               or an unknown SWAY_AUTOTILE_* variable: error naming it, exit != 0
"""
import os
import subprocess
import sys
import tempfile
import time

from lib import PROGRAM, check, check_open, cmd, finish, load_program, parents, result, spawn, tree, wid


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

print("== 8 daemon started with a focused tile")
cmd("workspace 2")
spawn("existing-a")
spawn("existing-b")
cmd(f"[con_id={wid('existing-a')}] focus")
daemon = subprocess.Popen([sys.executable, "-B", PROGRAM])
try:
    time.sleep(1)
    before = tree()
    spawn("first")
    check_open(before, check("8 first open"), "first", "8 startup")
finally:
    daemon.terminate()
    daemon.wait(timeout=10)

tmp = tempfile.TemporaryDirectory()


def config_file(name, text):
    path = os.path.join(tmp.name, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return path


print("== 9 --config with a valid file")
for name, text in (("on", "open_at_workspace_end = on\n"),
                   ("off-comments", "# a comment\n\n   open_at_workspace_end=off  \n  # indented\n"),
                   ("empty", "")):
    path = config_file(name, text)
    for args in (("--config", path), (f"--config={path}",)):
        before = ws_shape()
        p = run("--once", "--dry-run", *args)
        result(p.returncode == 0 and not p.stderr and ws_shape() == before,
               f"9 {name}, {' '.join(args).replace(path, 'FILE')}: exit 0, tree unchanged "
               f"(rc {p.returncode}, err {p.stderr[-200:]!r})")
path = config_file("daemon", "open_at_workspace_end = off\n")
daemon = subprocess.Popen([sys.executable, "-B", PROGRAM, "--config", path], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True)
time.sleep(1)
result(daemon.poll() is None, "9 the daemon runs with --config FILE")
daemon.terminate()
out, err = daemon.communicate(timeout=10)
result(not err, f"9 daemon: nothing on stderr ({err[-200:]!r})")

print("== 10 --config errors")
no_sock = {k: v for k, v in os.environ.items() if k not in ("SWAYSOCK", "I3SOCK")}
missing = os.path.join(tmp.name, "missing")
cases = [("missing file", ("--config", missing), f"{missing}: No such file or directory"),
         ("missing file, --config=", (f"--config={missing}",), f"{missing}: No such file or directory"),
         ("directory", ("--config", tmp.name), f"{tmp.name}: Is a directory"),
         ("no path", ("--config",), "--config needs a path (see --help)")]
for name, text, problem in (
        ("unknown key", "# ok\nopen_at_workspace_end = on\nbogus = on\n", "3: unknown key 'bogus'"),
        ("bad value", "\nopen_at_workspace_end = yes\n", "2: open_at_workspace_end: expected on or off, got 'yes'"),
        ("capitalized value", "open_at_workspace_end = On\n", "1: open_at_workspace_end: expected on or off, got 'On'"),
        ("no value", "open_at_workspace_end =\n", "1: open_at_workspace_end: expected on or off, got ''"),
        ("line without =", "# ok\n\nopen_at_workspace_end on\n",
         "3: expected `key = value`, got 'open_at_workspace_end on'")):
    path = config_file(name.replace(" ", "-"), text)
    cases.append((name, ("--config", path), f"{path}:{problem}"))
for label, args, message in cases:
    for env, where in ((None, ""), (no_sock, ", no SWAYSOCK")):
        p = run("--once", "--dry-run", *args, env=env)
        result(p.returncode != 0 and p.stderr.strip() == f"sway-autotile: {message}" and not p.stdout,
               f"10 {label}{where}: error, exit {p.returncode}: {p.stderr.strip()!r}")

print("== 11 default config file")
for label, xdg, home in (("XDG_CONFIG_HOME", "xdg", "home-unused"), ("XDG_CONFIG_HOME empty", "", "home"),
                         ("XDG_CONFIG_HOME unset", None, "home")):
    env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
    env["HOME"] = os.path.join(tmp.name, home)
    if xdg is not None:
        env["XDG_CONFIG_HOME"] = os.path.join(tmp.name, xdg) if xdg else ""
    default = os.path.join(env.get("XDG_CONFIG_HOME") or os.path.join(env["HOME"], ".config"), "sway-autotile",
                           "config")
    config_file(default, "bogus = on\n")
    p = run("--once", "--dry-run", env=env)
    result(p.returncode != 0 and p.stderr.strip() == f"sway-autotile: {default}:1: unknown key 'bogus'",
           f"11 {label}: reads {os.path.relpath(default, tmp.name)} (rc {p.returncode}, {p.stderr.strip()!r})")
    config_file(default, "open_at_workspace_end = off\n")
    p = run("--once", "--dry-run", env=env)
    result(p.returncode == 0 and not p.stderr, f"11 {label}: a valid file, exit 0 ({p.stderr[-200:]!r})")
env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
env["HOME"] = os.path.join(tmp.name, "home-none")
for label, xdg in (("no file in XDG_CONFIG_HOME or ~/.config", os.path.join(tmp.name, "xdg-none")),
                   ("no file in ~/.config", None)):
    if xdg:
        env["XDG_CONFIG_HOME"] = xdg
    else:
        env.pop("XDG_CONFIG_HOME", None)
    before = ws_shape()
    p = run("--once", "--dry-run", env=env)
    result(p.returncode == 0 and not p.stderr and ws_shape() == before,
           f"11 {label}: defaults, exit 0 (rc {p.returncode}, err {p.stderr[-200:]!r})")
print("== 12 SWAY_AUTOTILE_<KEY> variables")
program = load_program()                     # load_options() reads os.environ: set it per check
clean = {k: v for k, v in os.environ.items() if not k.startswith("SWAY_AUTOTILE_")}
on, off = config_file("env-on", "open_at_workspace_end = on\n"), config_file("env-off", "open_at_workspace_end = off\n")
missing_default = {"XDG_CONFIG_HOME": os.path.join(tmp.name, "xdg-none")}
for label, path, env, want in (
        ("off overrides the file's on", on, {"SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END": "off"}, False),
        ("on overrides the file's off", off, {"SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END": "on"}, True),
        ("off overrides the default", None, {**missing_default, "SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END": "off"}, False),
        ("empty keeps the file's off", off, {"SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END": ""}, False),
        ("empty keeps the default", None, {**missing_default, "SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END": ""}, True),
        ("unset: the file's off", off, {}, False)):
    saved = dict(os.environ)
    os.environ.clear()
    os.environ.update(clean, **env)
    try:
        got = program.load_options(path)["open_at_workspace_end"]
    finally:
        os.environ.clear()
        os.environ.update(saved)
    result(got is want, f"12 {label}: open_at_workspace_end {got} (expected {want})")
for label, env in (("empty", {"SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END": ""}),
                   ("empty unknown", {"SWAY_AUTOTILE_BOGUS": ""}),
                   ("valid", {"SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END": "off"})):
    before = ws_shape()
    p = run("--once", "--dry-run", "--config", on, env={**clean, **env})
    result(p.returncode == 0 and not p.stderr and ws_shape() == before,
           f"12 {label} variable: exit 0, tree unchanged (rc {p.returncode}, err {p.stderr[-200:]!r})")
no_sock = {k: v for k, v in clean.items() if k not in ("SWAYSOCK", "I3SOCK")}
for label, env, message in (
        ("bad value", {"SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END": "yes"},
         "SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END: expected on or off, got 'yes'"),
        ("bad value with spaces", {"SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END": " on"},
         "SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END: expected on or off, got ' on'"),
        ("unknown variable", {"SWAY_AUTOTILE_BOGUS": "on"}, "unknown variable SWAY_AUTOTILE_BOGUS (see --help)"),
        ("lower-case name", {"SWAY_AUTOTILE_open_at_workspace_end": "on"},
         "unknown variable SWAY_AUTOTILE_open_at_workspace_end (see --help)")):
    for base, where in ((clean, ""), (no_sock, ", no SWAYSOCK")):
        p = run("--once", "--dry-run", "--config", on, env={**base, **env})
        result(p.returncode != 0 and p.stderr.strip() == f"sway-autotile: {message}" and not p.stdout,
               f"12 {label}{where}: error, exit {p.returncode}: {p.stderr.strip()!r}")
tmp.cleanup()

finish()
