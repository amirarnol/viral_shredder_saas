# Viral Shredder — AI Content Shredder (micro-SaaS)

Paste a link to a TikTok video, Instagram Reel or YouTube Short. Viral Shredder reads the
clip, ranks the ideas in it, and writes three assets from the same source:

1. **A comprehensive SEO article** — title, meta description, focus + secondary keywords,
   structured sections, FAQ, and tags.
2. **An X thread** — hook first, then the highest-signal lines from the script, numbered.
3. **A LinkedIn post** — takeaways plus platform-appropriate hashtags.

Built with **Python + FastAPI** on the backend and **HTML5 + TailwindCSS** on the frontend.
Payments are a **simulated crypto gateway** (USDT TRC20 / BEP20 / Binance Pay) upgrading to
Pro at **$9/month**. WhatsApp and Telegram support buttons float on every page.

---

## Quick start

```bash
cd viral_shredder_saas
pip install -r requirements.txt
python run.py
```

Open <http://127.0.0.1:8000>. Enter an email to get 5 free credits, paste a video link,
and hit **Shred it**.

Requires Python 3.10+ (developed on 3.14).

---

## Project layout

```
viral_shredder_saas/
├── app/
│   ├── main.py        FastAPI routes: pages, /shred, payments, marketing
│   ├── config.py      Settings, wallets, plans (env-driven)
│   ├── database.py    SQLite layer (users, jobs, payments, submissions)
│   ├── shredder.py    The engine: URL parse → metadata → keywords → 3 assets
│   ├── payments.py    Simulated crypto gateway + settlement
│   └── marketing.py   Directory submission engine
├── scripts/
│   └── submit_directories.py   Autonomous marketing pass (CLI)
├── templates/         base + index + dashboard + pricing + checkout + result + marketing + support
├── static/data/directories.json   Submission target list
├── requirements.txt
├── run.py
└── .env.example
```

---

## The shredder pipeline

`app/shredder.py` works fully offline and deterministically:

- **`parse_video_url`** — identifies TikTok / Instagram / YouTube Shorts / Facebook / generic
  web pages and extracts the video id, including from short links.
- **`fetch_video_meta`** — fetches the page with a browser user agent, follows redirects, and
  pulls Open Graph / Twitter / JSON-LD metadata plus hashtags. YouTube captions are fetched
  via the timedtext API. If the network is blocked or the platform gatekeep the page, the
  engine degrades to whatever the URL itself carries instead of failing.
- **`extract_keywords`** — stopword-filtered term frequency with length and hashtag weighting.
- **`score_sentences`** — extractive ranking by keyword overlap, position and length.
- **`build_seo_article` / `build_x_thread` / `build_linkedin_post`** — structured generation
  around the ranked material, with an SEO title, 158-char meta description, FAQ section and
  tags, and tweets held under the 280-character limit.

**Optional LLM upgrade.** Set `LLM_API_BASE`, `LLM_API_KEY` and `LLM_MODEL` (any
OpenAI-compatible endpoint) and `llm_polish` rewrites the extractive draft while keeping the
structure and keywords. If the endpoint is unreachable, the draft is returned untouched.

---

## Tone & target-language selector

Every generated string flows through `app/localization.py` — the generators never hardcode
prose. The matrix is two layers:

- **Language layer** (`L10N`) — 32 string keys translated into English, Arabic, Spanish and
  French. This is the base table for any request.
- **Tone layer** (`TONE_OVERRIDES`) — 9 voice keys (hooks, openers, CTAs) overridden per tone
  and composed *on top of* the language table, so a tone never breaks a translation.

```python
resolve("thread_hook", language="ar", tone="viral", niche="القصير", primary="...", n=9)
```

Selection is available on the landing page ("Pick your voice"), is carried through signup as
query params, and is re-selectable on the dashboard per job:

| Parameter | Values | Default |
| --- | --- | --- |
| `tone` | `professional`, `viral`, `storytelling` | `professional` |
| `language` | `en`, `ar`, `es`, `fr` | `en` |

Backend contract — both are optional `Form` fields on `POST /shred`; unknown values are
rejected with `400` and a list of the valid ones:

```python
result = await asyncio.to_thread(shred, url.strip(), 0, tone, language)
```

Notes on correct rendering:

- Arabic sets `direction: "rtl"` on the article payload; the dashboard and permalink
  templates apply `dir="rtl"` to the output grid so the whole layout flips.
- Topic niches are matched in English and translated via `NICHE_L10N` so no English fragment
  leaks into a translated heading. The fallback niche is the bare adjective `short-form`,
  because every string that interpolates a niche already supplies its own noun
  ("this `{niche}` video", "a `{niche}` clip") — a noun here would duplicate it.
- Headline casing is language-aware: `headline_niche()` title-cases for English, keeps
  sentence case for Spanish and French, and leaves Arabic untouched.

---

## Payment gateway (simulated)

The deposit details shown at checkout:

