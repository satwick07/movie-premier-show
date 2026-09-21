#!/usr/bin/env python3
"""Decide, notify, dedupe and self-disable. Import-safe: detection lives in check.py."""
import json, os, sys, urllib.request
from datetime import datetime
import check as C

STATE = os.environ.get("STATE_FILE", "state.json")
DRY_RUNS = int(os.environ.get("DRY_RUNS", "10"))
BOOK_MOVIE = ("https://in.bookmyshow.com/movies/bengaluru/the-paradise/buytickets/"
              f"{C.EVENT}/{C.TARGET_BMS}?etCodes={C.EVENT}&language=telugu")
def venue_link(code):
    return f"https://in.bookmyshow.com/cinemas/BANG/x/buytickets/{code}/{C.TARGET_BMS}"

def load():
    try: return json.load(open(STATE))
    except Exception: return {"runs": 0, "fired": False, "fail_streak": 0, "notified_broken": False}

def save(s): json.dump(s, open(STATE, "w"), indent=1)

def decide(res):
    """Return (fired, reasons[]) - any one source seeing real 23rd inventory fires."""
    reasons = []
    for code, r in res["favs"].items():
        if r.get("open"):
            reasons.append(f"FAV {C.FAVS[code]}: {', '.join(s['t'] for s in r['shows'] if s['t'])}")
    mv = res.get("movie") or {}
    # A favourite's per-venue page can 403 from a datacenter IP (GitHub runners).
    # The movie-wide API covers every Bengaluru venue, so fall back to it for any
    # favourite whose own page failed - otherwise a 403 could mask a real opening.
    if mv.get("ok"):
        by_code = {v["code"]: v for v in mv.get("venues", [])}
        for code, r in res["favs"].items():
            if not r.get("ok") and code in by_code:
                v = by_code[code]
                reasons.append(f"FAV {C.FAVS[code]} (via movie-wide; own page "
                               f"{r.get('err')}): {', '.join(t for t in v['times'][:8] if t)}")
                res["favs"][code] = {"ok": True, "open": True, "degraded": True,
                                     "shows": [{"t": t, "avail": None, "min": None}
                                               for t in v["times"]]}
    if mv.get("ok") and mv.get("served_target") and mv.get("venues"):
        reasons.append(f"BMS movie-wide: {len(mv['venues'])} Bengaluru venue(s) on the 23rd")
    elif mv.get("ok") and mv.get("has23"):
        reasons.append("BMS date strip now lists the 23rd")
    dd = res.get("district") or {}
    if dd.get("ok") and dd.get("open"):
        reasons.append(f"District: showDates now include {C.TARGET_ISO}")
    return bool(reasons), reasons

def build_alert(res, reasons):
    L = ["*THE PARADISE - 23 SEP TICKETS ARE OPEN* :tada:", ""]
    L.append("*Why this fired:*")
    L += [f"  - {r}" for r in reasons]
    L.append("")
    favs_open = [(c, r) for c, r in res["favs"].items() if r.get("open")]
    if favs_open:
        L.append("*>>> YOUR FAVOURITES <<<*")
        for c, r in favs_open:
            times = ", ".join(f"{s['t']}" + (f" (Rs{int(float(s['min']))})" if s.get("min") else "")
                              for s in r["shows"] if s.get("t"))
            L.append(f"*{C.FAVS[c]}*")
            L.append(f"  {times}")
            L.append(f"  <{venue_link(c)}|BOOK NOW>")
        L.append("")
    mv = res.get("movie") or {}
    near = [v for v in mv.get("venues", []) if v["km"] <= C.RADIUS_KM] if mv.get("ok") else []
    if near:
        L.append(f"*Nearby (<={C.RADIUS_KM:g} km of Marathahalli/Whitefield):*")
        for v in near:
            if v["code"] in C.FAVS: continue
            L.append(f"  *{v['name']}* - {v['km']} km "
                     f"(M {v['per']['Marathahalli']} / W {v['per']['Whitefield']})")
            L.append(f"    {', '.join(t for t in v['times'][:8] if t)}")
            L.append(f"    <{venue_link(v['code'])}|book>")
        L.append("")
    far = [v for v in mv.get("venues", []) if v["km"] > C.RADIUS_KM] if mv.get("ok") else []
    if far:
        L.append(f"_{len(far)} more venue(s) further out: " +
                 ", ".join(f"{v['name'].split(':')[0]} ({v['km']}km)" for v in far[:6]) + "_")
        L.append("")
    L.append(f"<{BOOK_MOVIE}|Full BMS listing for 23 Sep>")
    L.append(f"_checked {datetime.now(C.IST):%d %b %H:%M IST}_")
    return "\n".join(L)

