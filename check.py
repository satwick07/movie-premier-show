#!/usr/bin/env python3
"""Watch for 23-Sep-2026 shows of The Paradise (Telugu) near Marathahalli/Whitefield."""
import json, math, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone

EVENT      = "ET00436621"          # The Paradise, Telugu child event
TARGET_BMS = "20260923"
TARGET_ISO = "2026-09-23"
IST        = timezone(timedelta(hours=5, minutes=30))
DEADLINE   = datetime(2026, 9, 22, 22, 0, tzinfo=IST)
DISTRICT   = "https://www.district.in/movies/the-paradise-movie-tickets-in-bengaluru-MV185027"
TELUGU_FMT = "sfuykkkg9p"
ANCHORS    = {"Marathahalli": (12.9591, 77.6974), "Whitefield": (12.9698, 77.7500)}
FAVS       = {"VTGB": "V Cinema (Vijayalakshmi): Garudacharpalya",
              "SVYK": "Sri Vinayaka Cinemas 4K: Varthur"}
RADIUS_KM  = float(os.environ.get("RADIUS_KM", "6"))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

def km(lat1, lon1, lat2, lon2):
    R, p = 6371.0, math.radians
    h = (math.sin(p(lat2-lat1)/2)**2 +
         math.cos(p(lat1))*math.cos(p(lat2))*math.sin(p(lon2-lon1)/2)**2)
    return 2*R*math.asin(math.sqrt(h))

def nearest(lat, lon):
    d = {k: km(v[0], v[1], lat, lon) for k, v in ANCHORS.items()}
    return min(d.values()), d

def walk(o):
    """Yield every dict nested anywhere in o."""
    if isinstance(o, dict):
        yield o
        for v in o.values(): yield from walk(v)
    elif isinstance(o, list):
        for v in o: yield from walk(v)

# ---------- source 1: BMS per-venue page (sharpest, used for favourites) ----------
def bms_venue(sess, code):
    url = f"https://in.bookmyshow.com/cinemas/BANG/x/buytickets/{code}/{TARGET_BMS}"
    r = sess.get(url, timeout=30, allow_redirects=True)
    if r.status_code != 200:
        return {"ok": False, "err": f"http {r.status_code}"}
    # BMS redirects away from a date it does not serve -> hard negative
    if TARGET_BMS not in str(r.url).rsplit("/", 1)[-1]:
        return {"ok": True, "open": False, "why": "redirected"}
    m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*</script>', r.text, re.S)
    if not m:
        return {"ok": False, "err": "no __INITIAL_STATE__"}
    try:
        state = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        return {"ok": False, "err": f"state json: {e}"}
    queries = state.get("venueShowtimesFunctionalApi", {}).get("queries", {})
    # the date is baked into the key, so a clamped page cannot match
    node = queries.get(f"getShowtimesByVenue-{code}-{TARGET_BMS}")
    if node is None:
        return {"ok": True, "open": False, "why": "no key for target date"}
    for ev in walk(node):
        if ev.get("EventCode") == EVENT:
            st = ev.get("ShowTimes") or []
            if st:
                return {"ok": True, "open": True,
                        "shows": [{"t": s.get("ShowTime"), "avail": s.get("AvailStatus"),
                                   "min": s.get("MinPrice")} for s in st if isinstance(s, dict)]}
    return {"ok": True, "open": False, "why": "venue open, no Paradise sessions"}

