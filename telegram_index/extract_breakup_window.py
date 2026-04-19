#!/usr/bin/env python3
"""
Extract the breakup window 2024-06-01 → 2024-10-02 (the last active day before
the 91-day silence) as one annotated document. Adds stage-direction lines
showing silence gaps, who-breaks-silence, volume, and flags the terminal
voice note and final message.

Output: breakup_window.md
"""
import csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

OUT = Path("/Users/andreyposelskiy/My_Story/telegram_index")
CSV_PATH = OUT / "unified_timeline.csv"
csv.field_size_limit(10_000_000)

USER = "Chief Garvey"
HER = "leeeroy"

WINDOW_START = datetime(2024, 6, 1)
WINDOW_END = datetime(2024, 10, 3)  # inclusive through end of Oct 2

rows = []
with CSV_PATH.open(encoding="utf-8") as f:
    r = csv.DictReader(f)
    for d in r:
        dt = datetime.fromisoformat(d["datetime"])
        if WINDOW_START <= dt < WINDOW_END and d["sender"] in {USER, HER}:
            d["dt"] = dt
            rows.append(d)
rows.sort(key=lambda x: x["dt"])

print(f"Window rows: {len(rows)}")

# Aggregate
by_day = {}
for r in rows:
    day = r["dt"].date()
    by_day.setdefault(day, []).append(r)
active_days = sorted(by_day.keys())

# Find last voice note in window
last_voice = None
for r in rows:
    if r["type"] == "voice":
        last_voice = r

md = []
md.append("# The Breakup Window — 2024-06-01 through 2024-10-02\n")
md.append(f"*{len(rows):,} messages across {len(active_days)} active days — the 123-day arc from the start of the fade to the last message before the 91-day silence.*\n")
md.append("*Stage directions in italics were inserted during analysis. Everything else is verbatim.*\n")
md.append("\n---\n")

# Orientation: month-level
md.append("## Orientation\n")
month_counts = Counter(r["dt"].strftime("%Y-%m") for r in rows)
month_voice = Counter(r["dt"].strftime("%Y-%m") for r in rows if r["type"] == "voice")
month_users = Counter((r["dt"].strftime("%Y-%m"), r["sender"]) for r in rows)
md.append("| Month | msgs | voice notes | you | her |")
md.append("|---|---|---|---|---|")
for ym in sorted(month_counts.keys()):
    md.append(f"| {ym} | {month_counts[ym]} | {month_voice.get(ym, 0)} | {month_users.get((ym, USER), 0)} | {month_users.get((ym, HER), 0)} |")
md.append("")

md.append(f"**The last voice note of the relationship** comes on **{last_voice['dt'].date()} at {last_voice['dt'].strftime('%H:%M')}** — from **{last_voice['sender']}**. "
          f"Marked below with ⚑ when it appears.\n")
md.append("\n---\n\n")

# Walk days
VOICE_ICON = "🎙"
TERMINAL_VOICE_ICON = "⚑🎙"
prev_day = None
for day in active_days:
    msgs = by_day[day]
    # Gap annotation
    if prev_day is not None:
        gap = (day - prev_day).days
        if gap > 1:
            md.append(f"\n> *{gap-1} day silence.*\n")
    # Day header with volume and initiator
    first_msg = msgs[0]
    senders = Counter(m["sender"] for m in msgs)
    volume_note = f"{len(msgs)} msgs  —  {USER}: {senders.get(USER, 0)}  |  {HER}: {senders.get(HER, 0)}"
    md.append(f"\n## {day.strftime('%A, %Y-%m-%d')}\n")
    md.append(f"> *{volume_note}. {first_msg['sender']} opens at {first_msg['dt'].strftime('%H:%M')}.*\n")
    # Messages
    for r in msgs:
        hm = r["dt"].strftime("%H:%M")
        sender = r["sender"]
        typ = r["type"]
        if typ == "text":
            body = (r["text"] or "(empty)").replace("  ⏎  ", "\n    ")
            md.append(f"**{hm}** `{sender}`: {body}")
        elif typ == "voice":
            icon = TERMINAL_VOICE_ICON if last_voice and r["dt"] == last_voice["dt"] else VOICE_ICON
            dur = f" [{r['duration']}]" if r["duration"] else ""
            if r["text"]:
                body = r["text"].replace("  ⏎  ", " ")
                md.append(f"**{hm}** `{sender}` {icon}{dur}: *{body}*")
            else:
                md.append(f"**{hm}** `{sender}` {icon}{dur}: _(no transcript)_")
        elif typ == "sticker":
            md.append(f"**{hm}** `{sender}`  _[sticker]_")
        elif typ == "photo":
            md.append(f"**{hm}** `{sender}`  _[photo]_")
        elif typ == "video":
            md.append(f"**{hm}** `{sender}`  _[video]_")
        elif typ == "file":
            md.append(f"**{hm}** `{sender}`  _[file]_")
        else:
            md.append(f"**{hm}** `{sender}`  _[{typ}]_")
        md.append("")
    prev_day = day

# Terminal note
last_msg = rows[-1]
md.append("\n---\n")
md.append("## The last thing said\n")
last_body = last_msg['text'][:400] if last_msg['text'] else f"[{last_msg['type']}]"
md.append(f"> **{last_msg['dt'].strftime('%Y-%m-%d %H:%M')}  —  {last_msg['sender']}:**\n>\n> {last_body}\n")
md.append("\nThen 91 days of nothing.\n")
md.append("\nNext message: **2025-01-01 at 16:38**, from you:\n")
md.append("> *Лера привет. Я знаю что ты просила меня тебе не писать, но...*\n")

(OUT / "breakup_window.md").write_text("\n".join(md), encoding="utf-8")
print(f"Wrote breakup_window.md ({sum(len(l) for l in md):,} chars)")
