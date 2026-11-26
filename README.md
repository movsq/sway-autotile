# sway-autotile

Autotiling for [sway](https://swaywm.org) that also removes the invisible one-window containers its
splits leave behind. New windows split the focused one along its longer side, so windows form a spiral,
and each leftover container is removed once you move on.

It is one Python file that uses only the standard library and reacts to sway's IPC events.

## Why

Autotilers such as [autotiling-rs](https://github.com/ammgws/autotiling-rs) leave one-window containers
in the tree. They pick the direction of the next window by running `split v` or `split h` on the focused
window, and sway does that by wrapping the window in a new container with just that window inside. If
no window opens there, the wrapper stays. You can't see it, but `layout tabbed` then turns it into a tab
group with a single tab, and `move` and `resize` work on a level of the tree you didn't know was there.
Closing windows leaves the same kind of one-window containers behind, sometimes nested.

sway-autotile removes those containers once focus moves on or their windows close, and a new window
takes half of the focused one, also where autotiling-rs would give it a smaller share.

## What it does

- Splits the focused tile along its longer side so the next window takes half of it. Floating,
  fullscreen, tabbed, and stacked windows keep sway's own layout behavior.
- Prepares the focused tile at startup and after focus, close, and floating changes. When a window
  opens, it checks the split direction again in case the focused tile was resized.
- Moves the tile on the first press of a move key. sway's directional `move` of a prepared tile only
  takes it out of its split, so the tile would need a second press to move. When a key binding ran
  the move, sway-autotile sends the same move again and then prepares the tile. A `move` from
  `swaymsg` or a script sends no binding event, so there the first command only takes the tile out of
  its split. Dragging a tile with the mouse works as in plain sway.
- Changes the focus on the first press of a `focus parent` or `focus child` key. The focused window's
  container looks exactly like the window, so a press that stops there would show no change; when a
  key binding ran the command, sway-autotile moves the focus on past it, one level per press, also
  when you press the key several times quickly. As with `move`, `swaymsg focus parent` keeps sway's
  behavior. When you come back to a workspace and sway gives the focus to a container that a key press
  went past, the window inside gets it, so a new window still halves that window.
- Opens a window at the end of the workspace when a focus key selected the whole workspace. sway
  puts it right after the window focused last, so with the left one of two halves it would open
  between them; this way it lands to the right of all of them, whichever window you started from.
  `open_at_workspace_end = off` in the [config file](#config-file) keeps sway's placement.
- Removes one-window split containers with `split none` after every focus change, close, move or
  floating toggle. It keeps:
  - the focused window's own container, which decides where the next window goes;
  - tabbed and stacked containers, so a tab group with one tab stays a tab group;
  - containers that are marked or focused.
- Does the splits and the cleanup in one process, one event at a time, so a cleanup can't undo a
  split made a moment earlier.

Example: a sway tree where `two` was left inside its own `splitv` container and `one` has focus.

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

`split none` removes the container around `two`, and `splitv` prepares `one`, which is taller than wide,
so the next window opens below it.

## Requirements

- sway, tested with 1.12
- Python 3, standard library only, tested with 3.14

## Install

Copy the script into your `PATH`:

```bash
git clone https://github.com/movsq/sway-autotile.git
install -Dm755 sway-autotile/sway-autotile ~/.local/bin/sway-autotile
```

Or, on Arch Linux, build a package from the checkout with the `PKGBUILD` in the repository. It installs
to `/usr/bin/sway-autotile`:

```bash
cd sway-autotile
makepkg -si
```

## Configuration

Remove any other autotiler, such as `autotiling` or `autotiling-rs`, because two autotilers would split
the same windows. Then add this line to your sway config, or `exec sway-autotile` if you installed the
package:

```
exec ~/.local/bin/sway-autotile
```

To start it without logging out, run the command for your installation.

```bash
swaymsg exec ~/.local/bin/sway-autotile   # script installed manually
swaymsg exec sway-autotile               # Arch package
```

`swaymsg reload` neither starts it again nor stops it, because sway runs `exec` lines only at startup.

## Usage

Without options it runs as a daemon, started from the sway config as above. It exits when sway does.

| Option | What it does |
| --- | --- |
| `--once` | one pass over the current tree, then exit |
| `--dry-run` | print the sway commands instead of running them |
| `--debug` | log every command it sends to stderr |
| `--config PATH` | read the config file at `PATH` instead of the default one |

`--once --dry-run` only reads the tree, so it's safe to run in your session to see what the daemon would do.
It needs `SWAYSOCK`, which sway sets for everything it starts, including your terminal inside sway.

### Config file

It reads `$XDG_CONFIG_HOME/sway-autotile/config`, or `~/.config/sway-autotile/config` when
`XDG_CONFIG_HOME` isn't set. Without that file it uses the defaults. A file given with `--config` must exist.
Each line is `key = value`; blank lines and lines starting with `#` are skipped. An unknown key or a bad
value stops it with an error that names the line.

```ini
# keep sway's placement of a window opened while a focus key selects the whole workspace
open_at_workspace_end = off
```

| Key | Values | What it does |
| --- | --- | --- |
| `open_at_workspace_end` | `on` (default), `off` | open a window at the end of the workspace when a focus key selected the whole workspace |

Each key can also be set in the environment as `SWAY_AUTOTILE_` plus the key in upper case, for example
`SWAY_AUTOTILE_OPEN_AT_WORKSPACE_END=off sway-autotile --once --dry-run`. A variable wins over the file,
and the file wins over the default. An empty variable counts as unset; a bad value or an unknown
`SWAY_AUTOTILE_` variable stops it with an error. sway's `exec` passes sway's environment on, so a
variable exported in your shell profile overrides the file.

## Tests

```bash
tests/run              # everything, about 5 minutes
tests/run scenarios    # invariants in normal use: no leftover containers, no event loops, tab groups intact
tests/run sequences    # 9 seeded open/focus/close sequences; placement checked after every step
tests/run resize       # windows whose longer side already matches their parent's layout
tests/run keys         # one press of a move key binding moves the window (needs wtype)
tests/run focus        # one press of a focus parent/child key changes the focus (needs wtype)
tests/run cli          # every option and error exit: --help, --once, --dry-run, --config, no SWAYSOCK
```

Each case starts its own headless, software-rendered sway, so nothing happens in your session. The tests
need sway, python3 and kitty, and `tests/run keys` and `tests/run focus` need wtype. To use another terminal with a
`--title` option, set `AUTOTILE_TEST_TERMINAL`. `SEEDS="1 2" tests/run sequences` runs a subset, and
`KEEP=1` keeps the output directory. The tests never read your config file or `SWAY_AUTOTILE_` variables: each case
gets its own `XDG_CONFIG_HOME` with them unset, and `CONFIG='open_at_workspace_end = off' tests/run focus` gives every case that config.

After each window opens, the tests check that the new window and the window focused before it fill the
old rectangle of the focused window, half each along its longer side, and that no other window moved. A
focus change must move no window, and a close must make none smaller.

## Development

Issues and pull requests are welcome. Changes to `sway-autotile` should pass `tests/run`. The design
constraints in [AGENTS.md](AGENTS.md) explain the non-obvious parts: why `split none` is only sent for
whole runs of split containers, why windows are split even when their parent already has the right
layout, why a key's move is sometimes sent twice, why a key's focus parent can move focus two levels, and why
it's one process.

## Acknowledgements

The split direction rule comes from [autotiling-rs](https://github.com/ammgws/autotiling-rs) (MIT).

## License

MIT. See [LICENSE](LICENSE).
