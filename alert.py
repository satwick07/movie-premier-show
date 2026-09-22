#!/usr/bin/env python3
"""Decide, notify, dedupe and self-disable.

Rules:
  - not open            -> silence
  - TIER 1 open         -> big alert, then STOP for good
  - other venue open    -> alert once, keep hunting tier 1
  - NEW nearby opens    -> alert again (each new one), keep hunting
  - past deadline       -> one line, then stop
Only tier 1 stops the watch.
"""
import json, os, sys, urllib.request
from datetime import datetime
import check as C

STATE    = os.environ.get("STATE_FILE", "state.json")
TIER1    = list(C.FAVS)                      # VTGB, SVYK - only these stop it
BOOK_MOVIE = ("https://in.bookmyshow.com/movies/bengaluru/the-paradise/buytickets/"
              f"{C.EVENT}/{C.TARGET_BMS}?etCodes={C.EVENT}&language=telugu")

def venue_link(code):
    return f"https://in.bookmyshow.com/cinemas/BANG/x/buytickets/{code}/{C.TARGET_BMS}"

def load():
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("runs", 0); s.setdefault("fired", False)
    s.setdefault("fail_streak", 0); s.setdefault("notified_broken", False)
    s.setdefault("elsewhere_notified", False); s.setdefault("notified_near", [])
    s.setdefault("cineluxe_notified", False)
    s.setdefault("deadline_notified", False)
    return s

def save(s): json.dump(s, open(STATE, "w"), indent=1)

def classify(res):
    """Split the world into: tier-1 hits, nearby others, far others."""
    mv = res.get("movie") or {}
    # a tier-1 venue page can 403 from a datacenter IP; recover it from the movie-wide payload
    if mv.get("ok"):
        by_code = {v["code"]: v for v in mv.get("venues", [])}
        for code in TIER1:
            r = res["favs"].get(code) or {}
            if not r.get("ok") and code in by_code:
                v = by_code[code]
                res["favs"][code] = {"ok": True, "open": True, "degraded": True,
                                     "shows": [{"t": t, "avail": None, "min": None}
                                               for t in v["times"]]}
    tier1 = [(c, res["favs"][c]) for c in TIER1
             if (res["favs"].get(c) or {}).get("open")]
    others = [v for v in mv.get("venues", [])
              if mv.get("ok") and v["code"] not in TIER1]
    near = [v for v in others if v["km"] <= C.RADIUS_KM]
    far  = [v for v in others if v["km"] >  C.RADIUS_KM]
    dd = res.get("district") or {}
    district_only = bool(dd.get("ok") and dd.get("open")) and not (mv.get("ok") and mv.get("venues"))

    # District-exclusive tier-1 venue (Vinayaka Cineluxe, Marathahalli).
    # CONFIRMED = the movie page's earliest date is the target AND that venue is
    # among the venues showing Paradise that day. This is the only way to tie the
    # venue to the film, because District ignores ?date= on both page types.
    dm = res.get("dmovie") or {}
    dt1 = []
    if dm.get("ok") and dm.get("earliest") == C.TARGET_ISO:
        dt1 = [v for v in dm.get("venues", []) if C.DISTRICT_T1_MATCH in v.lower()]
    # UNCONFIRMED = the venue has *some* film on the target date. Worth shouting
    # about (3.1 km away) but must NOT stop the watch - same trap as SVYK on BMS.
    dc = res.get("dcinema") or {}
    cineluxe_open = bool(dc.get("ok") and dc.get("open_target"))
    return {"tier1": tier1, "near": near, "far": far, "dt1": dt1,
            "cineluxe_open": cineluxe_open,
            "any_other": bool(others) or district_only, "district_only": district_only}

def _times(shows):
    return ", ".join(s["t"] + (f" (Rs{int(float(s['min']))})" if s.get("min") else "")
                     for s in shows if s.get("t"))

def build_cineluxe(k):
    L = ["*Vinayaka Cineluxe (Marathahalli) just opened 23 Sep* - 3.1 km away", ""]
    L.append("_The venue now has shows on 23 Sep. District will not tell us WHICH film"
             " per date, so Paradise is NOT confirmed there yet._")
    L.append("")
    L.append(f"<{C.DISTRICT_CINEMA}|Check Vinayaka Cineluxe on District>")
    L.append("")
    L.append("*Still watching* - your BMS favourites and Paradise confirmation.")
    L.append(f"_{datetime.now(C.IST):%d %b %H:%M IST}_")
    return "\n".join(L)

def build_tier1(k):
    L = ["*THE PARADISE - 23 SEP - YOUR THEATRE IS OPEN* :tada:", ""]
    L.append("*>>> BOOK NOW <<<*")
    for nm in k.get("dt1", []):
        L.append(f"*{nm}*  _(District)_")
        L.append(f"  <{C.DISTRICT_CINEMA}|BOOK NOW>")
    for code, r in k["tier1"]:
        L.append(f"*{C.FAVS[code]}*")
        L.append(f"  {_times(r['shows'])}")
        if r.get("degraded"): L.append("  _(times via movie-wide API; venue page was blocked)_")
        L.append(f"  <{venue_link(code)}|BOOK NOW>")
    L.append("")
    if k["near"]:
        L.append(f"*Also open nearby (<={C.RADIUS_KM:g} km):*")
        for v in k["near"]:
            L.append(f"  *{v['name']}* - {v['km']} km: {', '.join(t for t in v['times'][:6] if t)}")
            L.append(f"    <{venue_link(v['code'])}|book>")
        L.append("")
    if k["far"]: L.append(f"_{len(k['far'])} more venue(s) further out._")
    L.append(f"<{BOOK_MOVIE}|Full BMS listing>")
    L.append(f"_{datetime.now(C.IST):%d %b %H:%M IST} - watch STOPPED, this is the last message_")
    return "\n".join(L)

