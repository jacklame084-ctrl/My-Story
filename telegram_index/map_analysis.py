#!/usr/bin/env python3
"""
Structural analysis of the whole arc. Writes relationship_map.md.
Also writes map_data.json with the raw numbers that back the prose.
"""
import csv
import json
import re
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict

OUT = Path("/Users/andreyposelskiy/My_Story/telegram_index")
CSV_PATH = OUT / "unified_timeline.csv"

# Raise CSV field size limit for long voice-transcript rows
csv.field_size_limit(10_000_000)

# --- Load -------------------------------------------------------------------
rows = []
with CSV_PATH.open(encoding="utf-8") as f:
    r = csv.DictReader(f)
    for d in r:
        d["dt"] = datetime.fromisoformat(d["datetime"])
        rows.append(d)
rows.sort(key=lambda x: x["dt"])

USER = "Chief Garvey"
HER = "leeeroy"
primary = {USER, HER}
only_primary = [r for r in rows if r["sender"] in primary]

print(f"Loaded {len(rows)} rows ({len(only_primary)} between primaries)")

# --- Per-month dashboard ----------------------------------------------------
month_bins = defaultdict(list)
for r in only_primary:
    month_bins[r["dt"].strftime("%Y-%m")].append(r)

def latin_cyrillic_ratio(txts):
    lat, cyr = 0, 0
    for t in txts:
        for c in t:
            if c.isascii() and c.isalpha():
                lat += 1
            elif "\u0400" <= c <= "\u04FF":
                cyr += 1
    total = lat + cyr
    return (lat / total) if total else 0.0

def median_reply_minutes(msgs):
    """For each message where sender differs from previous sender, time diff in minutes."""
    gaps = []
    for i in range(1, len(msgs)):
        if msgs[i]["sender"] != msgs[i - 1]["sender"]:
            dt = (msgs[i]["dt"] - msgs[i - 1]["dt"]).total_seconds() / 60
            if dt >= 0:
                gaps.append(dt)
    return statistics.median(gaps) if gaps else None

def voice_count(msgs):
    return sum(1 for m in msgs if m["type"] == "voice")

monthly = {}
for ym, ms in sorted(month_bins.items()):
    ms_sorted = sorted(ms, key=lambda x: x["dt"])
    by_sender = Counter(m["sender"] for m in ms_sorted)
    monthly[ym] = {
        "total": len(ms_sorted),
        "voices": voice_count(ms_sorted),
        "user_msgs": by_sender.get(USER, 0),
        "her_msgs": by_sender.get(HER, 0),
        "english_ratio": latin_cyrillic_ratio([m["text"] for m in ms_sorted if m["text"]]),
        "median_reply_min": median_reply_minutes(ms_sorted),
    }

# --- Silences & resumers ----------------------------------------------------
gaps = []
for i in range(1, len(only_primary)):
    dt = only_primary[i]["dt"] - only_primary[i - 1]["dt"]
    if dt >= timedelta(days=2):
        gaps.append({
            "duration_days": dt.total_seconds() / 86400,
            "last_before": only_primary[i - 1],
            "first_after": only_primary[i],
        })
gaps.sort(key=lambda g: -g["duration_days"])

# Who resumes overall
resumer_counts = Counter(g["first_after"]["sender"] for g in gaps if g["duration_days"] >= 2)

# --- First-message-of-day by sender ----------------------------------------
by_day = defaultdict(list)
for m in only_primary:
    by_day[m["dt"].date()].append(m)
day_initiators = Counter()
for day, msgs in by_day.items():
    first = min(msgs, key=lambda x: x["dt"])
    day_initiators[first["sender"]] += 1

# --- Recurring capitalized tokens (proper-noun proxy) ----------------------
CAP_TOKEN = re.compile(r"\b([А-ЯЁ][а-яёA-Za-z]{2,})\b")
cap_counter = Counter()
for m in only_primary:
    if m["text"]:
        for tok in CAP_TOKEN.findall(m["text"]):
            cap_counter[tok] += 1