def build_dryrun(res, run_no):
    L = [f"*Paradise watch - dry run {run_no}/{DRY_RUNS}* (pipe test, 23rd not open yet)", ""]
    for code, r in res["favs"].items():
        st = "OPEN" if r.get("open") else (f"closed ({r.get('why','')})" if r["ok"] else f"BLOCKED {r.get('err')} - covered by movie-wide")
        L.append(f"  FAV {C.FAVS[code]} - {st}")
    mv = res.get("movie") or {}
    if mv.get("ok"):
        L.append(f"  BMS date strip: {', '.join(d for d, dis in mv['strip'] if not dis)} (enabled)")
    dd = res.get("district") or {}
    if dd.get("ok"):
        L.append(f"  District showDates: {', '.join(dd['dates'])}")
    L.append("")
    L.append("*Your shortlist, ranked by distance (from the live 24 Sep board):*")
    for i, v in enumerate(NEAR_REF, 1):
        tag = "  <-- FAV" if v[1] in C.FAVS else ""
        L.append(f"  {i}. {v[0]} - {v[2]} km{tag}")
    L.append("")
    L.append(f"_{datetime.now(C.IST):%d %b %H:%M IST} - will alert the moment the 23rd opens_")
    return "\n".join(L)

NEAR_REF = [("INOX: Nexus, Whitefield", "FMFB", 1.0),
            ("V Cinema (Vijayalakshmi): Garudacharpalya", "VTGB", 3.8),
            ("Sri Vinayaka Cinemas 4K: Varthur", "SVYK", 3.8),
            ("INOX: Arcadia, Brigade Utopia", "AMNH", 4.1),
            ("Pushpanjali B N Pura", "PTBK", 4.9),
            ("Kino Cinemas: Seegehalli Kadugodi", "KINO", 5.0),
            ("INOX: SBR Horizon, Whitefield-Hoskote Rd", "NSBR", 5.6)]

def send(text):
    hook = os.environ.get("GCHAT_WEBHOOK", "").strip()
    if not hook:
        print("--- NO GCHAT_WEBHOOK SET; message would have been ---")
        print(text); print("--- end ---")
        return False
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(hook, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        print(f"  gchat -> {r.status}")
    return True

def disable_workflow(why):
    """Switch off the GitHub schedule so it can never nag again."""
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    wf = os.environ.get("WORKFLOW_FILE", "watch.yml")
    if not (tok and repo):
        print(f"  [local] would disable workflow ({why})"); return
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{wf}/disable"
    req = urllib.request.Request(url, method="PUT", headers={
        "Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            print(f"  workflow disabled ({why}) -> {r.status}")
    except Exception as e:
        print(f"  !! disable failed: {e}")

def main():
    s = load()
    now = datetime.now(C.IST)
    if s.get("fired"):
        print("already fired; nothing to do"); disable_workflow("already fired"); return 0
    if now > C.DEADLINE:
        print(f"past deadline ({C.DEADLINE:%d %b %H:%M IST}); stopping")
        if not s.get("deadline_notified"):
            send(f"*Paradise watch stopped* - deadline {C.DEADLINE:%d %b %H:%M IST} reached, "
                 f"23 Sep never opened. No further messages.")
            s["deadline_notified"] = True; save(s)
        disable_workflow("deadline"); return 0

    res = C.main()
    s["runs"] = s.get("runs", 0) + 1
    fired, reasons = decide(res)

    sources_ok = [bool((res.get("movie") or {}).get("ok")), bool(res["district"]["ok"])] + \
                 [r["ok"] for r in res["favs"].values()]
    if not any(sources_ok):
        s["fail_streak"] = s.get("fail_streak", 0) + 1
        print(f"  ALL SOURCES FAILED (streak {s['fail_streak']})")
        if s["fail_streak"] >= 3 and not s.get("notified_broken"):
            send("*Paradise watch MONITOR BROKEN* - every source failed 3x in a row "
                 "(BMS bot-block or schema change). Check manually: " + BOOK_MOVIE)
            s["notified_broken"] = True
        save(s); return 1
    s["fail_streak"] = 0

    if fired:
        send(build_alert(res, reasons))
        s["fired"] = True; save(s)
        disable_workflow("tickets found")
        return 0

    if s["runs"] <= DRY_RUNS:
        send(build_dryrun(res, s["runs"]))
    else:
        print(f"  run {s['runs']}: closed, silent (dry-run window over)")
    save(s)
    return 0

if __name__ == "__main__":
    sys.exit(main())
