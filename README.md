# Mouse movement to clicks

[`remap_mouse.py`](remap_mouse.py) turns movement from one chosen mouse into left
clicks. Use a second mouse to aim. [`target_mouse.txt`](target_mouse.txt) contains
only the chosen mouse's device path.

## Compatibility

For Linux desktops using **Wayland or X11**. Tested on **Ubuntu with Wayland**;
other Linux distributions and X11 are expected to work but have not been verified.
The script uses Linux's evdev/uinput interfaces, so it does not run on Windows
or macOS as written.

Requires Python with evdev installed, access to the physical mouse and
`/dev/uinput`, and a desktop that recognizes the virtual mouse. Installation
commands and permissions may differ by distribution. The libinput debouncing
workaround below may apply on either Wayland or X11 when libinput handles input.

## For moderators

All remapping behavior is in **remap_mouse.py**, read from top to bottom:

- `remap_events` reads one mouse report at a time. A report groups horizontal and
  vertical movement together, so diagonal or large movement still earns only
  one click.
- The four lines marked **Press**, **Deliver**, **Release**, **Deliver** produce
  that click. There is no click timer, multiplier, rate cap, or saved click credit.
- Physical buttons and scrolling pass through. Holding or changing the target
  mouse's left button suppresses that report's movement click.
- `main` opens the chosen mouse and a virtual output mouse, waits for Enter,
  discards setup input, and starts reading. The `with` blocks close the devices
  on exit, releasing the physical mouse's grab and removing the virtual mouse.

The script imports Python's `contextlib` and `pathlib`, plus evdev for Linux input
and output. It does not import anything from `device_diagnostics/` or `tests/`.

## Run

Install evdev and find your target mouse:

```bash
sudo apt install python3-evdev
sudo python3 device_diagnostics/detect_mice.py
```

Put its absolute device path in `target_mouse.txt`, on one line with **no comments
or quotes**. Prefer a `/dev/input/by-id/...-event-mouse` path; event numbers can
change after rebooting. The script reads the file beside itself.

```bash
sudo python3 remap_mouse.py
```

Release mouse buttons, then press Enter in the terminal. **Ctrl+C in that terminal
stops the script.** Release the aiming mouse's left button while using movement
clicks. Keep the configured path pointed at your physical target mouse; the
script uses it directly without validation.

**If rapid clicks are filtered:** users of libinput may need to disable debouncing
for the virtual mouse in `/etc/libinput/local-overrides.quirks`. See the
[working configuration and restart step](device_diagnostics/README.md#allow-rapid-clicks-through-libinput).

## Optional device tools and development checks

- [`device_diagnostics/`](device_diagnostics/README.md): list mice, inspect movement, or measure
  generated CPS. These tools run separately and are not needed for remapping.
- [`tests/`](tests/test_remap_mouse.py): checks of the code using fake devices,
  used during development only.
  Run with `python3 -m unittest discover -s tests -v`.
- [`requirements.txt`](requirements.txt): evdev version for a pip installation.

Errors, including Ctrl+C, use Python's normal traceback. Share the terminal output
when debugging. There is no custom error recovery or input-loss detection.
Linux can buffer input, so reports may arrive late. In testing on this PC, uncapped
input worked best in Steam Cookie Clicker: roughly 47 accepted CPS without lag.
