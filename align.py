#!/usr/bin/env python3
"""Sleep until the next IST minute ending in 4 (01:04, 01:14, 01:24 ...)."""
import datetime, sys, time
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
n = datetime.datetime.now(IST)
w = ((4 - n.minute) % 10) * 60 - n.second
if w <= 0:
    w += 600
tgt = n + datetime.timedelta(seconds=w)
print(f"aligning: sleep {w}s -> next check {tgt:%H:%M:%S} IST", flush=True)
time.sleep(w)
