#!/usr/bin/env python3
"""Sleep until the next 3-minute boundary in IST (:00, :03, :06 ...)."""
import datetime, time
STEP = 3
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
n = datetime.datetime.now(IST)
w = ((STEP - n.minute % STEP) % STEP) * 60 - n.second
if w <= 0:
    w += STEP * 60
tgt = n + datetime.timedelta(seconds=w)
print(f"aligning: sleep {w}s -> next check {tgt:%H:%M:%S} IST", flush=True)
time.sleep(w)
