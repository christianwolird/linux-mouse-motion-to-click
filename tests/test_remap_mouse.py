"""Check the remapper using fake input and output; no mouse devices are opened."""

from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from evdev import InputEvent, ecodes as e

import remap_mouse


class Output:
    def __init__(self):
        self.events = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def write(self, kind, code, value):
        self.events.append((kind, code, value))

    def write_event(self, event):
        self.write(event.type, event.code, event.value)

    def syn(self):
        self.write(e.EV_SYN, e.SYN_REPORT, 0)


syn = (e.EV_SYN, e.SYN_REPORT, 0)
down = (e.EV_KEY, e.BTN_LEFT, 1)
up = (e.EV_KEY, e.BTN_LEFT, 0)
move = (e.EV_REL, e.REL_X, 1)
click = [down, syn, up, syn]


def run(records, left_held=False):
    output = Output()
    remap_mouse.remap_events((InputEvent(0, 0, *record) for record in records), output, left_held)
    return output.events


class RemapMouseTests(unittest.TestCase):
    def test_diagonal_large_movement_is_one_click(self):
        self.assertEqual(run([(e.EV_REL, e.REL_X, 10000),
                              (e.EV_REL, e.REL_Y, -10000), syn]), click)

    def test_two_reports_are_two_clicks(self):
        self.assertEqual(run([move, syn, move, syn]), click * 2)

    def test_zero_empty_and_incomplete_reports_do_not_click(self):
        self.assertEqual(run([(e.EV_REL, e.REL_X, 0), syn, syn, move]), [])

    def test_wheel_and_buttons_pass_through_without_clicking(self):
        records = [(e.EV_REL, e.REL_WHEEL, -1),
                   (e.EV_KEY, e.BTN_RIGHT, 1), syn,
                   (e.EV_KEY, e.BTN_RIGHT, 0), syn]
        self.assertEqual(run(records), records)

    def test_left_hold_and_transition_reports_suppress_mapping(self):
        records = [down, move, syn, move, syn, up, move, syn, move, syn]
        self.assertEqual(run(records), [down, syn, up, syn] + click)

    def test_metadata_does_not_trigger_clicks(self):
        self.assertEqual(run([(e.EV_MSC, e.MSC_SCAN, 1), syn]), [])

    def test_left_button_already_held_at_start_suppresses_movement(self):
        self.assertEqual(run([move, syn, up, syn, move, syn], left_held=True),
                         [up, syn] + click)

    def test_main_closes_devices_and_propagates_errors(self):
        for failure in (None, "interrupt", "disconnect", "grab", "mid-click", "prompt"):
            with self.subTest(failure=failure):
                mouse = Mock()
                mouse.capabilities.return_value = {e.EV_KEY: [e.BTN_LEFT],
                                                   e.EV_REL: [e.REL_X, e.REL_Y]}
                mouse.read_one.side_effect = [InputEvent(0, 0, *move), None]
                mouse.active_keys.return_value = []
                mouse.read_loop.return_value = [InputEvent(0, 0, *r) for r in (move, syn)]
                output = Output()
                expected = None
                if failure == "interrupt":
                    mouse.read_loop.side_effect = KeyboardInterrupt
                    expected = KeyboardInterrupt
                elif failure == "disconnect":
                    mouse.read_loop.side_effect = OSError("unplugged")
                    expected = OSError
                elif failure == "grab":
                    mouse.grab.side_effect = OSError("already grabbed")
                    expected = OSError
                elif failure == "prompt":
                    expected = EOFError
                elif failure == "mid-click":
                    original_write = output.write

                    def interrupted_write(kind, code, value):
                        original_write(kind, code, value)
                        if (kind, code, value) == down:
                            raise KeyboardInterrupt

                    output.write = interrupted_write
                    expected = KeyboardInterrupt
                with patch.object(Path, "read_text", return_value="/dev/input/by-id/my-mouse\n"), \
                     patch("remap_mouse.InputDevice", return_value=mouse) as opened, \
                     patch("remap_mouse.UInput", return_value=output) as virtual, \
                     patch("builtins.input", side_effect=EOFError if failure == "prompt" else None), \
                     patch("builtins.print"):
                    if expected:
                        with self.assertRaises(expected):
                            remap_mouse.main()
                    else:
                        remap_mouse.main()
                        self.assertEqual(output.events, click)
                        self.assertEqual(mouse.read_one.call_count, 2)
                opened.assert_called_once_with("/dev/input/by-id/my-mouse")
                self.assertEqual(virtual.call_args.kwargs,
                                 {"name": "mouse_move_click", "phys": "mouse_move_click"})
                mouse.close.assert_called_once()
                self.assertTrue(output.closed)
