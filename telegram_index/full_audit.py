#!/usr/bin/env python3
"""
Full-corpus audit of every specific claim made in the previous verdict.
For each theme: count, who-says, time distribution, sample quotes.

Produces full_ledger.md that is neutral evidence, not judgment.
"""
import csv
import re
import json
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

OUT = Path("/Users/andreyposelskiy/My_Story/telegram_index")
CSV_PATH = OUT / "unified_timeline.csv"
csv.field_size_limit(10_000_000)

USER = "Chief Garvey"
HER = "leeeroy"

# --- Load ------------------------------------------------------------------
rows = []
with CSV_PATH.open(encoding="utf-8") as f:
    r = csv.DictReader(f)
    for d in r:
        if d["sender"] not in {USER, HER}:
            continue
        d["dt"] = datetime.fromisoformat(d["datetime"])
        d["txt_norm"] = (d["text"] or "").replace("  ⏎  ", " ").lower()
        rows.append(d)
rows.sort(key=lambda x: x["dt"])
print(f"Loaded {len(rows):,} primary rows")

# --- Theme definitions ------------------------------------------------------
# Each theme: a regex + a short description. I lowercase everything before matching.
THEMES = {
    "sex_desire_conflict": re.compile(
        r"\b(секс(?:ом|е|а|у|ов)?|интим|либидо|эрекц|возбужд|sex|sexual|foreplay|\bхочу тебя\b|заниматься любовью|masturbat|мастурб|фрустрац)\b",
        re.IGNORECASE,
    ),
    "drinking_alcohol": re.compile(
        r"\b(пью|пил|пила|пить|выпил|выпила|напил|бухал|бухать|вино|пиво|виски|водк|алкогол|trunk|drunk|drink|drinking|алкаш|запой|похмел)\b",
        re.IGNORECASE,
    ),
    "cheating_kiss": re.compile(
        r"\b(измен(?:а|у|ы|е|ой|ил|ила|ять|яешь)?|поцел(?:ова|уй|уе|ую)?|kiss|cheat|изменил|изменила|kissed|мариша|мария|сабр|измен)\b",
        re.IGNORECASE,
    ),
    "friends_social": re.compile(
        r"\b(друг|друзь|подруг|встреча|встретит|увидет|увиж|posидет|с ребятами|с девочками|friends|hang out|общалась|общался)\b",
        re.IGNORECASE,
    ),
    "therapy_psychologist": re.compile(
        r"\b(психолог|терапи|сеанс|therap|шринк|shrink|консульта|психотер)\b",
        re.IGNORECASE,
    ),
    "apology_responsibility": re.compile(
        r"\b(прост[иь]|извин[иь]|прошу прощен|моя вина|я виноват|я не прав|sorry|my bad|my fault|i apolog|виновата)\b",
        re.IGNORECASE,
    ),
    "love_declaration": re.compile(
        r"\b(люблю тебя|я тебя люблю|тебя люблю|люблю|love you|i love u|i love you|родн(?:ая|ой)|солнышко|любимый|любимая|скучаю)\b",
        re.IGNORECASE,
    ),
    "threat_of_ending": re.compile(
        r"\b(расстат|расстан|разойд|разорв|конец|не хочу больше|брошу|оставь мен|оставлю|уйду|break up|breaking up|breakup)\b",
        re.IGNORECASE,
    ),
    "throwing_violence": re.compile(
        r"\b(швыря|кинул|кинула|сломал|ударил|разбил|орал|кричал|в ярости|вспылил)\b",
        re.IGNORECASE,
    ),
    "boundary_silence_requests": re.compile(
        r"\b(не пиши|отстань|оставь меня|перестань писать|хватит писать|не звони|пожалуйста уйди|дай мне время|дай мне пространств|leave me alone|don'?t write|stop writing)\b",
        re.IGNORECASE,
    ),
    "money_work_struggle": re.compile(
        r"\b(деньги|денег|без работы|ресторан|стартап|startup|работу|без зарплаты|долг|банкрот|нет денег|uber eats|официант|waiter|сбережения)\b",
        re.IGNORECASE,
    ),
    "war_politics": re.compile(
        r"\b(войн[аеуы]|мобилизац|путин|зеленск|украин|россии напала|вторжен|russia|ukraine|war\b)\b",
        re.IGNORECASE,
    ),
    "depression_mental": re.compile(
        r"\b(депрес|мне плохо|мне тяжело|не могу больше|выгора|burnout|suicidal|anxiety|тревог|панич|паническ|хочу умер)\b",
        re.IGNORECASE,
    ),
    "long_distance_travel": re.compile(
        r"\b(лондон|london|st andrews|сент эндрюс|эндрюс|эдинбург|edinburgh|автобус|поезд|перелет|прилечу|приехала|приеду|скучаю|разные города)\b",
        re.IGNORECASE,
    ),
    "plans_future_marriage": re.compile(
        r"\b(поженим|свадьба|свадьбу|кольцо|наше будущ|будущ(?:ее|ем|ее)|помолв|дети|ребен)\b",
        re.IGNORECASE,
    ),
    "accusation_always_never": re.compile(
        r"\b(ты всегда|ты никогда|ты вечно|ты постоянно|из-за тебя|это все ты|ты меня|ты мне не)\b",
        re.IGNORECASE,
    ),
    "i_statement_self_reflection": re.compile(
        r"\b(я чувствую|я понимаю|я знаю что я|я признаю|я виноват|я ошиб|мне стыдно|я должен был|я не должен был)\b",
        re.IGNORECASE,
    ),
    "sulking_silent_treatment": re.compile(
        r"\b(не разговар|молчан|игнорир|ignore|отверну|отвернул|перестал со мной|не отвечает|не отвечал)\b",
        re.IGNORECASE,
    ),
    "crying_tears": re.compile(
        r"\b(плакал|плакала|плачу|реву|рыда|слезы|в слез|tears|crying|cry|плачет)\b",
        re.IGNORECASE,
    ),
    "gratitude_thanks": re.compile(
        r"\b(спасибо|благодар|thank you|thanks|merci|appreciate)\b",
        re.IGNORECASE,
    ),
    "checking_how_she_is": re.compile(
        r"\b(как ты\??|как дела|как твои дела|как прошел|как прошло|как настроен|how are you|how was)\b",
        re.IGNORECASE,
    ),
    "encouraging_her_agency": re.compile(
        r"\b(ты умница|ты молодец|у тебя получит|ты справ|ты сильная|верю в тебя|proud of you|ты сможешь|ты достойна)\b",
        re.IGNORECASE,
    ),
    "withholding_secrets": re.compile(
        r"\b(не говорила|скрыла|скрывала|не сказала|не хотела говорить|от меня скрыва|утаила|не призналась)\b",
        re.IGNORECASE,
    ),
    "keeping_score": re.compile(
        r"\b(миллион раз|сто раз|тысячу раз|опять|снова|в который раз|каждый раз когда|всегда одно|уже устала|уже устал)\b",
        re.IGNORECASE,
    ),
}


