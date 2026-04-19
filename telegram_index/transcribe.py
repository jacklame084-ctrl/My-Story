#!/usr/bin/env python3
"""
Transcribe all voice notes with mlx_whisper large-v3 (Russian).
Loads model once, iterates. Resumable: skips files whose .json output already exists.
Writes progress to transcribe.log.
"""
import re
import sys
import json
import time
from pathlib import Path
from datetime import datetime

import mlx_whisper

EXPORT = Path("/Users/andreyposelskiy/Downloads/Telegram Desktop/ChatExport_2026-04-18")
VDIR = EXPORT / "voice_messages"
OUT = Path("/Users/andreyposelskiy/My_Story/telegram_index/transcripts")
OUT.mkdir(parents=True, exist_ok=True)
LOG = Path("/Users/andreyposelskiy/My_Story/telegram_index/transcribe.log")

MODEL = "mlx-community/whisper-large-v3-mlx"
LANG = "ru"

VOICE_FN_RE = re.compile(r"audio_(\d+)@(\d{2})-(\d{2})-(\d{4})_(\d{2})-(\d{2})-(\d{2})\.ogg")


def key(p: Path):
    m = VOICE_FN_RE.match(p.name)
    if not m:
        return (datetime.max, p.name)
    _, dd, mm, yyyy, h, mi, s = m.groups()
    return (datetime(int(yyyy), int(mm), int(dd), int(h), int(mi), int(s)), p.name)


def log(msg: str):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def main():
    files = sorted(VDIR.glob("*.ogg"), key=key)
    total = len(files)
    log(f"START  {total} files  model={MODEL}  lang={LANG}")
    start = time.time()
    done = 0
    skipped = 0
    failed = 0

    for i, f in enumerate(files, 1):
        out_json = OUT / (f.stem + ".json")
        if out_json.exists() and out_json.stat().st_size > 0:
            skipped += 1
            continue
        t0 = time.time()
        try:
            result = mlx_whisper.transcribe(
                str(f),
                path_or_hf_repo=MODEL,
                language=LANG,
                word_timestamps=True,
                verbose=None,
            )
            # Drop tokens to keep file size reasonable; keep text, segments, words, timestamps.
            slim = {
                "language": result.get("language"),
                "text": result.get("text"),
                "segments": [
                    {
                        "id": s.get("id"),
                        "start": s.get("start"),
                        "end": s.get("end"),
                        "text": s.get("text"),
                        "avg_logprob": s.get("avg_logprob"),
                        "no_speech_prob": s.get("no_speech_prob"),
                        "compression_ratio": s.get("compression_ratio"),
                        "words": s.get("words"),
                    }
                    for s in result.get("segments", [])
                ],
                "source_file": f.name,
            }
            out_json.write_text(json.dumps(slim, ensure_ascii=False, indent=1))
            dt = time.time() - t0
            done += 1
            elapsed = time.time() - start
            rate = done / elapsed if done else 0
            remaining = total - skipped - done - failed
            eta_h = (remaining / rate) / 3600 if rate else 0
            if i % 5 == 0 or i < 20:
                log(f"OK    [{i}/{total}]  {f.name}  {dt:.1f}s  done={done} skip={skipped} fail={failed}  ETA~{eta_h:.1f}h")
        except KeyboardInterrupt:
            log("INTERRUPTED by user")
            raise
        except Exception as e:
            failed += 1
            log(f"FAIL  [{i}/{total}]  {f.name}  {type(e).__name__}: {e}")

    log(f"END  done={done} skip={skipped} fail={failed}  total_time={(time.time()-start)/3600:.2f}h")


if __name__ == "__main__":
    main()
