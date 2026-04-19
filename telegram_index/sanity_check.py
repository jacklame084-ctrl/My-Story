#!/usr/bin/env python3
"""
Sanity-check the 777 transcripts:
  - corpus stats (word count, duration, confidence distributions)
  - detect problem files: English leak, repetition loops, empty, very low confidence
  - print stratified samples across memoir inflection periods
"""
import json
import re
import statistics
from pathlib import Path
from collections import Counter
from datetime import datetime

TDIR = Path("/Users/andreyposelskiy/My_Story/telegram_index/transcripts")

VOICE_FN_RE = re.compile(r"audio_(\d+)@(\d{2})-(\d{2})-(\d{4})_(\d{2})-(\d{2})-(\d{2})")


def parse_ts(name: str):
    m = VOICE_FN_RE.match(name)
    if not m:
        return None
    _, dd, mm, yyyy, h, mi, s = m.groups()
    return datetime(int(yyyy), int(mm), int(dd), int(h), int(mi), int(s))


def is_looping(text: str) -> bool:
    """Detect classic whisper repetition loops."""
    if len(text) < 40:
        return False
    # Check if any 15+ char substring repeats >3x
    for span in (20, 30, 50):
        for i in range(0, min(len(text) - span * 4, 200)):
            chunk = text[i:i + span]
            if chunk.strip() and text.count(chunk) >= 4:
                return True
    return False


def has_english_leak(text: str) -> bool:
    """Flag if a significant chunk is Latin-alphabet (suggests English leak)."""
    if not text:
        return False
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    cyrillic = sum(1 for c in text if "\u0400" <= c <= "\u04FF")
    total = latin + cyrillic
    if total < 20:
        return False
    return latin / total > 0.4


transcripts = sorted(TDIR.glob("*.json"))
print(f"Total transcript files: {len(transcripts)}")

stats = {
    "total_duration": 0.0,
    "total_words": 0,
    "empty": [],
    "looping": [],
    "english_leak": [],
    "low_conf": [],
    "very_short": [],
    "by_year": Counter(),
    "lang_counter": Counter(),
    "avg_logprobs": [],
    "no_speech_probs": [],
}

per_file = []
for p in transcripts:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  BAD JSON {p.name}: {e}")
        continue
    text = (d.get("text") or "").strip()
    segs = d.get("segments") or []
    source = d.get("source_file") or p.stem + ".ogg"
    ts = parse_ts(source)
    year = ts.year if ts else None
    duration = max((s.get("end") or 0) for s in segs) if segs else 0
    word_count = len(re.findall(r"[\wа-яА-ЯёЁ]+", text))
    lang = d.get("language") or ""
    stats["total_duration"] += duration
    stats["total_words"] += word_count
    stats["by_year"][year] += 1
    stats["lang_counter"][lang] += 1
    # confidence signals
    if segs:
        alp = [s.get("avg_logprob") for s in segs if s.get("avg_logprob") is not None]
        nsp = [s.get("no_speech_prob") for s in segs if s.get("no_speech_prob") is not None]
        if alp:
            stats["avg_logprobs"].append(statistics.mean(alp))
        if nsp:
            stats["no_speech_probs"].append(statistics.mean(nsp))
    # flags
    if not text:
        stats["empty"].append(source)
    if is_looping(text):
        stats["looping"].append(source)
    if has_english_leak(text):
        stats["english_leak"].append(source)
    if segs and statistics.mean([s.get("avg_logprob") or 0 for s in segs]) < -1.2:
        stats["low_conf"].append(source)
    if duration > 3 and word_count < 2:
        stats["very_short"].append(source)
    per_file.append({
        "source": source,
        "ts": ts.isoformat() if ts else None,
        "duration": round(duration, 1),
        "words": word_count,
        "text": text,
    })

print()
print("=" * 70)
print("CORPUS STATS")
print("=" * 70)
print(f"  total audio duration : {stats['total_duration']/3600:.2f} hours")
print(f"  total words          : {stats['total_words']:,}")
print(f"  language breakdown   : {dict(stats['lang_counter'])}")
print(f"  by year              : {dict(sorted(stats['by_year'].items(), key=lambda x: x[0] or 0))}")
if stats["avg_logprobs"]:
    vals = sorted(stats["avg_logprobs"])
    print(f"  avg_logprob median   : {statistics.median(vals):.3f}  (closer to 0 = higher confidence)")
    print(f"  avg_logprob p10      : {vals[len(vals)//10]:.3f}")
    print(f"  avg_logprob min      : {vals[0]:.3f}")

print()
print("=" * 70)
print("FLAGGED FILES")
print("=" * 70)
print(f"  empty transcripts              : {len(stats['empty'])}")
for f in stats["empty"][:5]:
    print(f"      - {f}")
print(f"  repetition loops               : {len(stats['looping'])}")
for f in stats["looping"][:5]:
    print(f"      - {f}")
print(f"  english leak                   : {len(stats['english_leak'])}")
for f in stats["english_leak"][:5]:
    print(f"      - {f}")
print(f"  low confidence (logprob<-1.2)  : {len(stats['low_conf'])}")
for f in stats["low_conf"][:5]:
    print(f"      - {f}")
print(f"  >3s audio but <2 words         : {len(stats['very_short'])}")
for f in stats["very_short"][:5]:
    print(f"      - {f}")

# Stratified samples across memoir periods
print()
print("=" * 70)
print("STRATIFIED SAMPLES  (5 files per period, first ~180 chars each)")
print("=" * 70)
periods = [
    ("2021-09 (beginning)",          datetime(2021, 9, 1),  datetime(2021, 9, 30)),
    ("2022-07-08 (Russia/Ukraine?)", datetime(2022, 7, 1),  datetime(2022, 8, 31)),
    ("2023-09-10 (mid-peak)",        datetime(2023, 9, 1),  datetime(2023, 10, 31)),
    ("2024-09 (pre-silence)",        datetime(2024, 9, 1),  datetime(2024, 10, 2)),
    ("2025-01 (reconnect)",          datetime(2025, 1, 1),  datetime(2025, 2, 28)),
]
per_file_sorted = sorted([p for p in per_file if p["ts"]], key=lambda x: x["ts"])
for label, a, b in periods:
    bucket = [p for p in per_file_sorted if a.isoformat() <= p["ts"] <= b.isoformat()]
    print(f"\n  --- {label}  (n={len(bucket)}) ---")
    # pick 5 evenly spaced
    step = max(1, len(bucket) // 5)
    for p in bucket[::step][:5]:
        snippet = (p["text"][:180] + "…") if len(p["text"]) > 180 else p["text"]
        print(f"    [{p['ts'][:16]} dur={p['duration']}s w={p['words']}] {snippet}")
