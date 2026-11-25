# sway-autotile

Autotiling for [sway](https://swaywm.org) that cleans up after itself. New windows split the focused one
along its longer side, so windows form a spiral. The splits leave invisible one-window containers behind,
and sway-autotile removes them once you move on.

It's one Python file that uses only the standard library. It reacts to sway's IPC events instead of polling.

## Why

Autotilers such as [autotiling-rs](https://github.com/ammgws/autotiling-rs) pick the direction of the
next window by running `split v` or `split h` on the focused window. sway does that by wrapping the window
in a new container with just that window inside. If no window opens there, the wrapper stays. You can't
see it, but `layout tabbed` then turns it into a tab group with a single tab, and `move` and `resize`
work on a level of the tree you didn't know was there. Closing windows leaves the same kind of
one-window containers behind, sometimes nested.

sway-autotile places windows exactly like autotiling-rs, and its tests check that step by step. It removes
those containers as soon as they stop doing anything.

## What it does

- Splits the focused window along its longer side, `splitv` if it's taller than wide, else `splith`.
  The rules are the same as in autotiling-rs: no splits for floating or fullscreen windows, inside tabbed
  or stacked containers, or when the parent already has that layout.
- Removes one-window split containers with `split none` after every focus change, close, move or
  floating toggle. It keeps:
  - the focused window's own container, which decides where the next window goes;
  - tabbed and stacked containers (a tab group with one tab stays a tab group);
  - containers that are marked or focused.
- If it removed the container of a window whose longer side matches its parent's layout, it splits that
  window again on its next focus. The next window then still halves it instead of sharing the parent.
- Does both in one process, one event at a time, so a cleanup can't undo a split made a moment earlier.

Here `two` was left inside its own `splitv` container and `one` has focus:

```
workspace splith
  one   (focused)   [con_id=5]
  splitv   [con_id=8]
    two   [con_id=6]
  three   [con_id=7]
```

```console
$ sway-autotile --once --dry-run
[con_id=6] split none; [con_id=5] splitv
```

`split none` removes the container around `two`. `one` is taller than wide, so `splitv` prepares it and the
next window opens below it.

## Requirements

- sway (tested with 1.12)
- Python 3, standard library only (tested with 3.14)

## Install

```bash
git clone https://github.com/movsq/sway-autotile.git
install -Dm755 sway-autotile/sway-autotile ~/.local/bin/sway-autotile
```

Add it to your sway config:

```
exec ~/.local/bin/sway-autotile
```

Remove any other autotiler, such as `autotiling` or `autotiling-rs`. Two of them would split the same windows.

To start it without logging out:

```bash
swaymsg exec ~/.local/bin/sway-autotile
```

`swaymsg reload` doesn't start it again or stop it, because sway only runs `exec` lines at startup.

## Usage

Without options it runs as a daemon, started from the sway config as above. It exits when sway does.

| Option | What it does |
| --- | --- |
| `--once` | one pass over the current tree, then exit |
| `--dry-run` | print the sway commands instead of running them |
| `--debug` | log every command it sends to stderr |

`--once --dry-run` only reads the tree, so it's safe to run in your session to see what the daemon would do.
It needs `SWAYSOCK`. sway sets it for everything it starts, your terminal inside sway included.

## Tests

```bash
tests/run              # everything, about 4.5 minutes
tests/run scenarios    # invariants in normal use: no leftover containers, no event loops, tab groups intact
tests/run sequences    # 9 seeded open/focus/close sequences; window geometry must match the baseline at every step
tests/run resize       # the case where cleaning up could change where windows open
```

Each case starts its own headless, software-rendered sway, so nothing happens in your session. The tests
need sway, python3 and kitty. Another terminal with a `--title` option works through `AUTOTILE_TEST_TERMINAL`.
`SEEDS="1 2" tests/run sequences` runs a subset, and `KEEP=1` keeps the output directory.

`tests/baseline/` holds the geometry autotiling-rs produces for the same sequences. `tests/run baseline`
records it again, which needs `autotiling-rs`.

## Development

<!-- TODO: say whether you accept issues / pull requests -->

Changes to `sway-autotile` should pass `tests/run`. The design constraints in [AGENTS.md](AGENTS.md)
explain the non-obvious parts: why `split none` is only sent for whole runs of split containers, why
windows are split again, why it's one process.

## Acknowledgements

The split rules come from [autotiling-rs](https://github.com/ammgws/autotiling-rs) (MIT), which is also
the reference for window placement in the tests.

## License

MIT. See [LICENSE](LICENSE).
