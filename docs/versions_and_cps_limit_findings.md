# Cookie Clicker versions and CPS findings

Recorded September 6, 2026. These are code findings and observations from testing
this remapper, not a guarantee of the CPS another setup will achieve.

## What we found

| Version | Limit found in the code | When the timer resets |
| --- | --- | --- |
| Modern web version, source copy inspected | 50 CPS: ordinary mouse clicks need at least 20 ms between accepted clicks | After an accepted click |
| v1.0466, official archived source | 250 CPS: attempts need at least 4 ms since the previous handler's timer reset | After every attempt, including rejected clicks |
| v1.036, source copy inspected | Same 4 ms check as v1.0466 | After every attempt, including rejected clicks |

Sources: [modern source copy](https://github.com/ozh/cookieclicker/blob/gh-pages/main.js),
[official v1.0466 source](https://orteil.dashnet.org/cookieclicker/v10466/main.js),
[v1.036 source copy](https://github.com/coderdojoindy/cookie-clicker/blob/master/main.js).
The modern web and Steam version numbers used in testing weren't recorded.
The Steam result below is an observation; its installed source wasn't inspected.
These findings don't establish the behavior of every v1 release or Cookie Clicker Classic.

## Modern version: extra input helped on this PC

In the modern source inspected, `Game.ClickCookie` rejects ordinary mouse clicks
less than 20 ms after the last accepted click. Rejected clicks don't update
`Game.lastClick`. This gives a theoretical ceiling of 50 accepted CPS.

Test observations:

- A browser test registered roughly 500 clicks in ten seconds, about 50 CPS.
  The game also slowed to a few frames per second during rapid input.
- Steam registered about 47 CPS without visible lag.
- After trying several remapper rate caps, uncapped input gave the best results.
  The optional rate cap was subsequently removed from the remapper.

Our explanation is that frequent attempts give the game another chance to accept
a click soon after each 20 ms wait ends. With attempts spaced near 20 ms, delivery
timing can make one arrive too early and get rejected, leaving a longer wait
for the next attempt. This is a plausible explanation, not a measured timing trace.
The reason Steam avoided the browser's lag wasn't established.

## v1.0466: too much input can reduce accepted clicks

The official v1.0466 handler checks this condition:

```javascript
new Date().getTime()-Game.lastClick<1000/250
```

The cutoff is **4 ms**, not 1 ms. The 1 ms figure discussed during testing was an
example of input arriving at 1,000 attempts per second.

`Game.lastClick` is updated at the end of the handler even when the attempt was
rejected. Consequently, rapid rejected attempts keep restarting the wait.
The cookie's click event calls this handler directly; no separate 50 CPS check
was found in that path.

Test observations:

- Fast movement initially produced about 43 accepted CPS, suggesting an apparent
  limit near 50.
- Moving the mouse more slowly then produced about 100 accepted CPS.
- That higher result shows the earlier 43 CPS wasn't a fixed 50 CPS ceiling in
  this test.

The slower-movement result supports the timer explanation: fewer movement
reports can leave enough time between attempts for more of them to count.
Browser delivery in bursts could also explain a low accepted rate: the first
attempt after a gap counts, then closely spaced attempts are rejected. We did
not measure event spacing, so the exact contribution of either effect is unknown.

For illustration, attempts processed 1 ms apart can continually reset the wait;
attempts around 5 ms apart could approach 200 accepted CPS if processing is quick
enough. **200 and 250 CPS were not achieved or verified in our tests.**
Uncapped input working best in the modern version doesn't establish that it is
best for v1.0466. No optimal rate for v1.0466 has been established.

## Mouse polling, debouncing, and measurement

Testing used Ubuntu with Wayland and a mouse configured for 1,000 Hz polling.
The remapper generates at most one click per report containing nonzero X/Y
movement. It doesn't generate a click merely because another millisecond passed.
Slower movement can produce fewer qualifying reports even with the same polling rate.

Libinput filtering was a separate issue. The following override in
`/etc/libinput/local-overrides.quirks` helped on this PC after a reboot:

```ini
[mouse_move_click intentional rapid clicks]
MatchName=mouse_move_click
ModelBouncingKeys=1
```

It applies to the virtual mouse and doesn't remove a game's own click checks.
See the [README](../README.md#turn-off-debouncing-if-needed) for setup and the
[libinput documentation](https://wayland.freedesktop.org/libinput/doc/latest/device-quirks.html)
for quirk details.

Keep these measurements separate:

- `device_diagnostics/show_cps.py` counts completed left clicks from all watched
  mice before libinput and application filtering. It doesn't measure game acceptance.
- The game's click counter measures accepted clicks. Compare its change over an
  independently timed interval; cookies earned can include passive production.
- A one-second online CPS test once displayed about 4,000 CPS while freezing.
  The user continued moving for roughly three more seconds. Queued clicks counted
  against a delayed test timer are a plausible explanation; this wasn't evidence
  of 4,000 clicks generated in one real second.

For future comparisons, record the exact game version/URL, browser or Steam,
remapper rate setting if any, polling rate, test duration, click-counter change,
and whether the game lagged. Receiving many clicks and accepting many clicks are
different measurements.
