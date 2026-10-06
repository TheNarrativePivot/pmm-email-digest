# Email Digest

A weekly, filterable digest of newsletters you follow. It pulls the new issues from a Gmail allowlist, uses [TypeSafe](https://docs.typesafe.ai) System One judgments to tag and select the useful passages, and gives you three things:

- `digest.md`: best things to act on, frameworks, items by topic, and what was filtered out.
- A single-file filter page (topic, framework, actionable, source, minimum actionability) with a question box that searches every stored email.
- `ask.py`: a deeper question search where TypeSafe judges each candidate passage against your question.

It was built for product marketing newsletters, but the topics and rules are in `classify.py` and `config.json`, so you can retarget it.

No email content is stored in this repository. Everything derived from your inbox stays local (see `.gitignore`).

## How it works

Design principle: **TypeSafe does the reading, Claude does as little as possible.**

1. Gmail is searched for new mail from the senders in `sources.json`.
2. `classify.py` sends each email to TypeSafe with about a dozen independent yes/no questions (one per topic, plus framework, actionable, idea, promo, career, roundup) and one 0 to 4 actionability score. Raw probabilities are stored; `config.json` decides what counts as a tag or an exclusion, so retuning never needs a rerun.
3. `extract.py` splits each body into passages and has TypeSafe judge each one (steps, insight, example, setup, promo, links). It stores `meat` (all substantive passages, verbatim), `core` (the best passages up to 1,800 characters) and `depth` (full, partial when cut off by a paywall, or teaser).
4. An LLM reads only `core` and writes a short `summary`, `points` (the actual steps or findings) and one `action` per email.
5. `build.py` applies the rules and writes `digest.md` and `page/index.html`.

In a test on 22 emails, `core` was 21% of the characters of the full text, and `meat` was 44%.

## Files

| File | Purpose |
|---|---|
| `classify.py` | Questions, topic list, and `apply_rules` (exclusions and tag thresholds). |
| `extract.py` | Passage splitting and TypeSafe passage judging. |
| `crawl_substack.py` | Appends new posts from the Substack publications in `sources.json` to `data/inbox.json`. |
| `ingest.py` | Turns saved Gmail thread dumps into `data/inbox.json` (new emails only). |
| `run_week.py` | Classifies and extracts everything in `data/inbox.json`, merges into `data/items.json`. |
| `playbook_pending.py`, `pb_add.py` | List posts that need a playbook; merge finished playbook records. |
| `pending.py` | Lists kept items that still need a summary, showing only their `core` passages. |
| `build.py` | Writes `digest.md` and `page/index.html` from `page/template.html`. |
| `ask.py` | Deep question search over all stored emails. |
| `reclassify.py` | Re-scores stored emails after you change a question. |
| `config.example.json`, `sources.example.json`, `data/state.example.json` | Copy to `config.json`, `sources.json`, `data/state.json` and edit. |

## Setup

```bash
python3.13 -m venv .venv            # typesafe-sdk needs Python 3.10 or newer
./.venv/bin/pip install typesafe-sdk
cp config.example.json config.json
cp sources.example.json sources.json
mkdir -p data && cp data/state.example.json data/state.json
export TYPESAFE_API_KEY=...         # from console.typesafe.ai, keep it out of git and chat
```

## Weekly run

1. Read `data/state.json` and `sources.json`; search Gmail since `last_run` per sender and skip ids already in `data/items.json`.
2. Fetch each new thread and save the JSON. `./.venv/bin/python ingest.py <folder with the dumps> --expect id1,id2` reports anything missing.
3. If `sources.json` has a `substack` list, run `./.venv/bin/python crawl_substack.py` after `ingest.py`. It reads each publication's public archive and post JSON (`/api/v1/archive`, `/api/v1/posts/<slug>`) and appends new posts to `data/inbox.json`. Paywalled posts arrive as previews and are marked partial.
3b. `./.venv/bin/python run_week.py` (needs `TYPESAFE_API_KEY`).
4. `./.venv/bin/python pending.py`, then write `summary`, `points` and `action` into `data/items.json` for each item listed.
5. `./.venv/bin/python build.py`, publish `page/index.html`, update `last_run`.

I run steps 1 to 5 as a scheduled Claude task each Monday morning; any scheduler that can fetch Gmail threads works.

## Asking questions

- On the page: "Find passages" ranks emails in the browser (keyword plus synonyms, no AI). "Ask Claude" sends the top passages to Claude for a short cited answer. This needs a host that offers an in-page model call.
- On your machine: `./.venv/bin/python ask.py "your question"`. Keyword retrieval picks about 60 candidate passages, TypeSafe judges each against your question, and the best are printed with sources.

## Rules and tuning

Exclusions live in `config.json` (subject regex, career, promo and roundup thresholds) and the questions in `classify.py`. Known weak spots: the actionable tag over-fires on essays, and podcast issues can pick up a topic they do not deserve. Spot-check the first few weeks and adjust thresholds.

## Playbooks

Beyond the digest, `playbook_pending.py` lists kept items with a framework or actionable tag and prints only the passages TypeSafe judged as steps, insight or example (verbatim, in order). From that, a playbook record is written per post (`pb_add.py` merges it into `data/playbooks.json`): purpose, what you need, numbered steps, the author's prompts verbatim, a fallback for other LLMs, and notes on what is paywalled. `build.py` renders them as a Playbooks tab on the page (theme filter, copy buttons, search by meaning through the page's Claude call) and as one Markdown file each in `data/playbooks/`. Themes are listed in `config.json` under `playbook_themes`. Posts with no method (opinion, teasers, promos) go in `data/playbook_skip.json`.

## Per-source rules

`config.json` can list `buildable_only_senders` (for example Substack hosts). For those, an item is kept only if it has a framework or actionable tag and an actionability of at least `buildable_min_actionability`. Everywhere, `consumer_exclude_threshold` drops B2C and ecommerce items and `vendor_news_exclude_threshold` drops vendor release digests. After adding a question, run `reclassify.py --new-keys` to score stored items without disturbing their existing scores.

## Notes

- Keep the TypeSafe key in your shell environment. Never commit it.
- Newsletter text belongs to its authors. This repo contains none; `data/` and the generated files are gitignored.
- Not affiliated with TypeSafe or any newsletter.