# --- Scan ------------------------------------------------------------------
def scan():
    theme_hits = defaultdict(list)
    for r in rows:
        t = r["txt_norm"]
        if not t:
            continue
        for name, pat in THEMES.items():
            if pat.search(t):
                theme_hits[name].append(r)
    return theme_hits


print("Scanning corpus for theme hits...")
theme_hits = scan()

# --- Summaries -------------------------------------------------------------
def stats_for_hits(hits):
    total = len(hits)
    by_sender = Counter(h["sender"] for h in hits)
    by_year = Counter(h["dt"].year for h in hits)
    first = min(hits, key=lambda x: x["dt"]) if hits else None
    last = max(hits, key=lambda x: x["dt"]) if hits else None
    return {
        "total": total,
        "by_sender": dict(by_sender),
        "by_year": dict(sorted(by_year.items())),
        "first": {"dt": first["dt"].isoformat(), "sender": first["sender"], "text": first["text"][:300]} if first else None,
        "last": {"dt": last["dt"].isoformat(), "sender": last["sender"], "text": last["text"][:300]} if last else None,
    }


# --- Build full_ledger.md --------------------------------------------------
md = []
md.append("# Full-Corpus Audit — Verdict Claims vs Data\n")
md.append(f"*Scanned all {len(rows):,} messages between the two of you.*\n")
md.append(f"*Method: regex pattern matching per theme. Not a substitute for reading, but systematic — every message got checked against every theme.*\n")
md.append("*Note: regex counts include false positives (e.g., \"любимый фильм\" matches love_declaration). Quotes below are representative, not filtered by human.*\n")
md.append("\n---\n")

