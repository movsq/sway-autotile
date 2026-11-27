"""The command line: every documented way to run the program. `run` starts no daemon for this case,
so each section runs the program itself.

  1 -h / --help                usage, exit 0
  2 unknown option             error, exit 2, no IPC
  3 SWAYSOCK not set           error, exit != 0
  4 --once --dry-run           prints the exact commands of one pass, changes nothing
  5 --once                     runs them, then exits
  6 daemon --dry-run           prints a pass per event, changes nothing
  7 daemon without options     splits and cleans up, logs nothing
  8 daemon startup             the first open halves an already focused tile
  9 --config FILE              a valid file (end, half, sway, comments, --config=FILE): runs as without it
 10 config file warnings       missing file, directory, bad UTF-8, unreadable, unknown key, bad value,
                               line without `=`: a warning naming the file and line, the line or file
                               skipped, exit 0 (--once, --dry-run, daemon); a FIFO whose writer stays
                               idle: a warning after 1 s, no hang; --config <(…) is read in full
 11 default config file        found in $XDG_CONFIG_HOME, else ~/.config; one that can't be read, also
                               below a directory that can't be searched: a warning; no file at all:
                               defaults, silent
 12 SWAY_AUTOTILE_<KEY>        overrides the file and the default; empty counts as unset; a bad value
                               or an unknown SWAY_AUTOTILE_* variable: a warning naming it, skipped
 13 --config argument errors   no path, a path starting with -, given twice: error, exit 2, no IPC
                               (also `--config --dry-run --once --config=/dev/null`); --config=-PATH works
 14 --check-config             the effective options on stdout, warnings on stderr, exit 1 if any;
                               with --config; any other option: usage error (exit 2); never connects to sway
 15 isolation                  tests/run removes every SWAY_AUTOTILE_* name from this environment
"""
import os
import subprocess
import sys
import tempfile
import time

from lib import PROGRAM, check, check_open, cmd, finish, parents, result, spawn, tree, wid


