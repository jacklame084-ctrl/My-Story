#!/usr/bin/env python3
"""
Build the unified chronological timeline.
Merges text messages (from HTML) with voice-note transcripts (from transcripts/).
Outputs:
  unified_timeline.csv       — one row per message (queryable)
  by_month/YYYY-MM.md        — readable monthly chunks
  unified_stats.json         — aggregate stats
"""
import re
import csv
import json
import html
from pathlib import Path
from datetime import datetime
from collections import defaultdict

EXPORT = Path("/Users/andreyposelskiy/Downloads/Telegram Desktop/ChatExport_2026-04-18")
TDIR = Path("/Users/andreyposelskiy/My_Story/telegram_index/transcripts")
OUT = Path("/Users/andreyposelskiy/My_Story/telegram_index")
MD_DIR = OUT / "by_month"
MD_DIR.mkdir(exist_ok=True)

DATE_RE = re.compile(r'class="pull_right date details" title="([^"]+)"')
FROM_RE = re.compile(r'<div class="from_name">\s*([^<\n]+?)\s*(?:<|\n)')
TEXT_RE = re.compile(r'<div class="text">\s*(.*?)\s*</div>', re.DOTALL)
VOICE_HREF_RE = re.compile(r'href="voice_messages/(audio_\d+@[^"]+\.ogg)"[^>]*class="[^"]*media_voice_message|class="[^"]*media_voice_message[^"]*"[^>]*href="voice_messages/(audio_\d+@[^"]+\.ogg)"')
VOICE_HREF_RE2 = re.compile(r'class="[^"]*media_voice_message[^"]*"\s+href="voice_messages/([^"]+\.ogg)"')
VOICE_DURATION_RE = re.compile(r'media_voice_message.*?<div class="status details">\s*(\d+:\d+)', re.DOTALL)
PHOTO_RE = re.compile(r'class="[^"]*media_photo')
VIDEO_RE = re.compile(r'class="[^"]*media_video')
FILE_RE = re.compile(r'class="[^"]*media_file')
STICKER_RE = re.compile(r'class="[^"]*media_sticker|class="sticker"')


def parse_dt(s: str):
    try:
        return datetime.strptime(s[:19], "%d.%m.%Y %H:%M:%S")
    except Exception:
        return None


def classify_and_voice(block: str):
    # Returns (type, voice_filename_or_None, duration_or_None)
    m = VOICE_HREF_RE2.search(block)
    if m:
        dur_m = VOICE_DURATION_RE.search(block)
        return ("voice", m.group(1), dur_m.group(1) if dur_m else None)
    if STICKER_RE.search(block):
        return ("sticker", None, None)
    if PHOTO_RE.search(block):
        return ("photo", None, None)
    if VIDEO_RE.search(block):
        return ("video", None, None)
    if FILE_RE.search(block):
        return ("file", None, None)
    if TEXT_RE.search(block):
        return ("text", None, None)
    return ("other", None, None)


def clean_text(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n+", "\n", s)
    return s.strip()


# Load voice transcripts keyed by filename
print("Loading voice transcripts...", flush=True)
voice_text = {}
for p in TDIR.glob("*.json"):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        voice_text[p.stem + ".ogg"] = (d.get("text") or "").strip()
    except Exception:
        pass
print(f"  {len(voice_text)} transcripts indexed")


def parse_html(path: Path):
    html_str = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r'(<div class="message (?:default clearfix(?: joined)?|service)"[^>]*>)', html_str)
    current_sender = None
    for i in range(1, len(parts), 2):
        opener = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if 'service"' in opener:
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
        typ, voice_file, duration = classify_and_voice(body)
        if typ == "text":
            tm = TEXT_RE.search(body)
            content = clean_text(tm.group(1)) if tm else ""
        elif typ == "voice":
            content = voice_text.get(voice_file, "") if voice_file else ""
        else:
            content = ""
        yield {
            "datetime": dt,
            "sender": sender,
            "type": typ,
            "text": content,
            "voice_file": voice_file,
            "duration": duration,
            "source_html": path.name,
        }


