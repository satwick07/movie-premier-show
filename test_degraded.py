import check as C, alert as A
C.TARGET_BMS="20260924"; C.TARGET_ISO="2026-09-24"
res = C.main()
# simulate exactly what GitHub saw: VTGB's own page 403s
res["favs"]["VTGB"] = {"ok": False, "err": "http 403"}
fired, reasons = A.decide(res)
print(f"\nfired={fired}")
assert fired
vt = res["favs"]["VTGB"]
print("VTGB recovered via movie-wide:", vt.get("open"), "degraded:", vt.get("degraded"))
print("shows:", [s["t"] for s in vt["shows"]])
assert vt.get("open"), "FALLBACK FAILED - a 403 would mask a real opening"
print("\n--- reasons ---"); [print(" -", r) for r in reasons]