| Method | Address / ID |
| --- | --- |
| USDT — TRC20 (Tron) | `TKcGim9AWivJhySpbuR7FHC738anMsSSz3` |
| USDT — BEP20 (BNB Smart Chain) | `0xee2d811a8c7c851c54fb2695f458983028e6a9fa` |
| Binance Pay | ID `736985053` |

Behaviour is controlled by `PAYMENT_DEMO_MODE`:

- **`1` (default)** — a background settlement loop marks each order `paid` roughly 45s after
  it is created, then flips the account to **Pro**. Nothing touches a blockchain; this exists
  so the full upgrade flow can be demoed end to end. The checkout page also polls
  `/api/payment/{id}/status` and offers "I've paid — verify now".
- **`0`** — orders stay `pending` until an operator confirms them via
  `POST /api/payment/{id}/confirm` or manually through support.

`POST /webhook/payment` accepts `{order_ref, tx_hash, amount, currency}` in the shape a real
gateway would send. Set `WEBHOOK_TOKEN` to require `Authorization: Bearer <token>`.

**Going live** means replacing `settle_pending_orders` in `app/payments.py` with a TronGrid /
BSC scan for incoming USDT to those wallets, matching on the exact amount and the order
reference. The rest of the flow (plan flip, UI polling, webhook) already expects that.

Manual fallback is always available: the checkout and support pages link straight to WhatsApp
and Telegram for a human to confirm the upgrade.

---

## Support contacts

Floating buttons on every page, bottom right:

- **WhatsApp:** +963 934 641 795 → `https://wa.me/963934641795`
- **Telegram:** @avdv3 → `https://t.me/avdv3`

These are also in the footer and on `/support`, where all three deposit addresses are shown
with copy buttons.

---

## Autonomous directory submission

`scripts/submit_directories.py` submits the product to 15 startup / AI-tool directories with
no interaction:

```bash
python scripts/submit_directories.py              # live pass
python scripts/submit_directories.py --dry-run    # build payloads, send nothing
python scripts/submit_directories.py --only "Toolify.ai,Futurepedia"
python scripts/submit_directories.py --json       # machine-readable summary
```

Two modes per directory (see `static/data/directories.json`):

- **`post`** — a public form endpoint exists; we POST the payload and record the HTTP status.
- **`get`** — the form is login/captcha gated; we build a prefilled URL and record a `manual`
  action for an operator to submit once.

Every attempt is written to `submissions.jsonl` and the `submissions` table, and the log is
visible on `/marketing`, which can also trigger a run (or a dry run) from the browser.

To add a directory, append an object to `static/data/directories.json`:

```json
{ "name": "Example Directory", "submit_url": "https://example.com/submit", "mode": "get",
  "notes": "why it matters" }
```

---

## Configuration

Copy `.env.example` to `.env`. Everything has a default, so the app runs without it:

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | bind address |
| `PAYMENT_DEMO_MODE` | `1` | auto-confirm orders (see above) |
| `PAYMENT_DEMO_CONFIRM_AFTER` | `45` | seconds before demo settlement |
| `PRO_PLAN_PRICE_USD` | `9` | Pro price |
| `USDT_TRC20_WALLET` | `TKcGim9AWivJhySpbuR7FHC738anMsSSz3` | TRC20 deposit |
| `USDT_BEP20_WALLET` | `0xee2d811a8c7c851c54fb2695f458983028e6a9fa` | BEP20 deposit |
| `BINANCE_ID` | `736985053` | Binance Pay ID |
| `WHATSAPP_NUMBER` | `963934641795` | WhatsApp click-to-chat |
| `TELEGRAM_USERNAME` | `avdv3` | Telegram handle |
| `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` | empty | optional OpenAI-compatible polish step |

---

## Key endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | landing page |
| GET/POST | `/signup` | email-only account, sets a session cookie |
| GET | `/dashboard` | the shredder UI + recent jobs |
| POST | `/shred` | runs the pipeline, returns all three assets |
| GET | `/job/{id}` | permalink for a finished job |
| GET | `/pricing` · `/upgrade` · `/checkout/{id}` | plans and crypto checkout |
| GET | `/api/payment/{id}/status` | polled by the checkout page |
| POST | `/api/payment/{id}/confirm` | manual settlement |
| POST | `/webhook/payment` | gateway webhook shape |
| GET | `/marketing` · POST `/api/marketing/run` | directory submissions |
| GET | `/support` · `/health` | contacts · health check |

---

## Notes and limits

- The demo auth model is an httpOnly cookie holding a user id. There is no password and no
  email verification — fine for a local demo, not for production. Replace it before exposing
  the port publicly, and set `WEBHOOK_TOKEN`.
- TikTok and Instagram render much of their metadata client-side, so `fetch_video_meta` gets
  what is in the served HTML; YouTube Shorts captions are the most reliable source.
- Content is generated from public page metadata. Don't republish clips you don't have the
  rights to.
