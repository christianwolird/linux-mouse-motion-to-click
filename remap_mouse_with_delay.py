#!/usr/bin/env python3
"""Turn mouse movement reports into left clicks, with a minimum delay between clicks."""

from argparse import ArgumentParser
from contextlib import closing
from pathlib import Path
from time import monotonic
from evdev import InputDevice, UInput, ecodes as codes


def remap_events(events, output, min_delay_ms, left_held=False):
    min_delay = min_delay_ms / 1000  # The clock measures seconds.
    last_click = None  # Allow the first movement click immediately.
    report = []
    for event in events:
        # A report is a group of records ending in SYN_REPORT.
        if event.type != codes.EV_SYN:
            report.append(event)
            continue
        if event.code != codes.SYN_REPORT:
            continue

        moved = False
        left_changed = False
        forwarded = False
        for item in report:
            # X/Y movement earns a click but does not move the pointer.
            if item.type == codes.EV_REL and item.code in (codes.REL_X, codes.REL_Y):
                moved = moved or item.value != 0
                continue
            # Pass physical buttons and scrolling through unchanged.
            if item.type in (codes.EV_KEY, codes.EV_REL):
                if item.code == codes.BTN_LEFT and item.type == codes.EV_KEY:
                    left_changed = True
                    left_held = item.value != 0
                output.write_event(item)
                forwarded = True
        if forwarded:
            output.syn()

        # One click per moving report, regardless of distance or direction.
        # Using the target mouse's left button takes precedence over movement.
        if moved and not left_held and not left_changed:
            now = monotonic()  # Unaffected by changes to the system clock.
            if last_click is None or now - last_click >= min_delay:
                last_click = now  # Dropped clicks do not restart the timer.
                output.write(codes.EV_KEY, codes.BTN_LEFT, 1)  # Press.
                output.syn()  # Deliver the press.
                output.write(codes.EV_KEY, codes.BTN_LEFT, 0)  # Release.
                output.syn()  # Deliver the release.
        report.clear()  # No movement or click credit is saved for later.


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--min-delay', type=float, required=True, metavar='MS',
                        help='minimum time between movement clicks in milliseconds (e.g. 20)')
    args = parser.parse_args()
    if args.min_delay < 0:
        parser.error('--min-delay must be nonnegative')

    path = Path(__file__).with_name('target_mouse.txt').read_text().strip()
    # Closing the physical mouse releases its grab; closing the virtual mouse
    # removes it. These 'with' blocks close both devices when the script exits.
    with closing(InputDevice(path)) as mouse:
        capabilities = mouse.capabilities()
        buttons_and_axes = {codes.EV_KEY: capabilities[codes.EV_KEY],
                            codes.EV_REL: capabilities[codes.EV_REL]}
        # Keep the virtual name used by the existing libinput quirk.
        with UInput(buttons_and_axes, name='mouse_move_click', phys='mouse_move_click') as output:
            print(f'Target mouse: {mouse.name} ({path})')
            input('Release mouse buttons, then press Enter. Ctrl+C here stops. ')
            mouse.grab()  # Only this mouse is remapped. Use another to aim.
            while mouse.read_one() is not None:
                pass  # Discard input received while waiting to start.
            left_held = codes.BTN_LEFT in mouse.active_keys()
            remap_events(mouse.read_loop(), output, args.min_delay, left_held)


if __name__ == '__main__':
    main()