# Walk all HTML files in order
html_files = sorted(
    EXPORT.glob("messages*.html"),
    key=lambda p: int(re.search(r"messages(\d*)\.html", p.name).group(1) or "1"),
)

print(f"Walking {len(html_files)} HTML files...", flush=True)
all_rows = []
for p in html_files:
    n_before = len(all_rows)
    for row in parse_html(p):
        all_rows.append(row)
    print(f"  {p.name}: +{len(all_rows) - n_before}", flush=True) if False else None

print(f"Total rows: {len(all_rows)}")

# Sort chronologically (should already be mostly sorted but guarantee)
all_rows.sort(key=lambda r: r["datetime"])

# CSV output
csv_path = OUT / "unified_timeline.csv"
with csv_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["datetime", "sender", "type", "voice_file", "duration", "text", "source_html"])
    for r in all_rows:
        w.writerow([
            r["datetime"].isoformat(),
            r["sender"],
            r["type"],
            r["voice_file"] or "",
            r["duration"] or "",
            r["text"].replace("\n", "  ⏎  "),
            r["source_html"],
        ])
print(f"Wrote {csv_path}")

# Markdown per-month
print("Writing monthly markdown files...")
by_month = defaultdict(list)
for r in all_rows:
    by_month[r["datetime"].strftime("%Y-%m")].append(r)

VOICE_BADGE = "🎙"
for ym, rows in sorted(by_month.items()):
    path = MD_DIR / f"{ym}.md"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# {ym}  ({len(rows)} messages)\n\n")
        current_day = None
        for r in rows:
            day = r["datetime"].strftime("%Y-%m-%d")
            if day != current_day:
                f.write(f"\n## {day}\n\n")
                current_day = day
            hm = r["datetime"].strftime("%H:%M")
            sender = r["sender"]
            typ = r["type"]
            if typ == "text":
                body = r["text"] or "(empty)"
                f.write(f"**{hm}** `{sender}`: {body}\n\n")
            elif typ == "voice":
                dur = f" [{r['duration']}]" if r["duration"] else ""
                if r["text"]:
                    f.write(f"**{hm}** `{sender}` {VOICE_BADGE}{dur}: *{r['text']}*\n\n")
                else:
                    f.write(f"**{hm}** `{sender}` {VOICE_BADGE}{dur}: _(no transcript)_\n\n")
            elif typ == "sticker":
                f.write(f"**{hm}** `{sender}`  _[sticker]_\n\n")
            elif typ == "photo":
                f.write(f"**{hm}** `{sender}`  _[photo]_\n\n")
            elif typ == "video":
                f.write(f"**{hm}** `{sender}`  _[video]_\n\n")
            elif typ == "file":
                f.write(f"**{hm}** `{sender}`  _[file]_\n\n")
            else:
                f.write(f"**{hm}** `{sender}`  _[{typ}]_\n\n")

print(f"Wrote {len(by_month)} monthly .md files")

# Stats
stats = {
    "total_rows": len(all_rows),
    "by_type": {},
    "by_sender": {},
    "voice_with_transcript": sum(1 for r in all_rows if r["type"] == "voice" and r["text"]),
    "voice_without_transcript": sum(1 for r in all_rows if r["type"] == "voice" and not r["text"]),
    "first": all_rows[0]["datetime"].isoformat() if all_rows else None,
    "last": all_rows[-1]["datetime"].isoformat() if all_rows else None,
}
from collections import Counter
stats["by_type"] = dict(Counter(r["type"] for r in all_rows))
stats["by_sender"] = dict(Counter(r["sender"] for r in all_rows))
(OUT / "unified_stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
print(json.dumps(stats, indent=2, ensure_ascii=False))
