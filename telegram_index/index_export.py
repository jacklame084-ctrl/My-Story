#!/usr/bin/env python3
"""
Index a Telegram HTML export + voice-note directory into timeline CSVs/JSON.
Outputs:
  - per_file.json   : list of {file, first_date, last_date, counts, senders}
  - messages.csv    : one row per message {date, sender, type, chars, file}
  - voice_notes.csv : one row per voice file {date, time, filename, seconds?}
  - timeline_daily.csv : merged daily aggregates {date, text_msgs, voice_msgs, senders}
"""
import os
import re
import csv
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

EXPORT = Path("/Users/andreyposelskiy/Downloads/Telegram Desktop/ChatExport_2026-04-18")
OUT = Path("/Users/andreyposelskiy/My_Story/telegram_index")
OUT.mkdir(parents=True, exist_ok=True)

# --- HTML parsing -----------------------------------------------------------
MSG_RE = re.compile(
    r'<div class="message (default clearfix(?: joined)?|service)"[^>]*id="message(\d+)"[^>]*>(.*?)(?=<div class="message |</div>\s*</div>\s*</div>\s*</body>|$)',
    re.DOTALL,
)
DATE_RE = re.compile(r'class="pull_right date details" title="([^"]+)"')
FROM_RE = re.compile(r'<div class="from_name">\s*([^<\n]+?)\s*(?:<|\n)')
TEXT_RE = re.compile(r'<div class="text">\s*(.*?)\s*</div>', re.DOTALL)
VOICE_RE = re.compile(r'class="[^"]*media_voice_message')
PHOTO_RE = re.compile(r'class="[^"]*media_photo')
FILE_RE = re.compile(r'class="[^"]*media_file')
STICKER_RE = re.compile(r'class="[^"]*media_sticker|class="sticker"')
VIDEO_RE = re.compile(r'class="[^"]*media_video')


def parse_dt(s: str):
    # "26.08.2021 16:04:51 UTC+03:00"
    try:
        return datetime.strptime(s[:19], "%d.%m.%Y %H:%M:%S")
    except Exception:
        return None


def classify(block: str) -> str:
    if VOICE_RE.search(block):
        return "voice"
    if STICKER_RE.search(block):
        return "sticker"
    if PHOTO_RE.search(block):
        return "photo"
    if VIDEO_RE.search(block):
        return "video"
    if FILE_RE.search(block):
        return "file"
    if TEXT_RE.search(block):
        return "text"
    return "other"


def parse_html(path: Path):
    html = path.read_text(encoding="utf-8", errors="replace")
    # Split on message divs more simply: use regex to find message blocks
    # Cheap approach: split by the div opener and iterate.
    parts = re.split(r'(<div class="message (?:default clearfix(?: joined)?|service)"[^>]*>)', html)
    # parts is [pre, opener1, body1, opener2, body2, ...]
    msgs = []
    current_sender = None
    for i in range(1, len(parts), 2):
        opener = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        is_joined = "joined" in opener
        is_service = 'service"' in opener
        if is_service:
            # Skip service messages (date separators, etc.) for aggregation
            continue
        dm = DATE_RE.search(body)
        if not dm:
            continue
        dt = parse_dt(dm.group(1))
        if not dt:
            continue
        fm = FROM_RE.search(body)
        if fm:
            current_sender = fm.group(1).strip()
        sender = current_sender or "unknown"
        typ = classify(body)
        chars = 0
        if typ == "text":
            tm = TEXT_RE.search(body)
            if tm:
                raw = re.sub(r"<[^>]+>", " ", tm.group(1))
                raw = re.sub(r"\s+", " ", raw).strip()
                chars = len(raw)
        msgs.append((dt, sender, typ, chars))
    return msgs