# ---------- source 2: BMS movie-wide API (discovers NEW venues, incl. PVR) ----------
def bms_movie(sess):
    url = ("https://in.bookmyshow.com/api/movies-data/showtimes-by-event"
           f"?appCode=MOBAND2&appVersion=14304&language=en&eventCode={EVENT}"
           "&regionCode=BANG&subRegion=BANG&bmsId=1.0&token=67x1xa33b4x422b361ba7d8"
           f"&lat=12.971599&lon=77.594566&query=&dateCode={TARGET_BMS}")
    r = sess.get(url, timeout=30)
    if r.status_code != 200: return {"ok": False, "err": f"http {r.status_code}"}
    try: d = r.json()
    except Exception as e: return {"ok": False, "err": f"json: {e}"}
    if "ShowDatesArray" not in d: return {"ok": False, "err": "schema drift"}
    strip = [(x.get("Date"), x.get("isDisabled")) for x in d["ShowDatesArray"]]
    has23 = any(str(dt) == "23" and not dis for dt, dis in strip)
    blocks = [b for b in d.get("ShowDetails", []) if str(b.get("Date")) == TARGET_BMS]
    venues = []
    for b in blocks:
        for v in b.get("Venues", []):
            if v.get("SubRegCode") != "BANG":      # hard Bengaluru assertion
                continue
            st = [s for s in v.get("ShowTimes", []) if str(s.get("ShowDateCode")) == TARGET_BMS]
            if not st: continue
            try: lat, lon = float(v["Lat"]), float(v["Lng"])
            except Exception: continue
            dist, per = nearest(lat, lon)
            venues.append({"name": v.get("VenueName"), "code": v.get("VenueCode"),
                           "km": round(dist, 1), "per": {k: round(x, 1) for k, x in per.items()},
                           "times": [s.get("ShowTime") for s in st]})
    venues.sort(key=lambda x: x["km"])
    return {"ok": True, "strip": strip, "has23": has23,
            "served_target": bool(blocks), "venues": venues}

# ---------- source 3: District (no bot protection, zero deps) ----------
def district():
    try:
        req = urllib.request.Request(DISTRICT, headers={"User-Agent": UA})
        b = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', b, re.S)
        d = json.loads(m.group(1))
        pp = d["props"]["pageProps"]
        city = pp["data"]["cityName"]
        dates = pp["data"]["serverState"]["movieSessions"][TELUGU_FMT]["meta"]["showDates"]
        return {"ok": True, "city": city, "dates": dates,
                "open": TARGET_ISO in dates and city == "bengaluru"}
    except Exception as e:
        return {"ok": False, "err": f"{type(e).__name__}: {e}"}

def main():
    now = datetime.now(IST)
    print(f"[{now:%Y-%m-%d %H:%M:%S %Z}] deadline {DEADLINE:%d %b %H:%M} "
          f"({(DEADLINE-now).total_seconds()/3600:+.1f}h)")
    try:
        from curl_cffi import requests as cr
        sess = cr.Session(impersonate="chrome")
        have_bms = True
    except ImportError:
        sess, have_bms = None, False
        print("  ! curl_cffi missing - BMS sources skipped")

    res = {"favs": {}, "movie": None, "district": district()}
    if have_bms:
        for code, label in FAVS.items():
            res["favs"][code] = bms_venue(sess, code)
            r = res["favs"][code]
            flag = "*** OPEN ***" if r.get("open") else ("ERR " + r.get("err", "") if not r["ok"] else "closed")
            print(f"  fav {code} {label[:38]:<38} {flag} {r.get('why','')}")
            if r.get("shows"): print("       ", [s["t"] for s in r["shows"]])
        res["movie"] = bms_movie(sess)
        mv = res["movie"]
        if mv["ok"]:
            print(f"  movie-wide: date strip {mv['strip']}")
            print(f"              has23={mv['has23']} served_target={mv['served_target']} "
                  f"venues_on_23={len(mv['venues'])}")
        else:
            print(f"  movie-wide: ERR {mv['err']}")
    dd = res["district"]
    print(f"  district: {'showDates=' + str(dd['dates']) if dd['ok'] else 'ERR ' + dd['err']}")
    print(json.dumps({"fired": False}, indent=0) if False else "")
    json.dump(res, open("last_result.json", "w"), indent=1)
    return res

if __name__ == "__main__":
    main()
