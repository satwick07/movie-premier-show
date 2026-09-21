"""Exercise the FIRE path against real live data by retargeting to 24 Sep (which IS open)."""
import check as C, alert as A
C.TARGET_BMS = "20260924"; C.TARGET_ISO = "2026-09-24"
A.BOOK_MOVIE = A.BOOK_MOVIE.replace("20260923", "20260924")
res = C.main()
fired, reasons = A.decide(res)
print(f"\n==== fired={fired} ====\n")
assert fired, "FIRE PATH BROKEN: 24 Sep is open but decide() returned False"
msg = A.build_alert(res, reasons)
print(msg)
print(f"\n[message length {len(msg)} chars]")
