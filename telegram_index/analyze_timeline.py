#!/usr/bin/env python3
"""Emotional-weather analysis over the daily timeline."""
import csv
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta

OUT = Path("/Users/andreyposelskiy/My_Story/telegram_index")

rows = []
with (OUT / "timeline_daily.csv").open(encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        row["text_msgs"] = int(row["text_msgs"])
        row["voice_chat_refs"] = int(row["voice_chat_refs"])
        row["voice_files"] = int(row["voice_files"])
        row["photo"] = int(row["photo"])
        row["total_msgs"] = int(row["total_msgs"])
        rows.append(row)

by_date = {r["date"]: r for r in rows}

# Monthly aggregate
monthly = defaultdict(lambda: {"msgs": 0, "voices": 0, "active_days": 0})
for r in rows:
    ym = r["date"][:7]
    monthly[ym]["msgs"] += r["total_msgs"]
    monthly[ym]["voices"] += r["voice_files"]
    monthly[ym]["active_days"] += 1

print("=" * 70)
print("MONTHLY TIMELINE  (msgs | voice-notes | active-days)")
print("=" * 70)
for ym in sorted(monthly.keys()):
    m = monthly[ym]
    bar = "█" * min(60, m["msgs"] // 50)
    print(f"  {ym}   {m['msgs']:>5}  v:{m['voices']:>3}  d:{m['active_days']:>2}  {bar}")

# Top-20 spike days
print()
print("=" * 70)
print("TOP-20 SPIKE DAYS  (highest total message count)")
print("=" * 70)
for r in sorted(rows, key=lambda x: -x["total_msgs"])[:20]:
    print(f"  {r['date']}  total={r['total_msgs']:>4}  text={r['text_msgs']:>4}  voice={r['voice_files']:>3}  photos={r['photo']:>3}")

# Top-20 voice-heavy days
print()
print("=" * 70)
print("TOP-20 VOICE-NOTE-HEAVY DAYS")
print("=" * 70)
for r in sorted(rows, key=lambda x: -x["voice_files"])[:20]:
    if r["voice_files"] == 0:
        break
    print(f"  {r['date']}  voices={r['voice_files']:>3}  total_msgs={r['total_msgs']:>4}")

# Longest silences (gaps between consecutive active days)
print()
print("=" * 70)
print("TOP-15 LONGEST SILENCES  (gaps between active days)")
print("=" * 70)
dates_sorted = sorted(date.fromisoformat(r["date"]) for r in rows)
gaps = []
for i in range(1, len(dates_sorted)):
    d = (dates_sorted[i] - dates_sorted[i - 1]).days
    if d > 1:
        gaps.append((d, dates_sorted[i - 1], dates_sorted[i]))
gaps.sort(reverse=True)
for g, a, b in gaps[:15]:
    print(f"  {g:>3} days silent   {a}  →  {b}")

# Total voice notes per known memoir window
print()
print("=" * 70)
print("VOICE NOTES BY YEAR")
print("=" * 70)
by_year = defaultdict(int)
for r in rows:
    by_year[r["date"][:4]] += r["voice_files"]
for y in sorted(by_year):
    print(f"  {y}: {by_year[y]}")

# First / last message
print()
print("=" * 70)
print("SPAN")
print("=" * 70)
print(f"  first day:  {min(by_date.keys())}")
print(f"  last day:   {max(by_date.keys())}")
print(f"  total active days:  {len(rows)}")
print(f"  total messages:     {sum(r['total_msgs'] for r in rows)}")
print(f"  total voice files:  {sum(r['voice_files'] for r in rows)}")