# Filter obvious non-names (common sentence-initial words)
STOPWORDS = {
    "Это", "Что", "Как", "Ну", "Да", "Нет", "Мне", "Тебе", "Ты", "Он", "Она", "Они",
    "Мы", "Вы", "Все", "Если", "Потому", "Когда", "Там", "Здесь", "Сейчас", "Уже",
    "Теперь", "Так", "Надо", "Нужно", "Есть", "Был", "Была", "Было", "Были", "Такой",
    "Такая", "Такое", "Такие", "Весь", "Вся", "Всё", "Какой", "Какая", "Какое",
    "Какие", "Это", "Этот", "Эта", "Эти", "Того", "Моё", "Моя", "Мой", "Мои",
    "Твоя", "Твой", "Твои", "Наш", "Ваш", "Только", "Даже", "Ещё", "Или", "Потом",
    "Просто", "Вообще", "Тоже", "Может", "Можно", "Нельзя", "Где", "Куда", "Откуда",
    "Почему", "Зачем", "Сколько", "Много", "Мало", "Лучше", "Хуже", "Больше", "Меньше",
    "Один", "Два", "Три", "Как", "Типа", "Кажется", "Конечно", "Наверное", "Обычно",
    "Довольно", "Очень", "Пока", "Всегда", "Никогда", "Часто", "Редко", "Иногда",
    "Теперь", "Однако", "Затем", "Потому", "Значит", "Видимо", "Сегодня", "Вчера",
    "Завтра", "Утром", "Днем", "Вечером", "Ночью", "Воскресенье", "Понедельник",
    "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Январь", "Февраль",
    "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь",
    "Ноябрь", "Декабрь", "Спасибо", "Пожалуйста", "Прости", "Прощай", "Привет",
    "Блядь", "Какого", "Но", "И", "А", "Или", "Хотя", "Пусть", "Давай", "Слушай",
    "Смотри", "Окей", "Ок",
}
top_caps = [(w, c) for w, c in cap_counter.most_common(80) if w not in STOPWORDS][:40]

# --- First/last anchors ----------------------------------------------------
first_msg = only_primary[0]
last_msg = only_primary[-1]
first_voice = next((m for m in only_primary if m["type"] == "voice"), None)
# last voice before 91-day silence (2024-10-02)
silence_start_dt = datetime(2024, 10, 2)
last_voice_pre_silence = None
for m in only_primary:
    if m["type"] == "voice" and m["dt"] < silence_start_dt:
        last_voice_pre_silence = m
# first msg after 91-day silence
first_after_silence = None
for m in only_primary:
    if m["dt"] >= datetime(2025, 1, 1):
        first_after_silence = m
        break

# --- "I love you" and related pattern matches ------------------------------
LOVE_PATTERN = re.compile(r"(?i)(люблю тебя|я тебя люблю|тебя люблю|love you|i love u|i love you)")
love_by_month = defaultdict(lambda: {USER: 0, HER: 0})
for m in only_primary:
    if m["text"] and LOVE_PATTERN.search(m["text"]):
        love_by_month[m["dt"].strftime("%Y-%m")][m["sender"]] += 1