def run(*args, env=None, cwd=None):
    return subprocess.run([sys.executable, "-B", PROGRAM, *args], capture_output=True, text=True, env=env,
                          cwd=cwd, timeout=20)


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
result(p.returncode == 2 and "unknown option(s): --bogus" in p.stderr and not p.stdout,
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
for name, text in (("end", "workspace_open = end\n"), ("half", "workspace_open = half\n"),
                   ("sway-comments", "# a comment\n\n   workspace_open=sway  \n  # indented\n"),
                   ("empty", "")):
    path = config_file(name, text)
    for args in (("--config", path), (f"--config={path}",)):
        before = ws_shape()
        p = run("--once", "--dry-run", *args)
        result(p.returncode == 0 and not p.stderr and ws_shape() == before,
               f"9 {name}, {' '.join(args).replace(path, 'FILE')}: exit 0, tree unchanged "
               f"(rc {p.returncode}, err {p.stderr[-200:]!r})")
path = config_file("daemon", "workspace_open = half\n")
daemon = subprocess.Popen([sys.executable, "-B", PROGRAM, "--config", path], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True)
time.sleep(1)
result(daemon.poll() is None, "9 the daemon runs with --config FILE")
daemon.terminate()
out, err = daemon.communicate(timeout=10)
result(not err, f"9 daemon: nothing on stderr ({err[-200:]!r})")


no_sock = {k: v for k, v in os.environ.items() if k not in ("SWAYSOCK", "I3SOCK")}
no_default = os.path.join(tmp.name, "xdg-none")  # an XDG_CONFIG_HOME without a config file
VAR = "SWAY_AUTOTILE_WORKSPACE_OPEN"
BAD = "expected end, half or sway, got"


def warned(*warnings):
    """What the program prints on stderr for these warnings."""
    return "".join(f"sway-autotile: warning: {w}\n" for w in warnings)


def check_config(*args, env=None):
    """--check-config without SWAYSOCK and without a default file (unless `env` sets one)."""
    return run("--check-config", *args, env={**no_sock, "XDG_CONFIG_HOME": no_default, **(env or {})})


print("== 10 config file warnings")
missing = os.path.join(tmp.name, "missing")
bad_utf8 = os.path.join(tmp.name, "bad-utf8")
with open(bad_utf8, "wb") as f:
    f.write(b"workspace_open = half\n\xff\n")
try:
    with open(bad_utf8, encoding="utf-8") as f:
        f.read()
except UnicodeDecodeError as e:
    utf8_error = str(e)
cases = [("missing file", ("--config", missing), {}, [f"{missing}: No such file or directory"], "end"),
         ("missing file, --config=", (f"--config={missing}",), {}, [f"{missing}: No such file or directory"], "end"),
         ("missing file, valid variable", ("--config", missing), {VAR: "sway"},
          [f"{missing}: No such file or directory"], "sway"),
         ("directory", ("--config", tmp.name), {}, [f"{tmp.name}: Is a directory"], "end"),
         ("bad UTF-8", ("--config", bad_utf8), {}, [f"{bad_utf8}: {utf8_error}"], "end")]
unreadable = config_file("unreadable", "workspace_open = half\n")
os.chmod(unreadable, 0)
if os.access(unreadable, os.R_OK):
    print("   (running as root: no unreadable file)")
else:
    cases.append(("unreadable", ("--config", unreadable), {}, [f"{unreadable}: Permission denied"], "end"))
for name, text, env, problems, want in (
        ("unknown key", "# ok\nworkspace_open = half\nbogus = on\n", {}, ["3: unknown key 'bogus'"], "half"),
        ("bad value", "\nworkspace_open = on\n", {}, [f"2: workspace_open: {BAD} 'on'"], "end"),
        ("bad value, valid variable", "workspace_open = on\n", {VAR: "half"},
         [f"1: workspace_open: {BAD} 'on'"], "half"),
        ("bad value after a valid one", "workspace_open = sway\nworkspace_open = on\n", {},
         [f"2: workspace_open: {BAD} 'on'"], "sway"),
        ("capitalized value", "workspace_open = Half\n", {}, [f"1: workspace_open: {BAD} 'Half'"], "end"),
        ("no value", "workspace_open =\n", {}, [f"1: workspace_open: {BAD} ''"], "end"),
        ("line without =", "# ok\n\nworkspace_open half\n", {},
         ["3: expected `key = value`, got 'workspace_open half'"], "end"),
        ("three problems", "bogus = 1\nworkspace_open = half\nworkspace_open\nworkspace_open = off\n", {},
         ["1: unknown key 'bogus'", "3: expected `key = value`, got 'workspace_open'",
          f"4: workspace_open: {BAD} 'off'"], "half")):
    path = config_file(name.replace(",", "").replace(" ", "-"), text)
    cases.append((name, ("--config", path), env, [f"{path}:{w}" for w in problems], want))
for label, args, env, warnings, want in cases:
    p = check_config(*args, env=env)
    result(p.returncode == 1 and p.stderr == warned(*warnings) and p.stdout == f"workspace_open = {want}\n",
           f"10 {label}: --check-config exit {p.returncode}, {p.stdout.strip()!r} (expected {want}), "
           f"err {p.stderr.strip()!r}")
    before = ws_shape()
    p = run("--once", "--dry-run", *args, env={**os.environ, **env})
    result(p.returncode == 0 and p.stderr == warned(*warnings) and ws_shape() == before,
           f"10 {label}: --once --dry-run warns, exit 0, tree unchanged (rc {p.returncode}, err {p.stderr[-200:]!r})")
os.chmod(unreadable, 0o600)
fifo = os.path.join(tmp.name, "fifo")
os.mkfifo(fifo)
writer = os.open(fifo, os.O_RDWR)  # a writer that never writes or closes: a blocking read would wait for good
try:
    for label, args in (("--check-config", ("--check-config",)), ("--once --dry-run", ("--once", "--dry-run"))):
        start = time.monotonic()
        p = run(*args, "--config", fifo, env={**os.environ, "XDG_CONFIG_HOME": no_default})
        took = time.monotonic() - start
        result(p.returncode == (1 if args[0] == "--check-config" else 0) and took < 5
               and p.stderr == warned(f"{fifo}: no end of input within 1 s (a pipe or terminal?)"),
               f"10 a FIFO with an idle writer, {label}: warns after {took:.1f} s, exit {p.returncode} "
               f"(err {p.stderr.strip()!r})")
finally:
    os.close(writer)
# --config <(…): a pipe whose text comes late is read in full
p = subprocess.run(["bash", "-c", f'exec "$0" -B "$1" --check-config --config <(sleep 0.3; echo "workspace_open = half")',
                    sys.executable, PROGRAM], capture_output=True, text=True, timeout=20,
                   env={**no_sock, "XDG_CONFIG_HOME": no_default})
result(p.returncode == 0 and not p.stderr and p.stdout == "workspace_open = half\n",
       f"10 --config <(sleep 0.3; echo …): reads the pipe (rc {p.returncode}, out {p.stdout!r}, err {p.stderr.strip()!r})")
bad = config_file("bad-daemon", "workspace_open = on\n")
warning = warned(f"{bad}:1: workspace_open: {BAD} 'on'")
p = run("--once", "--config", bad)
result(p.returncode == 0 and p.stderr == warning and not p.stdout,
       f"10 --once with a bad value: warns, exit 0 (rc {p.returncode}, err {p.stderr[-200:]!r})")
cmd("workspace 3")
spawn("warned-a")
daemon = subprocess.Popen([sys.executable, "-B", PROGRAM, "--config", bad], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True)
try:
    time.sleep(1)
    before = tree()
    spawn("warned-b")
    check_open(before, check("10 daemon with a bad value: open"), "warned-b", "10 daemon with a bad value")
    result(daemon.poll() is None, "10 the daemon runs on with a bad value")
finally:
    daemon.terminate()
    out, err = daemon.communicate(timeout=10)
result(err == warning and not out, f"10 daemon: the warning on stderr, nothing else ({err[-200:]!r})")

print("== 11 default config file")
for label, xdg, home in (("XDG_CONFIG_HOME", "xdg", "home-unused"), ("XDG_CONFIG_HOME empty", "", "home"),
                         ("XDG_CONFIG_HOME unset", None, "home")):
    env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
    env["HOME"] = os.path.join(tmp.name, home)
    if xdg is not None:
        env["XDG_CONFIG_HOME"] = os.path.join(tmp.name, xdg) if xdg else ""
    default = os.path.join(env.get("XDG_CONFIG_HOME") or os.path.join(env["HOME"], ".config"), "sway-autotile",
                           "config")
    where = os.path.relpath(default, tmp.name)
    config_file(default, "workspace_open = sway\n")
    p = run("--check-config", env={k: v for k, v in env.items() if k not in ("SWAYSOCK", "I3SOCK")})
    result(p.returncode == 0 and not p.stderr and p.stdout == "workspace_open = sway\n",
           f"11 {label}: reads {where} (rc {p.returncode}, out {p.stdout!r}, err {p.stderr.strip()!r})")
    p = run("--once", "--dry-run", env=env)
    result(p.returncode == 0 and not p.stderr, f"11 {label}: a valid file, exit 0 ({p.stderr[-200:]!r})")
    config_file(default, "bogus = on\n")
    p = run("--once", "--dry-run", env=env)
    result(p.returncode == 0 and p.stderr == warned(f"{default}:1: unknown key 'bogus'"),
           f"11 {label}: a bad file warns, exit 0 (rc {p.returncode}, {p.stderr.strip()!r})")
xdg_dir = os.path.join(tmp.name, "xdg-dir")
default = os.path.join(xdg_dir, "sway-autotile", "config")
os.makedirs(default)
for label, env, want in (("a directory", {}, "end"), ("a directory, valid variable", {VAR: "half"}, "half")):
    p = check_config(env={"XDG_CONFIG_HOME": xdg_dir, **env})
    result(p.returncode == 1 and p.stderr == warned(f"{default}: Is a directory")
           and p.stdout == f"workspace_open = {want}\n",
           f"11 {label} at the default path: warns, {want} (rc {p.returncode}, out {p.stdout!r}, "
           f"err {p.stderr.strip()!r})")
locked = os.path.join(tmp.name, "xdg-locked")  # the default file below a directory that can't be searched
config_file(os.path.join(locked, "sway-autotile", "config"), "workspace_open = half\n")
os.chmod(locked, 0)
try:
    if os.access(os.path.join(locked, "sway-autotile"), os.F_OK):
        print("   (running as root: no unsearchable directory)")
    else:
        p = check_config(env={"XDG_CONFIG_HOME": locked})
        result(p.returncode == 1 and p.stdout == "workspace_open = end\n"
               and p.stderr == warned(f"{locked}/sway-autotile/config: Permission denied"),
               f"11 below an unsearchable XDG_CONFIG_HOME: warns, not taken for no file (rc {p.returncode}, "
               f"out {p.stdout!r}, err {p.stderr.strip()!r})")
finally:
    os.chmod(locked, 0o700)
env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
env["HOME"] = os.path.join(tmp.name, "home-none")
for label, xdg in (("no file in XDG_CONFIG_HOME or ~/.config", no_default), ("no file in ~/.config", None)):
    if xdg:
        env["XDG_CONFIG_HOME"] = xdg
    else:
        env.pop("XDG_CONFIG_HOME", None)
    before = ws_shape()
    p = run("--once", "--dry-run", env=env)
    result(p.returncode == 0 and not p.stderr and ws_shape() == before,
           f"11 {label}: defaults, exit 0 (rc {p.returncode}, err {p.stderr[-200:]!r})")
    p = run("--check-config", env={k: v for k, v in env.items() if k not in ("SWAYSOCK", "I3SOCK")})
    result(p.returncode == 0 and not p.stderr and p.stdout == "workspace_open = end\n",
           f"11 {label}: --check-config shows the default (rc {p.returncode}, out {p.stdout!r})")

print("== 12 SWAY_AUTOTILE_<KEY> variables")
clean = {k: v for k, v in os.environ.items() if not k.startswith("SWAY_AUTOTILE_")}
half, sway = config_file("env-half", "workspace_open = half\n"), config_file("env-sway", "workspace_open = sway\n")
for label, path, env, want in (
        ("sway overrides the file's half", half, {VAR: "sway"}, "sway"),
        ("half overrides the file's sway", sway, {VAR: "half"}, "half"),
        ("sway overrides the default", None, {VAR: "sway"}, "sway"),
        ("empty keeps the file's sway", sway, {VAR: ""}, "sway"),
        ("empty keeps the default", None, {VAR: ""}, "end"),
        ("empty unknown variable: nothing", sway, {"SWAY_AUTOTILE_BOGUS": ""}, "sway"),
        ("unset: the file's sway", sway, {}, "sway")):
    p = check_config(*(("--config", path) if path else ()), env=env)
    result(p.returncode == 0 and not p.stderr and p.stdout == f"workspace_open = {want}\n",
           f"12 {label}: {p.stdout.strip()!r} (expected {want}, rc {p.returncode}, err {p.stderr.strip()!r})")
for label, env in (("empty", {VAR: ""}),
                   ("empty unknown", {"SWAY_AUTOTILE_BOGUS": ""}),
                   ("valid", {VAR: "sway"})):
    before = ws_shape()
    p = run("--once", "--dry-run", "--config", half, env={**clean, **env})
    result(p.returncode == 0 and not p.stderr and ws_shape() == before,
           f"12 {label} variable: exit 0, tree unchanged (rc {p.returncode}, err {p.stderr[-200:]!r})")
for label, path, env, warning, want in (
        ("bad value", half, {VAR: "off"}, f"{VAR}: {BAD} 'off'", "half"),
        ("bad value with spaces", half, {VAR: " half"}, f"{VAR}: {BAD} ' half'", "half"),
        ("bad value, no file", None, {VAR: "off"}, f"{VAR}: {BAD} 'off'", "end"),
        ("unknown variable", half, {"SWAY_AUTOTILE_BOGUS": "on"},
         "unknown variable SWAY_AUTOTILE_BOGUS (see --help)", "half"),
        ("unknown variable beside a valid one", half, {"SWAY_AUTOTILE_BOGUS": "on", VAR: "sway"},
         "unknown variable SWAY_AUTOTILE_BOGUS (see --help)", "sway"),
        ("lower-case name", half, {"SWAY_AUTOTILE_workspace_open": "sway"},
         "unknown variable SWAY_AUTOTILE_workspace_open (see --help)", "half"),
        ("name that is no shell identifier", half, {"SWAY_AUTOTILE_BAD-NAME": "on"},
         "unknown variable SWAY_AUTOTILE_BAD-NAME (see --help)", "half")):
    args = ("--config", path) if path else ()
    p = check_config(*args, env=env)
    result(p.returncode == 1 and p.stderr == warned(warning) and p.stdout == f"workspace_open = {want}\n",
           f"12 {label}: --check-config exit {p.returncode}, {p.stdout.strip()!r} (expected {want}), "
           f"err {p.stderr.strip()!r}")
    before = ws_shape()
    p = run("--once", "--dry-run", *args, env={**clean, "XDG_CONFIG_HOME": no_default, **env})
    result(p.returncode == 0 and p.stderr == warned(warning) and ws_shape() == before,
           f"12 {label}: --once --dry-run warns, exit 0, tree unchanged (rc {p.returncode}, "
           f"err {p.stderr[-200:]!r})")

print("== 13 --config argument errors")
cmd("workspace 4")
spawn("c")
spawn("d")                                   # no daemon: splith[c, d]
cmd(f"[con_id={wid('c')}] split v")          # a leftover wrapper: a live pass would change the tree
cmd(f"[con_id={wid('d')}] focus")
p = run("--once", "--dry-run")
result(p.returncode == 0 and p.stdout.strip(), f"13 a pass would change this tree ({p.stdout.strip()!r})")
no_path = "--config needs a path (see --help)"
twice = "--config given more than once (see --help)"
dash = "(use --config=PATH for a path starting with -)"
for args, message in (
        (("--config",), no_path),
        (("--once", "--config"), no_path),
        (("--config", "--dry-run", "--once", "--config=/dev/null"), f"--config needs a path, got '--dry-run' {dash}"),
        (("--config", "-x", "--once"), f"--config needs a path, got '-x' {dash}"),
        (("--config", "/dev/null", "--config", "/dev/null", "--once"), twice),
        (("--config=/dev/null", "--config=/dev/null", "--once"), twice),
        (("--config", "/dev/null", "--once", "--config=/dev/null"), twice),
        (("--config=", "--config", "/dev/null", "--once"), twice)):
    for env, where in ((None, ""), (no_sock, ", no SWAYSOCK")):
        before = ws_shape()
        p = run(*args, env=env)
        result(p.returncode == 2 and p.stderr == f"sway-autotile: {message}\n" and not p.stdout
               and ws_shape() == before,
               f"13 {' '.join(args)}{where}: error, tree unchanged, exit {p.returncode}: {p.stderr.strip()!r}")
config_file("-dash", "workspace_open = sway\n")
p = run("--check-config", "--config=-dash", env={**no_sock, "XDG_CONFIG_HOME": no_default}, cwd=tmp.name)
result(p.returncode == 0 and not p.stderr and p.stdout == "workspace_open = sway\n",
       f"13 --config=-dash reads ./-dash (rc {p.returncode}, out {p.stdout!r}, err {p.stderr.strip()!r})")

print("== 14 --check-config")
for args in ((), ("--config", half), (f"--config={half}",)):
    want = "half" if args else "end"
    for label, env in (("no SWAYSOCK", {}), ("SWAYSOCK that doesn't exist", {"SWAYSOCK": "/nonexistent/sock"})):
        p = check_config(*args, env=env)
        result(p.returncode == 0 and not p.stderr and p.stdout == f"workspace_open = {want}\n",
               f"14 --check-config {' '.join(args).replace(half, 'FILE')}, {label}: {p.stdout.strip()!r}, "
               f"exit {p.returncode} (err {p.stderr.strip()!r})")
p = run("--config", half, "--check-config", env={**os.environ, "XDG_CONFIG_HOME": no_default})
result(p.returncode == 0 and not p.stderr and p.stdout == "workspace_open = half\n",
       f"14 --config FILE --check-config, with the case's SWAYSOCK: {p.stdout.strip()!r}, exit {p.returncode}")
for others in (("--once",), ("--dry-run",), ("--debug",), ("--once", "--dry-run"), ("--config", half, "--once")):
    named = " ".join(sorted(o for o in others if o.startswith("--") and o != "--config"))
    message = f"sway-autotile: --check-config combines only with --config, got {named} (see --help)\n"
    for env, where in ((None, ""), (no_sock, ", no SWAYSOCK")):
        before = ws_shape()
        p = run("--check-config", *others, env=env)
        result(p.returncode == 2 and p.stderr == message and not p.stdout and ws_shape() == before,
               f"14 --check-config {' '.join(others).replace(half, 'FILE')}{where}: usage error, "
               f"exit {p.returncode}: {p.stderr.strip()!r}")
p = run("--check-config", "--bogus", env=no_sock)
result(p.returncode == 2 and "unknown option(s): --bogus" in p.stderr and not p.stdout,
       f"14 --check-config --bogus: unknown option, exit {p.returncode}: {p.stderr.strip()!r}")

print("== 15 isolation")
leaked = sorted(k for k in os.environ if k.startswith("SWAY_AUTOTILE_"))
result(not leaked, f"15 no SWAY_AUTOTILE_* variable reaches the tests (found {leaked})")
p = check_config()
result(p.returncode == 0 and not p.stderr, f"15 the program sees none either (err {p.stderr.strip()!r})")
tmp.cleanup()

finish()
