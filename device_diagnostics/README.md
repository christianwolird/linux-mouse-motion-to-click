# Optional device diagnostics

These scripts observe input; they do not grab mice or generate clicks. Run them
from the repository's top directory with evdev installed.

## Find or inspect mice

```bash
sudo python3 device_diagnostics/detect_mice.py
sudo python3 device_diagnostics/print_mice_events.py
```

Move each mouse separately to identify it. The listing includes mouse candidates:
keyboards, receivers, and virtual devices can expose mouse interfaces. Prefer a
listed `by-id` link when configuring the remapper. A `by-path` link identifies
the connection port instead. Both tools report inaccessible devices.

To inspect a particular mouse or print raw records:

```bash
sudo python3 device_diagnostics/print_mice_events.py --device /dev/input/event23
sudo python3 device_diagnostics/print_mice_events.py --device /dev/input/event23 --raw
```

Repeat `--device PATH` for multiple mice. Without `--raw`, output groups records
by `SYN_REPORT` (end of report). Ctrl+C stops printing. Printing every event can
lose input at high rates; this tool is not a throughput benchmark. Lost input
(`SYN_DROPPED`) is reported and grouped output resumes at the next report boundary.

## Measure generated CPS

Start the remapper first, then use a second terminal:

```bash
sudo python3 device_diagnostics/show_cps.py
```

The monitor watches all accessible mice present at startup, including the virtual
`mouse_move_click` mouse. Restart it after adding mice or restarting the remapper.
The virtual name stays unchanged because the existing libinput quirk matches it.

The display refreshes ten times per second:

```text
CPS:    500.0 | Total: 1523
```

Each completed left-button press/release pair counts once, after its report ends.
CPS is the count received in the previous one second; Total does not expire.
The first second fills the window. Physical left clicks from all watched mice
also count. The grabbed target mouse's clicks are observed through the virtual
mouse rather than directly.

This measures input **before libinput, the desktop, browser, and game filtering**.
Scheduling delays or buffered input can shift the measured rate. It does not tell
you how many clicks a game accepts. Lost input or disconnection stops the monitor
with an error. The monitor neither grabs devices nor consumes other readers' copies.

```bash
python3 device_diagnostics/show_cps.py --self-test
```

## Allow rapid clicks through libinput

Libinput's button debouncing can discard intentional rapid clicks. If the CPS
monitor shows high rates but applications receive much fewer clicks, this is one
possible cause. The following override worked on this PC after a reboot.

Create `/etc/libinput/local-overrides.quirks` if needed, or append this section to
the existing file using an editor with administrator permissions. Keep any other
sections already present:

```ini
[mouse_move_click intentional rapid clicks]
MatchName=mouse_move_click
ModelBouncingKeys=1
```

This is the debouncing workaround for the remapper's **virtual mouse**. Keep
`MatchName=mouse_move_click` exactly as written; it is not your physical mouse's
name. Then reboot and start the remapper again. The script does not edit this file.

This does not remove the game's own click limit. Libinput quirks can change
between versions; see the [official device-quirk documentation](https://wayland.freedesktop.org/libinput/doc/latest/device-quirks.html).

## Setup notes

Use Python 3.10 or newer. `sudo apt install python3-evdev` is the Debian/Ubuntu
installation route. Alternatively, use `requirements.txt` with a virtual environment:

```bash
python3 -m venv "$HOME/.local/share/fast-click-linux-tools/venv"
"$HOME/.local/share/fast-click-linux-tools/venv/bin/python" -m pip install -r requirements.txt
```

For that environment, replace `sudo python3` with
`sudo "$HOME/.local/share/fast-click-linux-tools/venv/bin/python"`.
Installing evdev from source may require a compiler and Python/Linux headers.

Input-device permissions are needed for diagnostics; the remapper also needs
uinput access. If `/dev/uinput` is missing, try `sudo modprobe uinput`.
Libinput debouncing and game processing may filter rapid clicks. These scripts
make no system-setting changes. The remapper deliberately omits validation,
input-loss handling, and friendly error messages; retain its traceback for debugging.