def index_html_files():
    per_file = []
    all_msgs_rows = []
    html_files = sorted(
        EXPORT.glob("messages*.html"),
        key=lambda p: int(re.search(r"messages(\d*)\.html", p.name).group(1) or "1"),
    )
    for p in html_files:
        msgs = parse_html(p)
        if not msgs:
            per_file.append({"file": p.name, "first_date": None, "last_date": None, "count": 0})
            continue
        first = min(m[0] for m in msgs)
        last = max(m[0] for m in msgs)
        type_counts = Counter(m[2] for m in msgs)
        sender_counts = Counter(m[1] for m in msgs)
        per_file.append({
            "file": p.name,
            "first_date": first.isoformat(),
            "last_date": last.isoformat(),
            "count": len(msgs),
            "types": dict(type_counts),
            "senders": dict(sender_counts),
        })
        for dt, sender, typ, chars in msgs:
            all_msgs_rows.append([dt.isoformat(), sender, typ, chars, p.name])
        print(f"  {p.name}: {len(msgs)} msgs, {first.date()} → {last.date()}", flush=True)

    (OUT / "per_file.json").write_text(json.dumps(per_file, indent=2, ensure_ascii=False))
    with (OUT / "messages.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["datetime", "sender", "type", "chars", "file"])
        w.writerows(all_msgs_rows)
    print(f"[html] wrote {len(all_msgs_rows)} message rows across {len(per_file)} files")
    return all_msgs_rows


# --- Voice-filename parsing --------------------------------------------------
VOICE_FN_RE = re.compile(r"audio_(\d+)@(\d{2})-(\d{2})-(\d{4})_(\d{2})-(\d{2})-(\d{2})\.ogg")


def index_voice_filenames():
    vdir = EXPORT / "voice_messages"
    rows = []
    for f in sorted(vdir.iterdir()):
        m = VOICE_FN_RE.match(f.name)
        if not m:
            continue
        _, dd, mm, yyyy, h, mi, s = m.groups()
        dt = datetime(int(yyyy), int(mm), int(dd), int(h), int(mi), int(s))
        rows.append([dt.isoformat(), f.name, f.stat().st_size])
    rows.sort()
    with (OUT / "voice_notes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["datetime", "filename", "size_bytes"])
        w.writerows(rows)
    print(f"[voice] indexed {len(rows)} voice notes, "
          f"{rows[0][0][:10]} → {rows[-1][0][:10]}")
    return rows


# --- Daily merge ------------------------------------------------------------
def daily_merge(msg_rows, voice_rows):
    # msg_rows: [dt_iso, sender, type, chars, file]
    # voice_rows: [dt_iso, filename, size]
    by_day = defaultdict(lambda: {"text": 0, "voice_text": 0, "photo": 0, "other": 0,
                                    "senders": Counter(), "voice_notes": 0})
    for dt_iso, sender, typ, chars, _ in msg_rows:
        d = dt_iso[:10]
        if typ == "text":
            by_day[d]["text"] += 1
        elif typ == "voice":
            by_day[d]["voice_text"] += 1  # voice note referenced in chat
        elif typ == "photo":
            by_day[d]["photo"] += 1
        else:
            by_day[d]["other"] += 1
        by_day[d]["senders"][sender] += 1
    for dt_iso, _, _ in voice_rows:
        d = dt_iso[:10]
        by_day[d]["voice_notes"] += 1

    days = sorted(by_day.keys())
    with (OUT / "timeline_daily.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "text_msgs", "voice_chat_refs", "voice_files", "photo", "other", "top_sender", "total_msgs"])
        for d in days:
            b = by_day[d]
            total = b["text"] + b["voice_text"] + b["photo"] + b["other"]
            top = b["senders"].most_common(1)
            w.writerow([d, b["text"], b["voice_text"], b["voice_notes"], b["photo"], b["other"],
                        top[0][0] if top else "", total])
    print(f"[merge] wrote {len(days)} daily rows → timeline_daily.csv")


if __name__ == "__main__":
    print("Indexing HTML...", flush=True)
    msgs = index_html_files()
    print("Indexing voice filenames...", flush=True)
    voices = index_voice_filenames()
    print("Merging daily timeline...", flush=True)
    daily_merge(msgs, voices)
    print("Done.")