# Totals overview
md.append("## Quick overview — theme frequency and who raises them\n")
md.append("| Theme | Total | You | Her | First → Last |")
md.append("|---|---|---|---|---|")
for name in [
    "sex_desire_conflict",
    "drinking_alcohol",
    "cheating_kiss",
    "friends_social",
    "therapy_psychologist",
    "apology_responsibility",
    "love_declaration",
    "threat_of_ending",
    "throwing_violence",
    "boundary_silence_requests",
    "money_work_struggle",
    "war_politics",
    "depression_mental",
    "long_distance_travel",
    "plans_future_marriage",
    "accusation_always_never",
    "i_statement_self_reflection",
    "sulking_silent_treatment",
    "crying_tears",
    "gratitude_thanks",
    "checking_how_she_is",
    "encouraging_her_agency",
    "withholding_secrets",
    "keeping_score",
]:
    s = stats_for_hits(theme_hits[name])
    firstlast = f"{s['first']['dt'][:10]} → {s['last']['dt'][:10]}" if s["first"] else "—"
    md.append(f"| {name} | {s['total']:,} | {s['by_sender'].get(USER, 0):,} | {s['by_sender'].get(HER, 0):,} | {firstlast} |")
md.append("")

# --- For each claim, write detailed section --------------------------------
CLAIMS = [
    {
        "title": "CLAIM 1 — \"You isolated her from friends\"",
        "themes": ["friends_social"],
        "intro": (
            "Context you provided: you were exhausting yourself on the London → St Andrews route, "
            "and experienced her framing as unfair. Let's look at everything that mentions friends "
            "across the whole corpus — who raises the topic, how it's discussed, whether you ever "
            "encouraged her to see friends vs. objected."
        ),
    },
    {
        "title": "CLAIM 2 — \"You drank past a stated condition\"",
        "themes": ["drinking_alcohol"],
        "intro": (
            "Context you provided: 4–5 year depression, wine/beer, self-medication rather than spirits. "
            "Looking at every mention of alcohol across the corpus: who raises it, in what register, "
            "is it raised as concern or as accusation, did you acknowledge it, did you try."
        ),
    },
    {
        "title": "CLAIM 3 — \"You threw things\"",
        "themes": ["throwing_violence"],
        "intro": (
            "Her accusation (2024-07-31 10:27): «Да, ты швырялся вещами и не давал мне спать». "
            "I treated this as confirmed because you didn't deny it. Let's see every message across "
            "the corpus that references throwing / physical anger / yelling. Pattern or single incident?"
        ),
    },
    {
        "title": "CLAIM 4 — \"Sex-as-leverage pattern (tantrums, silent treatment)\"",
        "themes": ["sex_desire_conflict", "sulking_silent_treatment"],
        "intro": (
            "The argument 2024-07-31 is where she named this explicitly. Is it corroborated "
            "across years of data? Who talks about sex more — is it recurrent argument or episodic? "
            "Does the sulking theme co-occur with sex conflict?"
        ),
    },
    {
        "title": "CLAIM 5 — \"Four years in, you were still relitigating sex frequency\"",
        "themes": ["sex_desire_conflict"],
        "intro": "Frequency of sex-theme mentions over time — is it a steady recurring topic you raise, or episodic?",
    },
    {
        "title": "CLAIM 6 — \"Cheating\" (one kiss in your context)",
        "themes": ["cheating_kiss"],
        "intro": (
            "You clarified: one kiss during wartime/startup collapse/months-without-sex. "
            "Every mention of betrayal/kissing across the corpus — when, who brings it up, frequency."
        ),
    },
    {
        "title": "CLAIM 7 — \"Boundary-crossing at the 91-day silence\" (and beyond)",
        "themes": ["boundary_silence_requests"],
        "intro": (
            "Beyond the one explicit boundary (don't write to me), does the corpus show other times "
            "where she asked for space/silence and how you responded?"
        ),
    },
    {
        "title": "CLAIM 8 — Her: \"couldn't let go of the betrayal\"",
        "themes": ["cheating_kiss", "keeping_score"],
        "intro": "How often does she bring up the betrayal, and in what form — litigation or grief?",
    },
    {
        "title": "CLAIM 9 — Her: \"withheld / kept score\"",
        "themes": ["withholding_secrets", "keeping_score"],
        "intro": "Evidence of withholding — yours about her, hers about you. Whose pattern is clearer.",
    },
]

def sample_quotes(hits, sender_filter=None, n=5):
    filtered = [h for h in hits if (sender_filter is None or h["sender"] == sender_filter)]
    if not filtered:
        return []
    # Pick N spread across time
    filtered.sort(key=lambda x: x["dt"])
    if len(filtered) <= n:
        return filtered
    step = len(filtered) // n
    return [filtered[i * step] for i in range(n)]


def render_quote(h, max_chars=300):
    t = (h["text"] or "").replace("  ⏎  ", " ")
    if h["type"] == "voice":
        t = f"🎙 {t}"
    if len(t) > max_chars:
        t = t[:max_chars] + "…"
    return f"- **{h['dt'].strftime('%Y-%m-%d %H:%M')} — {h['sender']}**: {t}"


