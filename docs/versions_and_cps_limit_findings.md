# Cookie Clicker versions and CPS findings

Recorded September 6, 2026; findings updated September 7, 2026; repository references
updated September 15, 2026. These are code findings and
observations from testing this remapper, not a guarantee of the clicks per second
(CPS) another setup will achieve.

## What we found

| Version | Limit found in the code | When the timestamp changes | Time recorded |
| --- | --- | --- | --- |
| Web v2.052 and v2.058 | 50 CPS: ordinary mouse clicks need at least 20 ms since the last accepted click | Only after an accepted click | Start of that handler call |
| v1.0466, official archived source | 250 CPS: attempts need at least 4 ms since the previous handler's timer reset | After every attempt, including rejected clicks | End of that handler call |
| v1.036, source copy inspected in the earlier investigation | Same 4 ms check as v1.0466 | After every attempt, including rejected clicks | End of that handler call |

Sources: [archived v2.052 source](https://github.com/ozh/cookieclicker/blob/c056e4f767a0da581b28b9142f0a29df834aa010/main.js#L4764-L4797),
[official current web source, inspected as v2.058](https://orteil.dashnet.org/cookieclicker/main.js),
[official v1.0466 source](https://orteil.dashnet.org/cookieclicker/v10466/main.js),
[v1.036 source copy](https://github.com/coderdojoindy/cookie-clicker/blob/master/main.js).
The v2.052 and v2.058 `Game.ClickCookie` functions inspected were identical.
Steam testing used v2.053; its installed source wasn't inspected.
These findings don't establish the behavior of every v1 release or Cookie Clicker Classic.

The remaining investigation is **how the browser and JavaScript engine space or
bunch mouse events before and during handler execution**. The game's throttle
rules are established; the timing that reaches those rules hasn't been measured.

## The click handlers

These excerpts retain the relevant source lines and control flow; comments mark
omitted work such as particles, sounds, and achievement tracking.

### v1.0466: every attempt restarts the wait

The official source defines `Game.ClickCookie` at lines 1550–1578:

```javascript
if (new Date().getTime()-Game.lastClick<1000/250)
{
}
else
{
    // ... omitted ...
    Game.Earn(Game.computedMouseCps);
    // ... omitted ...
    Game.cookieClicks++;
}
Game.lastClick=new Date().getTime();
```

The cutoff is 4 ms. The timestamp update is **outside** the accepted branch and
reads the clock again at the **end** of the handler. Rejected attempts restart the
wait too. An accepted handler's own execution time therefore delays the start of
the next 4 ms wait. The desktop binding at line 1617 sends the big cookie's DOM
`click` events directly to this function.

### v2.052 and v2.058: only accepted clicks restart the wait

In the archived v2.052 source, the function is at lines 4764–4797:

```javascript
var now=Date.now();
// ... omitted ...
if (Game.OnAscend || Game.AscendTimer>0 || Game.T<3 || now-Game.lastClick<1000/((e?e.detail:1)===0?3:50)) {}
else
{
    // ... omitted ...
    Game.cookieClicks++;
    // ... omitted ...
    Game.lastClick=now;
}
```

The update is **inside** the accepted branch and stores the time captured at the
**start** of the handler. Rejected clicks don't restart the wait. Ordinary mouse
clicks select the `50` branch, giving 20 ms. Events with `detail === 0` instead
select a 3 CPS limit using the same timestamp, not a second timer. Other conditions
prevent clicks during ascension and the first few game ticks.

Both versions also check a 15 CPS threshold inside the accepted branch. That
tracks the "Uncanny clicker" achievement; it doesn't reject clicks. No second
click-acceptance timer was found in these handlers.

## Measurements

Game rates below were estimated by moving the mouse for approximately ten seconds,
timed with a handheld stopwatch, and dividing the net cookie increase by ten.
They are approximate effective rates, not instrumented handler counts. **The web
results slightly above 50 CPS are explained by hand-timing error and are not an
open question.** Raw click rates were measured separately with an external program.

The delay-controlled trials below used `remap_mouse_with_delay.py`, which has
since been removed. They are retained as historical measurements. The current
[`remap_mouse.py`](../remap_mouse.py) has no minimum-delay setting or click-rate limit.

### v1.0466

The original browser trials used Brave. A subsequent Firefox trial used the same
1–6 ms delay settings in v1.0466. The raw rates below are the earlier external
measurements; they weren't remeasured concurrently with the Firefox trial.

| Minimum delay (ms) | Raw clicks/s | Brave effective CPS | Firefox effective CPS |
| --- | ---: | ---: | ---: |
| 1 | 680 | 53 | 44 |
| 2 | 400 | 61 | 82 |
| 3 | 280 | 126 | 144 |
| 4 | 220 | 152 | 168 |
| 5 | 180 | 142 | 157 |
| 6 | 152 | 127 | 152 |

Unthrottled Brave previously produced 39.4 effective CPS at approximately 1,000
raw clicks/s, the nominal movement-report rate. An unthrottled Firefox result
hasn't been recorded.

Firefox was higher at five of six settings. Both browsers peaked at 4 ms, with
Firefox reaching 168 versus Brave's 152 effective CPS (about 10.5% higher).
At 6 ms, Firefox's effective rate matched the separately measured raw rate; this
is consistent with little loss, but doesn't establish that every event survived
in that trial. No universal optimum has been established, and 200 or 250 accepted
CPS hasn't been verified.

The results support browser-dependent timing and the hypothesis that Firefox
bunches clicks differently, possibly less aggressively. They don't isolate the
cause: handler execution cost, clock precision, browser settings, and the Linux
window-system backend can also affect the comparison. Higher game CPS alone is
not a measure of faithful spacing. Below v1's 4 ms threshold, perfectly preserved
spacing would reject almost every attempt; extra gaps can increase acceptance.

Earlier informal tests gave about 43 CPS with fast movement and about 100 CPS
with slower movement. The newer measurements reinforce that the apparent limit
near 50 was not a fixed v1 cap. No visible lag was reported in v1 web testing.

### v2 web and Steam

| Version | Approximately 1,000 raw clicks/s | Approximately 400 raw clicks/s | Visual behavior |
| --- | --- | --- | --- |
| Web v2.052 and v2.058 | 50.8 and 51.4 effective CPS, both approximately 50 given hand timing | 42.2 and 46.5 effective CPS | Heavy lag under high input, approximately 1 FPS |
| Steam v2.053 | Approximately 46 effective CPS | Approximately 46.7 effective CPS | No visible lag |

The paired web figures aren't assigned to individual versions in the measurement
record. The small Steam difference is within the stated measurement uncertainty.
These trials don't establish that visual lag improves click acceptance.

## What the timing rules explain, and what remains unknown

### The game checks processing time, not the event's timestamp

Neither handler uses `event.timeStamp` for its throttle. It checks the clock when
JavaScript executes. Events can wait while the browser is busy and then be
processed close together. Constant delivery latency preserves spacing; changes
in latency can stretch or compress it. See
[MDN's JavaScript execution model](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Execution_model)
and [event timestamps](https://developer.mozilla.org/en-US/docs/Web/API/Event/timeStamp).

This distinction can explain nonzero v1 acceptance under very fast input. A
perfectly regular sequence processed every 1 ms would keep restarting the wait
after the first click. A processing gap of at least 4 ms instead lets the next
click through; subsequent closely spaced clicks fail. Smooth-looking animation
doesn't exclude occasional pauses of a few milliseconds. The exact reason for
the measured 39.4 CPS remains unmeasured.

Likewise, 220 raw clicks/s means a mean interval of 4.545 ms, not a guarantee of
4 ms between the previous handler's end and the next handler's check. For example,
with negligible handler duration:

| Event | Generated at | Processed at | v1 result |
| --- | ---: | ---: | --- |
| 1 | 0 ms | 0 ms | Accepted |
| 2 | 5 ms | 10 ms | Accepted |
| 3 | 10 ms | 10.2 ms | Rejected |
| 4 | 15 ms | 15 ms | Accepted |

All generated intervals are 5 ms, yet processing bunches two events together.
Handler cost can also matter: a handler beginning at 0 ms and finishing at 2 ms
leaves only 3 ms before the next attempt at 5 ms. These are illustrative
mechanisms, not traces from this PC. Average rates alone can't tell whether
bunching, handler cost, or losses before the DOM handler account for 220 becoming 152.

For v2, frequent attempts can reduce the wait for the first event after its 20 ms
deadline. However, perfectly uniform 400 CPS would still allow 50 accepted CPS:
eight 2.5 ms intervals equal 20 ms. The measured reduction therefore needs timing
variation or processing effects, not merely a lower average input rate. At 46
accepted CPS, the mean accepted interval is about 21.74 ms. Steam's exact delivery
behavior and its installed handler still need inspection.

### The removed delay-based remapper also sampled events at processing time

The removed `remap_mouse_with_delay.py` checked `monotonic()` when
processing each eligible movement report. The first click passed immediately;
only generated clicks restarted its timer. It dropped early attempts and didn't
schedule a click for the instant the delay expired. The next eligible report
had to arrive and be processed first.

The raw measurements show a consistent excess over the requested minimum:

| Minimum delay | Mean output interval, 1,000 / raw CPS | Excess over minimum |
| --- | ---: | ---: |
| 1 ms | 1.471 ms | 0.471 ms |
| 2 ms | 2.500 ms | 0.500 ms |
| 3 ms | 3.571 ms | 0.571 ms |
| 4 ms | 4.545 ms | 0.545 ms |
| 5 ms | 5.556 ms | 0.556 ms |
| 6 ms | 6.579 ms | 0.579 ms |

This roughly half-millisecond excess is consistent with waiting for an eligible
report on a nominal 1 ms stream with variable processing times. It doesn't prove
the distribution of report intervals. In particular, 680/1,000 is an output/input
ratio, not the fraction of adjacent reports separated by less than 1 ms: the
comparison is against the last accepted report, not every preceding report.

The removed script accepted fractional milliseconds, for example `--min-delay 3.8`
for 3,800 microseconds. Changing the CLI's units alone wouldn't have improved clock
precision. This option is not available in the current remapper.

### Visual lag and sound are separate leads

Low displayed FPS doesn't imply equally infrequent click handling. Painting can
fall behind while input processing continues.

In v2, the big cookie's `mousedown` handler invokes click-sound work whenever
`Game.prefs.cookiesound` is enabled, independently of the earning throttle. This
could create substantial work under high input even when only 50 clicks/s earn
cookies. Setting game sound volume to zero makes `PlaySound` return early, so
sound-off trials can test this hypothesis. Sound settings and their contribution
to these results haven't been established. See the
[v2.058 mouse and sound handlers](https://github.com/ozh/cookieclicker/blob/151a25611cb6dc68877f215769d0a2373b06dc42/main.js#L4930-L5025).

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

- `diagonstics/show_cps.py` counts completed left clicks from all watched
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

## Next investigation: trace browser event spacing

### Candidate browsers and online evidence

Firefox and Chrome aren't the only browser families. The broader survey below
covers the main practical Linux alternatives and several experimental engines.
It groups browsers by their underlying implementation, rather than treating
every browser brand as a wholly different input pipeline. Shared engines don't
guarantee identical timing: versions, patches, toolkits, and settings still matter.

The online sources reviewed don't establish which browser best preserves rapid
button-event spacing on this setup. The priorities below are judgments about
useful experiments, not a measured performance ranking.

| Family or implementation | Browsers surveyed | Relevance to these tests |
| --- | --- | --- |
| Chromium/Blink | Chrome, Chromium, Brave, Edge, Opera, Vivaldi | Shared Chromium foundation, so start with one clean Chrome/Chromium control against Brave instead of assuming every brand provides an independent engine. [Brave's comparison](https://brave.com/compare/chrome-vs-brave/) documents the shared base. |
| Chromium through QtWebEngine | qutebrowser, Falkon | Still Chromium, but Qt integration provides an additional platform path to compare if needed. [qutebrowser documentation](https://qutebrowser.org/doc/help/settings.html) and [Falkon](https://www.falkon.org/about/). |
| Current Firefox/Gecko family | Firefox, Waterfox, LibreWolf, Floorp, Zen | Firefox remains the measured baseline. Fork-specific changes may matter, but no reviewed source shows one of these forks preserving rapid click spacing better. Their projects document the Firefox base: [Waterfox](https://github.com/BrowserWorks/waterfox), [LibreWolf](https://librewolf.net/), [Floorp](https://floorp.app/), [Zen](https://github.com/zen-browser/desktop). |
| WebKitGTK | GNOME Web (Epiphany), Luakit, Vimb, surf | A separate engine family worth testing next; GNOME Web is the most straightforward first representative for this experiment. Other frontends provide further comparisons if WebKit performs well. [WebKitGTK](https://webkitgtk.org/), [Luakit](https://luakit.github.io/), [Vimb](https://fanglingsu.github.io/vimb/), [surf](https://surf.suckless.org/). |
| Goanna / Unified XUL Platform | Pale Moon, Basilisk | Maintained forks of older Mozilla technology, sufficiently distinct from current Firefox to merit a separate test. Pale Moon's single-process architecture is a particularly relevant contrast. [Pale Moon](https://www.palemoon.org/index.shtml), [Basilisk](https://www.basilisk-browser.org/). |
| Ladybird | Ladybird | Independent engine, but the project describes its first alpha as aimed at developers and early adopters. Exploratory rather than a first practical choice. [Project status](https://ladybird.org/). |
| Servo | servoshell | Another distinct engine; the project explicitly describes servoshell as a test browser, not a full browser. Exploratory, with game compatibility and timing unverified. [Servo documentation](https://book.servo.org/trying/getting-servoshell.html). |
| Other lightweight engines | NetSurf | Its documentation describes incomplete JavaScript support, making it a lower-priority compatibility experiment for this JavaScript game. [NetSurf documentation](https://www.netsurf-browser.org/documentation/info.html#JavaScript). |

**Recommended next tests: Pale Moon, then GNOME Web, with Firefox retained as the
baseline.** A clean Chrome/Chromium trial remains useful to separate Brave-specific
behavior from the shared Chromium engine. After that, consider Basilisk, one
QtWebEngine browser, or another WebKitGTK frontend before spending time on many
closely related Firefox or Chromium variants.

Pale Moon is the significant addition to the earlier shortlist. Its project
documents a [single-process design](https://www.palemoon.org/index.shtml), and
[current Linux builds are available](https://www.palemoon.org/download.shtml).
My inference is that this offers a useful test of whether browser-to-renderer
process messaging contributes to the timing variation. It doesn't establish
that Pale Moon will be faster or preserve spacing better: a single process still
has event queues, and competing UI/rendering work can cause delays. Cookie Clicker
v1.0466 compatibility and accepted CPS in these browsers haven't been tested here.

GNOME Web offers a different mature engine without changing the Linux machine.
WebKit is also used by Safari, but Safari isn't a native option for this Linux
setup; changing operating systems would introduce another variable. For Goanna
tests, record the actual display backend too: for example,
[Basilisk's Linux requirements](https://basilisk-browser.org/requirements.html)
list X.Org, so its results shouldn't automatically be attributed solely to the
engine when compared with a native-Wayland browser.

The strongest input-specific finding is that **movement-event coalescing and
button-event bunching are different mechanisms**. Coalescing merges events;
bunching can preserve every event while compressing their execution intervals.
[Chrome's input architecture explanation](https://developer.chrome.com/blog/inside-browser-part4/)
describes frame-aligned coalescing for continuous movement/wheel events and
immediate dispatch for discrete mouse presses/releases. The remapper sends
button events, having already consumed the target mouse's X/Y movement.

Current [Chromium event-queue source](https://github.com/chromium/chromium/blob/main/third_party/blink/renderer/platform/widget/input/main_thread_event_queue.cc)
supports that distinction: `IsRafAlignedEvent` selects mouse movement, wheel,
and touch movement, not mouse down/up. However, `DispatchEvents` drains queued
events in a loop. Immediate scheduling therefore doesn't promise immediate
JavaScript execution or preservation of the original spacing when work backs up.
This gives a concrete mechanism to inspect; it doesn't prove that the tested
Brave build was bunching clicks at this point.

Also record whether each browser actually uses native Wayland or X11 through
XWayland. Being in a Wayland desktop session doesn't identify the browser's
backend. Chromium supports separate X11 and Wayland platforms, documented in its
[Ozone overview](https://chromium.googlesource.com/chromium/src/+/main/docs/ozone_overview.md).
Comparing backends within one browser is a useful separate experiment; neither
backend is established as better here.

Because the game reads a JavaScript wall clock, record clock precision as well
as dispatch intervals. [MDN documents browser-dependent precision reduction for
`Date.now()`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date/now).
Different game acceptance rates can therefore arise without different physical
input spacing. Keep default settings for the initial comparison and record the
exact versions and relevant privacy settings.

### Measurements that distinguish faithful delivery from higher game CPS

The next step is to follow the same trial through the input pipeline, rather than
compare only average rates from different programs:

1. Record virtual-mouse press/release timestamps to establish actual output
   spacing and counts.
2. Record DOM `click` timestamps and handler entry/exit times. Compare event
   spacing with processing spacing and check whether delivery lag grows and
   then collapses into bursts. Event timestamps describe browser events, not
   necessarily hardware report times; compare intervals within each clock domain.
3. Record `Game.lastClick` and changes to `Game.cookieClicks` to distinguish
   events missing before the handler from attempts rejected by its throttle.
   For v1, measure the previous handler's final timestamp to the next check;
   for v2, measure from the previous accepted handler's start.
4. Compare the same input settings across browser and Steam trials, recording
   browser/runtime versions, actual window-system backends, and sound/graphics
   settings. Test sound volume zero separately to isolate its contribution.

Start with a minimal click-recording page and then the game, so browser delivery
can be compared with the extra work in Cookie Clicker's handler. Report event
counts, the distribution of consecutive handler intervals, delivery-lag changes,
and handler durations. In particular, count how often a source interval of at
least 4 ms becomes a shorter interval at the game's check. Those observations
can establish spacing fidelity; an average click counter alone cannot.

Use an accurately measured elapsed interval and buffer observations in memory
instead of printing every event during a trial. Instrumentation itself can
change timing, so compare with an uninstrumented baseline. The aim is to locate
where spacing changes and quantify it; browser bunching is currently a plausible
explanation, not an established measurement from this setup.
