# Project Architecture — Local vs Remote

*Locked 2026-04-20. Privacy and workflow framework for the novel.*

---

## The split

This project has two layers. They must not mix.

### Layer 1 — Private working substrate *(local only, gitignored)*

The raw material the novel is built from. **Never pushed to GitHub.** Grows as new characters are added.

- `telegram_index/corpus/<character>/` — one directory per character. Holds the raw Telegram export (JSON), flattened CSV, voice note transcripts, and any per-character derivatives that contain verbatim content. Example: `telegram_index/corpus/kostya/export.json`.
- `telegram_index/dossiers/<character>.md` — derived character analysis: voice signature, tics, relationship arc, gold-mine exchanges with timestamps. Contains real names and verbatim quotes. Stays local.
- Legacy raw files in `telegram_index/` root: `messages.csv`, `unified_timeline.csv`, `voice_notes.csv`, `timeline_daily.csv`, `breakup_window.md`, `full_ledger.md`, `full_ledger_data.json`, `per_file.json`, `transcripts/`, `by_month/`, `*.log`. All gitignored, all local.
- `notebook/` — working notebook. Session logs, planning scratch, craft conversations distilled from sessions. Contains real names, quotes, and in-progress thinking. Local only.

### Layer 2 — Shareable fictional layer *(tracked and pushed to GitHub)*

The novel itself and the planning around it — **fictional names throughout, zero verbatim quotes from the corpus**.

- `01_structure.md` through `06_architecture.md` — planning docs. Use fictional names only (*Lera* is a codename until locked; real names forbidden).
- `prose/` — fictional prose drafts. One file per chapter (e.g. `prose/ch01_may_dip.md`), grows as beats are drafted.
- `characters/` *(to be created)* — fictional character sheets, drawn from the dossiers but sanitized of real names and verbatim quotes. One file per character in the book.
- `telegram_index/*.py` — processing scripts. Code is fine on GitHub; only content is not.

---

## The rule

> If a file contains a **verbatim quote** or a **real name**, it belongs in Layer 1. Full stop.

Dossiers live in Layer 1 because they *have* to contain verbatim evidence — that's their purpose. The fictional character sheets (Layer 2) are the sanitized, publishable reflection of a dossier.

---

## Workflow for building a character

1. Export the Telegram chat with that person → save the JSON into `telegram_index/corpus/<name>/`.
2. Run the existing pipeline (flatten to CSV, transcribe voice notes) within that folder.
3. We build `telegram_index/dossiers/<name>.md` together — voice signature, arc, gold-mine quotes, function in the book. Lives on disk only.
4. We extract the fictional sheet → `characters/<fictional_name>.md`. No real name, no verbatim quotes. Pushed to GitHub.
5. When drafting a scene involving that character, both files are in play: dossier as evidence, fictional sheet as the canonical reference for the novel.

---

## Why this exists

The corpus is the engine of the book. The LLM reads it to build characters and guard voice. But the corpus also contains a non-consenting third party's private messages and multiple real names. The only defensible arrangement is: **raw substrate stays off the wire; only the fictionalized derivative is shareable.**

The assistant reads the local filesystem — not GitHub — so keeping the corpus local costs nothing in capability.

---

## Cleanup history

- **2026-04-20.** Audit found `relationship_map.md`, `map_data.json`, and `unified_stats.json` contained verbatim Russian message quotes, real names (Лера, Андрей, Медина, Костя, Артём, Оли), and Telegram handles. All three deleted from disk. `.gitignore` strengthened. Git history rewrite pending.
