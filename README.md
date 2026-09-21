# movie-premier-show — The Paradise, 23 Sep 2026, Bengaluru

Watches for **23 Sep 2026** shows of **The Paradise (Telugu, `ET00436621`)** in
**Bengaluru**, prioritising theatres near **Marathahalli / Whitefield**, and posts to
Google Chat the moment they open. Then it **switches itself off**.

## Favourites (tier 1, top of every alert)
| Theatre | Code | ←Marathahalli | ←Whitefield |
|---|---|---|---|
| V Cinema (Vijayalakshmi): Garudacharpalya | `VTGB` | 3.8 km | 5.8 km |
| Sri Vinayaka Cinemas 4K: Varthur | `SVYK` | 5.7 km | 3.8 km |

## How detection works (3 independent sources)

1. **BMS per-venue page** — *sharpest, used for the favourites.*
   `GET /cinemas/BANG/x/buytickets/{CODE}/20260923`, parse `window.__INITIAL_STATE__`,
   look up `venueShowtimesFunctionalApi.queries["getShowtimesByVenue-{CODE}-20260923"]`
   and require a node with `EventCode == ET00436621` and a **non-empty `ShowTimes`**.
2. **BMS movie-wide API** — `showtimes-by-event`. Discovers *new* venues (e.g. if a PVR
   appears), asserts `SubRegCode == "BANG"`, ranks by haversine distance.
3. **District (Zomato)** — no bot protection, stdlib-only. Telugu format group
   `sfuykkkg9p` → `meta.showDates` must contain `2026-09-23`.

Any one source seeing real inventory fires the alert.

## Traps this deliberately avoids

- **BMS clamps unopened dates.** Asking for `20260923` returns the 24th's data. The
  per-venue check is immune because the requested date is baked into the state key; the
  movie-wide check filters `ShowDetails[].Date` and `ShowTimes[].ShowDateCode`.
- **Venue open ≠ film showing.** `SVYK` already lists 23 Sep for *other* films. We require
  Paradise **sessions**, not the date's presence.
- **Footer nav mentions.** `ET00436621` appears in "Movies Now Showing" links on pages with
  no Paradise sessions. Only session nodes count.
- **Hindi false positive.** District's Telugu group is queried directly; Hindi
  (`rnmyF80TtQ`) is a separate group.
- **Cloudflare.** Plain `curl` gets 403. BMS needs `curl_cffi` TLS impersonation. District
  needs nothing, so it still works if impersonation ever fails.
- **`MinPrice` is a string** (`"250.00"`) — parsed via `float`, not `int`.

## Stop guarantees (it cannot nag you)
1. Fires once → `state.json.fired = true` → every later run exits immediately.
2. Past **22 Sep 22:00 IST** → sends one "stopped" note, then nothing.
3. Either case calls the GitHub API to **disable its own schedule**.
4. All sources failing 3× in a row sends one `MONITOR BROKEN` alert (silent failure is the
   worst outcome), then stays quiet.

## Arming it
```bash
# 1. the webhook (repo secret — never a file)
gh secret set GCHAT_WEBHOOK --repo satwick07/movie-premier-show

# 2. prove the pipe before it matters
gh workflow run watch.yml --repo satwick07/movie-premier-show

# 3. kill it early if you change your mind
gh workflow disable watch.yml --repo satwick07/movie-premier-show
```
`DRY_RUNS=10` makes the first 10 runs post the nearby-theatre list so you can see it works;
after that it is silent until the 23rd opens.

## Mac tier (optional, 2-minute latency, zero GitHub minutes)
```bash
echo 'https://chat.googleapis.com/...' > .webhook   # gitignored
cp com.user.paradisewatch.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.user.paradisewatch.plist
# stop:
launchctl unload ~/Library/LaunchAgents/com.user.paradisewatch.plist
```
Uses a separate `state.local.json`, so the two tiers never disable each other.

## Cost
Public repo → Actions minutes are free and unlimited. On a private repo it would be
~44 runs to the deadline ≈ 44 billed minutes (`ubuntu-latest`, `timeout-minutes: 3`).