for claim in CLAIMS:
    md.append(f"\n## {claim['title']}\n")
    md.append(claim["intro"] + "\n")
    # Combine hits from all themes in the claim
    combined_hits = []
    seen = set()
    for t in claim["themes"]:
        for h in theme_hits[t]:
            key = (h["dt"].isoformat(), h["sender"], (h["text"] or "")[:50])
            if key not in seen:
                seen.add(key)
                combined_hits.append(h)
    combined_hits.sort(key=lambda x: x["dt"])
    total = len(combined_hits)
    by_sender = Counter(h["sender"] for h in combined_hits)
    by_year = Counter(h["dt"].year for h in combined_hits)
    md.append(f"**Total messages matching**: {total:,}  —  You: {by_sender.get(USER, 0):,}  |  Her: {by_sender.get(HER, 0):,}\n")
    md.append("**Yearly distribution**: " + "  ".join(f"{y}: {c}" for y, c in sorted(by_year.items())) + "\n")
    md.append("\n**Representative quotes from you:**\n")
    for q in sample_quotes(combined_hits, sender_filter=USER, n=5):
        md.append(render_quote(q))
    md.append("\n**Representative quotes from her:**\n")
    for q in sample_quotes(combined_hits, sender_filter=HER, n=5):
        md.append(render_quote(q))
    md.append("")

# --- Apology ledger ---------------------------------------------------------
md.append("\n## BONUS — Apology ledger\n")
md.append("Who apologizes more across the whole corpus.\n")
ap = theme_hits["apology_responsibility"]
ap_by_year = defaultdict(lambda: Counter())
for h in ap:
    ap_by_year[h["dt"].year][h["sender"]] += 1
md.append("| Year | You | Her |")
md.append("|---|---|---|")
for y in sorted(ap_by_year.keys()):
    md.append(f"| {y} | {ap_by_year[y].get(USER, 0)} | {ap_by_year[y].get(HER, 0)} |")
md.append("")

# --- I-statements ledger ---------------------------------------------------
md.append("\n## BONUS — Self-reflection ('I-statement') ledger\n")
md.append("Who uses language of self-reflection (\"я чувствую\", \"я признаю\", \"я ошибся\", etc.)\n")
isr = theme_hits["i_statement_self_reflection"]
isr_by_year = defaultdict(lambda: Counter())
for h in isr:
    isr_by_year[h["dt"].year][h["sender"]] += 1
md.append("| Year | You | Her |")
md.append("|---|---|---|")
for y in sorted(isr_by_year.keys()):
    md.append(f"| {y} | {isr_by_year[y].get(USER, 0)} | {isr_by_year[y].get(HER, 0)} |")
md.append("")

# --- Accusation ledger -----------------------------------------------------
md.append("\n## BONUS — Accusation ledger\n")
md.append("\"Always/never/because of you\" framings by year.\n")
ac = theme_hits["accusation_always_never"]
ac_by_year = defaultdict(lambda: Counter())
for h in ac:
    ac_by_year[h["dt"].year][h["sender"]] += 1
md.append("| Year | You | Her |")
md.append("|---|---|---|")
for y in sorted(ac_by_year.keys()):
    md.append(f"| {y} | {ac_by_year[y].get(USER, 0)} | {ac_by_year[y].get(HER, 0)} |")
md.append("")

# --- Checking on her / encouraging her -------------------------------------
md.append("\n## BONUS — Care-work ledger (you toward her)\n")
md.append("\"Как ты?\" / \"how are you?\" plus explicit encouragement. Counts by year.\n")
ck = theme_hits["checking_how_she_is"]
en = theme_hits["encouraging_her_agency"]
care_by_year = defaultdict(lambda: Counter())
for h in ck + en:
    care_by_year[h["dt"].year][h["sender"]] += 1
md.append("| Year | You | Her |")
md.append("|---|---|---|")
for y in sorted(care_by_year.keys()):
    md.append(f"| {y} | {care_by_year[y].get(USER, 0)} | {care_by_year[y].get(HER, 0)} |")
md.append("")

(OUT / "full_ledger.md").write_text("\n".join(md), encoding="utf-8")
print(f"Wrote full_ledger.md")

# Also dump the raw stats JSON for further use
all_stats = {name: stats_for_hits(hits) for name, hits in theme_hits.items()}
(OUT / "full_ledger_data.json").write_text(json.dumps(all_stats, ensure_ascii=False, indent=2))
print("Wrote full_ledger_data.json")