def build_elsewhere(k):
    L = ["*23 Sep is OPEN in Bengaluru - but NOT your two theatres yet*", ""]
    L.append(f"*Still closed:* {' / '.join(C.FAVS[c].split(':')[0] for c in TIER1)}")
    L.append("")
    if k["district_only"]:
        L.append("_District says the 23rd opened; BMS is blocking us, so no venue list yet._")
    if k["near"]:
        L.append(f"*Open near you (<={C.RADIUS_KM:g} km):*")
        for v in k["near"]:
            L.append(f"  *{v['name']}* - {v['km']} km: {', '.join(t for t in v['times'][:6] if t)}")
            L.append(f"    <{venue_link(v['code'])}|book>")
        L.append("")
    if k["far"]:
        L.append(f"_{len(k['far'])} open further out: " +
                 ", ".join(f"{v['name'].split(':')[0]} ({v['km']}km)" for v in k["far"][:5]) + "_")
        L.append("")
    L.append("*Still watching for your two.* Next message = they opened, or a new one near you.")
    L.append(f"_{datetime.now(C.IST):%d %b %H:%M IST}_")
    return "\n".join(L)

def build_new_near(new):
    L = [f"*New theatre near you just opened for 23 Sep* ({len(new)})", ""]
    for v in new:
        L.append(f"*{v['name']}* - {v['km']} km "
                 f"(M {v['per']['Marathahalli']} / W {v['per']['Whitefield']})")
        L.append(f"  {', '.join(t for t in v['times'][:8] if t)}")
        L.append(f"  <{venue_link(v['code'])}|book>")
    L.append("")
    L.append("_Your two are still closed. Still watching._")
    L.append(f"_{datetime.now(C.IST):%d %b %H:%M IST}_")
    return "\n".join(L)

def send(text):
    hook = os.environ.get("GCHAT_WEBHOOK", "").strip()
    if not hook:
        print("--- NO GCHAT_WEBHOOK SET; message would have been ---"); print(text); return False
    req = urllib.request.Request(hook, data=json.dumps({"text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        print(f"  gchat -> {r.status}")
    return True

def disable_workflow(why):
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    wf = os.environ.get("WORKFLOW_FILE", "watch.yml")
    if not (tok and repo):
        print(f"  [local] would disable workflow ({why})"); return
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{wf}/disable",
        method="PUT", headers={"Authorization": f"Bearer {tok}",
                               "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            print(f"  workflow disabled ({why}) -> {r.status}")
    except Exception as e:
        print(f"  !! disable failed: {e}")

def main():
    s = load()
    now = datetime.now(C.IST)
    if s["fired"]:
        print("tier 1 already found; done"); disable_workflow("already fired"); return 0
    if now > C.DEADLINE:
        print(f"past deadline {C.DEADLINE:%d %b %H:%M IST}")
        if not s["deadline_notified"]:
            send(f"*Paradise watch done* - {C.DEADLINE:%d %b %H:%M IST} passed, "
                 f"your two theatres never opened for 23 Sep. No more messages.")
            s["deadline_notified"] = True; save(s)
        disable_workflow("deadline"); return 0

    res = C.main()
    s["runs"] += 1

    ok_flags = [bool((res.get("movie") or {}).get("ok")), bool(res["district"]["ok"])] + \
               [bool(r.get("ok")) for r in res["favs"].values()]
    if not any(ok_flags):
        s["fail_streak"] += 1
        print(f"  ALL SOURCES FAILED (streak {s['fail_streak']})")
        if s["fail_streak"] >= 3 and not s["notified_broken"]:
            send("*Paradise watch MONITOR BROKEN* - every source failed 3x. "
                 "Check by hand: " + BOOK_MOVIE)
            s["notified_broken"] = True
        save(s); return 1
    s["fail_streak"] = 0

    k = classify(res)

    # High-signal but unconfirmed: alert once, keep hunting.
    if k["cineluxe_open"] and not s["cineluxe_notified"] and not k["tier1"] and not k["dt1"]:
        print("  Vinayaka Cineluxe opened the 23rd (film unconfirmed) -> notifying")
        send(build_cineluxe(k)); s["cineluxe_notified"] = True; save(s)

    if k["tier1"] or k["dt1"]:                       # only these stop the watch
        print("  *** TIER 1 OPEN ***")
        send(build_tier1(k)); s["fired"] = True; save(s)
        disable_workflow("tier 1 found"); return 0

    if k["any_other"]:
        near_now = [v["code"] for v in k["near"]]
        if not s["elsewhere_notified"]:
            print("  open elsewhere (first time) -> notifying, still watching")
            send(build_elsewhere(k))
            s["elsewhere_notified"] = True
            s["notified_near"] = near_now
        else:
            new = [v for v in k["near"] if v["code"] not in s["notified_near"]]
            if new:
                print(f"  {len(new)} NEW nearby venue(s) -> notifying, still watching")
                send(build_new_near(new))
                s["notified_near"] = sorted(set(s["notified_near"]) | {v["code"] for v in new})
            else:
                print("  open elsewhere, nothing new near you -> silent")
    else:
        print(f"  run {s['runs']}: not open -> silent")

    save(s)
    return 0

if __name__ == "__main__":
    sys.exit(main())
