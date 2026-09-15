#!/usr/bin/env python3
"""Measure observed left-click intervals for 10 seconds after the first click.

A click is a BTN_LEFT press followed by release, committed at SYN_REPORT.
Release observation times are stored as integer monotonic nanoseconds. These
measure delivery to Python, including scheduling and evdev read batching, not
hardware event spacing. No devices are grabbed and no input is injected.
"""

import argparse
from contextlib import ExitStack
from pathlib import Path
import selectors
import signal
import statistics
import sys
import time


DURATION_NS = 10_000_000_000


class ClickObserver:
    """Keep separate press/release state for each mouse."""

    def __init__(self):
        self.pressed = False
        self.pending = []

    def feed(self, event, now_ns, e):
        if event.type == e.EV_SYN:
            if event.code == e.SYN_DROPPED:
                raise RuntimeError("SYN_DROPPED: input was lost; trial is invalid. Stopped.")
            if event.code == e.SYN_REPORT:
                clicks, self.pending = self.pending, []
                return clicks
        elif event.type == e.EV_KEY and event.code == e.BTN_LEFT:
            if event.value == 1:
                self.pressed = True
            elif event.value == 0 and self.pressed:
                self.pending.append(now_ns)
                self.pressed = False
        return []


def collect_trial(selector, e):
    """Wait indefinitely for the first click, then stop even if input goes quiet."""
    timestamps = []
    deadline = None
    while True:
        now_ns = time.monotonic_ns()
        if deadline is not None and now_ns >= deadline:
            return sorted(timestamps)
        timeout = None if deadline is None else (deadline - now_ns) / 1_000_000_000
        for key, _ in selector.select(timeout):
            try:
                for event in key.fileobj.read():
                    # Timestamp immediately, before decoding/counting the event.
                    now_ns = time.monotonic_ns()
                    if deadline is not None and now_ns >= deadline:
                        return sorted(timestamps)
                    clicks = key.data.feed(event, now_ns, e)
                    if clicks:
                        if deadline is None:
                            deadline = clicks[0] + DURATION_NS
                            print("Started!", flush=True)
                        timestamps.extend(stamp for stamp in clicks if stamp < deadline)
            except BlockingIOError:
                pass


def interval_histogram(intervals_ns):
    """Group intervals by hundredths of a millisecond, combining the tails."""
    bins = dict.fromkeys(range(3_850_000, 4_150_001, 10_000), 0)
    for interval in intervals_ns:
        rounded = ((interval + 5_000) // 10_000) * 10_000
        bins[max(3_850_000, min(4_150_000, rounded))] += 1
    return bins


def print_results(timestamps):
    intervals = [right - left for left, right in zip(timestamps, timestamps[1:])]
    print("\n10-second trial complete (timed from the first completed click).")
    print(f"Total clicks: {len(timestamps)}")
    print(f"Intervals:    {len(intervals)}")
    if not intervals:
        print("At least two clicks are needed to measure intervals.")
        return
    print(f"Average delay: {statistics.mean(intervals) / 1_000_000:.6f} ms")
    print(f"Median delay:  {statistics.median(intervals) / 1_000_000:.6f} ms")
    print(f"Minimum delay: {min(intervals) / 1_000_000:.6f} ms")
    print(f"Maximum delay: {max(intervals) / 1_000_000:.6f} ms")
    print(f"Std. deviation (population): {statistics.pstdev(intervals) / 1_000_000:.6f} ms")
    print("\nIntervals rounded to 0.01 ms:")
    print(f"{'Delay (ms)':>12}  {'Count':>8}  {'Percent':>8}")
    for bucket_ns, count in interval_histogram(intervals).items():
        label = f'{bucket_ns / 1_000_000:.2f}'
        if bucket_ns == 3_850_000:
            label = '<=' + label
        elif bucket_ns == 4_150_000:
            label = '>=' + label
        print(f"{label:>12}  {count:8d}  {100 * count / len(intervals):7.2f}%")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", action="append", type=Path,
                        help="watch only this device path; repeat for multiple mice")
    args = parser.parse_args()
    try:
        from evdev import InputDevice, ecodes as e
    except ImportError:
        raise ValueError("Install Python evdev first; see README.md.") from None

    paths = args.device or sorted(p for p in Path('/dev/input').iterdir()
                                  if p.name.startswith('event'))
    with ExitStack() as devices, selectors.DefaultSelector() as selector:
        seen = set()
        for path in paths:
            try:
                path = path.resolve(strict=True)
                if path in seen:
                    continue
                seen.add(path)
                device = InputDevice(str(path))
                devices.callback(device.close)
                caps = device.capabilities()
            except OSError as error:
                if args.device:
                    raise
                print(f"Skipping {path}: {error}", file=sys.stderr)
                continue
            if not (e.BTN_LEFT in caps.get(e.EV_KEY, []) and
                    {e.REL_X, e.REL_Y} <= set(caps.get(e.EV_REL, []))):
                device.close()
                if args.device:
                    raise ValueError(f"{path} is not a relative-pointer mouse")
                continue
            selector.register(device, selectors.EVENT_READ, ClickObserver())
            print(f"Watching {device.path}: {device.name}")
        if not selector.get_map():
            raise ValueError("No accessible mice found. Start the remapper first and run with sudo.")
        print("Combined clicks from the devices above, before libinput/browser filtering.")
        print("Observation timestamps include Python scheduling and input read batching.")
        resolution_ns = time.get_clock_info('monotonic').resolution * 1_000_000_000
        print(f"Monotonic clock resolution: {resolution_ns:g} ns (not a guarantee of delivery accuracy).")
        print("Waiting for the first completed left click; Started! marks the beginning of the 10-second trial.")
        print("Restart after adding mice or restarting the remapper. Ctrl+C cancels.", flush=True)
        print_results(collect_trial(selector, e))


if __name__ == '__main__':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nTrial cancelled.", file=sys.stderr)
        sys.exit(130)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"variance_probe: {error}", file=sys.stderr)
        sys.exit(1)