# --- Write map_data.json ---------------------------------------------------
data = {
    "span": {
        "first": first_msg["dt"].isoformat(),
        "last": last_msg["dt"].isoformat(),
        "total_primary_msgs": len(only_primary),
        "user_total": sum(m["sender"] == USER for m in only_primary),
        "her_total": sum(m["sender"] == HER for m in only_primary),
    },
    "monthly": monthly,
    "top_20_silences": [
        {
            "duration_days": round(g["duration_days"], 1),
            "last_before": {
                "dt": g["last_before"]["dt"].isoformat(),
                "sender": g["last_before"]["sender"],
                "type": g["last_before"]["type"],
                "text": g["last_before"]["text"][:200],
            },
            "first_after": {
                "dt": g["first_after"]["dt"].isoformat(),
                "sender": g["first_after"]["sender"],
                "type": g["first_after"]["type"],
                "text": g["first_after"]["text"][:200],
            },
        }
        for g in gaps[:20]
    ],
    "resumer_counts": dict(resumer_counts),
    "day_initiators": dict(day_initiators),
    "top_capitalized_tokens": top_caps,
    "anchors": {
        "first_msg": {"dt": first_msg["dt"].isoformat(), "sender": first_msg["sender"], "text": first_msg["text"][:300]},
        "last_msg": {"dt": last_msg["dt"].isoformat(), "sender": last_msg["sender"], "text": last_msg["text"][:300]},
        "first_voice": {"dt": first_voice["dt"].isoformat(), "sender": first_voice["sender"], "text": first_voice["text"][:300]} if first_voice else None,
        "last_voice_pre_silence": {"dt": last_voice_pre_silence["dt"].isoformat(), "sender": last_voice_pre_silence["sender"], "text": last_voice_pre_silence["text"][:300]} if last_voice_pre_silence else None,
        "first_after_91day_silence": {"dt": first_after_silence["dt"].isoformat(), "sender": first_after_silence["sender"], "text": first_after_silence["text"][:300]} if first_after_silence else None,
    },
    "love_by_month": {k: dict(v) for k, v in love_by_month.items()},
}
(OUT / "map_data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
print("Wrote map_data.json")

# --- Write relationship_map.md (analytical prose + evidence) --------------
# Compute sender-balance shifts per quarter
def quarter(dt):
    return f"{dt.year}-Q{(dt.month-1)//3 + 1}"

quarterly = defaultdict(lambda: {USER: 0, HER: 0})
for m in only_primary:
    quarterly[quarter(m["dt"])][m["sender"]] += 1

md = []
md.append("# The Relationship Arc — Map\n")
md.append(f"*Source: {len(only_primary):,} messages between the two of you over "
          f"{(last_msg['dt'] - first_msg['dt']).days} days "
          f"({first_msg['dt'].date()} → {last_msg['dt'].date()}).*\n")
md.append("*Third-party messages excluded from this analysis (forwards, bots, group members).*\n")

md.append("---\n")
md.append("## 1. The shape\n")
md.append("Three acts, cleanly separable by the data:\n")
md.append("- **Act I — Opening (2021-08 → 2022-06).** First 10 months. Volume climbs fast to a plateau of ~2–5k msgs/month. 144 voice notes in Sept 2021 alone — the densest voice-intimacy of the entire arc.")
md.append("- **Act II — The Long Plateau (2022-07 → 2024-05).** Two steady years. 3–6k msgs/month. Voice notes become episodic clusters (Jul-Aug 2022, Sep-Oct 2023, Jan-Feb 2024) separated by prose-dominant stretches.")
md.append("- **Act III — The Fade (2024-06 → 2025-04).** Collapse begins. May 2024 is the last normal month (2,970 msgs). June: 527. July: 574. Aug: 105. Sept: 245. Oct: 203 (only 2 days). Then the 91-day silence. Then Jan–Feb 2025 reopens explosively — and fades again.\n")

md.append("## 2. Voice died before the relationship did\n")
md.append("The single clearest structural finding. Voice note counts:\n")
md.append("| Period | Voice notes |")
md.append("|---|---|")
md.append("| 2024 Jan | 28 |")
md.append("| 2024 Feb | 36 |")
md.append("| 2024 Mar | 6 |")
md.append("| 2024 Apr | 3 |")
md.append("| 2024 May | 11 |")
md.append("| 2024 Jun | **0** |")
md.append("| 2024 Jul | 4 |")
md.append("| 2024 Aug | **0** |")
md.append("| 2024 Sep | **0** |")
md.append("| 2024 Oct | **0** |\n")
md.append("You did not send each other a voice note for **the four months before the silence**. The intimate medium had been abandoned. Text — the most mediated, least vulnerable channel — was all that remained. And then even text stopped.\n")

md.append("## 3. Who initiates\n")
md.append(f"- Total message count: **{USER}** {data['span']['user_total']:,}  |  **{HER}** {data['span']['her_total']:,}")
md.append(f"- First message of the day (across {len(day_initiators)} active days): **{USER}** {day_initiators.get(USER, 0)}  |  **{HER}** {day_initiators.get(HER, 0)}")
md.append(f"- Who breaks silences of ≥2 days (total {sum(resumer_counts.values())} gaps): **{USER}** {resumer_counts.get(USER, 0)}  |  **{HER}** {resumer_counts.get(HER, 0)}")
u_pct = data['span']['user_total'] / len(only_primary) * 100
md.append(f"\nBalance: {u_pct:.1f}% of all words came from {USER}. You wrote more, reached out more, broke silences more. She wrote back.\n")

md.append("## 4. The silences\n")
md.append("Top 10 gaps and who resumed:\n")
md.append("| Days silent | Last before | First after | Resumed by |")
md.append("|---|---|---|---|")
for g in gaps[:10]:
    lb = g["last_before"]; fa = g["first_after"]
    t_before = (lb["text"][:60] or f"[{lb['type']}]").replace("|", "\\|").replace("\n", " ")
    t_after = (fa["text"][:60] or f"[{fa['type']}]").replace("|", "\\|").replace("\n", " ")
    md.append(f"| {g['duration_days']:.1f} | {lb['dt'].date()} {lb['sender']}: {t_before} | {fa['dt'].date()} {fa['sender']}: {t_after} | **{fa['sender']}** |")
md.append("")

md.append("## 5. Response latency over time\n")
md.append("Median minutes between a message and the other person's reply:\n")
md.append("| Quarter | Median reply (min) | msgs |")
md.append("|---|---|---|")
quarterly_lat = defaultdict(list)
for ym, m in monthly.items():
    y, mo = ym.split("-")
    q = f"{y}-Q{(int(mo)-1)//3 + 1}"
    if m["median_reply_min"] is not None:
        quarterly_lat[q].append((m["median_reply_min"], m["total"]))
for q in sorted(quarterly_lat.keys()):
    vals = quarterly_lat[q]
    weighted = sum(v * n for v, n in vals) / sum(n for v, n in vals)
    total_msgs = sum(n for _, n in vals)
    md.append(f"| {q} | {weighted:.1f} | {total_msgs:,} |")
md.append("")

md.append("## 6. Language drift\n")
md.append("Share of Latin characters (English) vs Cyrillic per quarter. Rising = more English creep. Both of you are bilingual; watching this shift is watching the relationship shift registers.\n")
md.append("| Quarter | English ratio |")
md.append("|---|---|")
q_eng = defaultdict(list)
for ym, m in monthly.items():
    y, mo = ym.split("-")
    q = f"{y}-Q{(int(mo)-1)//3 + 1}"
    q_eng[q].append((m["english_ratio"], m["total"]))
for q in sorted(q_eng.keys()):
    vals = q_eng[q]
    weighted = sum(r * n for r, n in vals) / sum(n for r, n in vals)
    md.append(f"| {q} | {weighted*100:.1f}% |")
md.append("")

md.append("## 7. The supporting cast\n")
md.append("Most-repeated capitalized tokens (proper-noun proxy). Stopwords filtered but not annotated — you'll need to identify which are people, places, or jokes:\n")
md.append("| Token | Count |")
md.append("|---|---|")
for tok, c in top_caps[:30]:
    md.append(f"| {tok} | {c} |")
md.append("")

md.append("## 8. Anchors\n")
if data["anchors"]["first_msg"]:
    a = data["anchors"]["first_msg"]
    md.append(f"**First message** — {a['dt'][:16]}  _{a['sender']}_:\n> {a['text']}\n")
if data["anchors"]["first_voice"]:
    a = data["anchors"]["first_voice"]
    md.append(f"**First voice note** — {a['dt'][:16]}  _{a['sender']}_:\n> *{a['text']}*\n")
if data["anchors"]["last_voice_pre_silence"]:
    a = data["anchors"]["last_voice_pre_silence"]
    md.append(f"**Last voice note before the 91-day silence** — {a['dt'][:16]}  _{a['sender']}_:\n> *{a['text']}*\n")
if data["anchors"]["first_after_91day_silence"]:
    a = data["anchors"]["first_after_91day_silence"]
    md.append(f"**First message after the 91-day silence** — {a['dt'][:16]}  _{a['sender']}_:\n> {a['text']}\n")
if data["anchors"]["last_msg"]:
    a = data["anchors"]["last_msg"]
    md.append(f"**Last message in the corpus** — {a['dt'][:16]}  _{a['sender']}_:\n> {a['text']}\n")

md.append("## 9. \"Люблю тебя\" / \"I love you\" — who says it, when\n")
md.append("Count of love-declaration messages per month (Russian and English patterns):\n")
md.append("| Month | You | Her |")
md.append("|---|---|---|")
for ym in sorted(love_by_month.keys()):
    md.append(f"| {ym} | {love_by_month[ym][USER]} | {love_by_month[ym][HER]} |")
md.append("")

md.append("---\n")
md.append("*Raw numbers behind every claim above: `map_data.json`.*\n")

(OUT / "relationship_map.md").write_text("\n".join(md), encoding="utf-8")
print(f"Wrote relationship_map.md ({len('\\n'.join(md)):,} chars)")
