"""The Content Shredder.

Pipeline:  video URL -> platform parse -> page metadata -> transcript/captions
           -> keyword + sentence scoring -> SEO article / X thread / LinkedIn post.

The local engine is fully offline and deterministic. It does real work:
stopword-filtered term-frequency keyword extraction, sentence scoring by
keyword overlap and position, then structured generation around the ranked
material. If an OpenAI-compatible endpoint is configured it is used to polish
the draft; otherwise the extractive output is returned as-is.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field

import httpx

from .config import settings
from .localization import (
    DEFAULT_LANGUAGE,
    DEFAULT_TONE,
    is_rtl,
    headline_niche,
    language_name,
    localize_niche,
    resolve,
    tone_label,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "also", "just", "like", "get", "got", "really",
    "much", "many", "even", "still", "back", "thing", "things", "make", "makes",
    "made", "go", "going", "one", "two", "us", "our", "im", "ive", "dont", "cant",
    "wont", "yeah", "yes", "okay", "ok", "lol", "omg", "ah", "oh", "um", "uh",
}

# Hashtags that carry real topical signal on short-form video platforms.
TOPIC_HASHTAGS = {
    "fitness": "fitness",
    "gym": "fitness",
    "workout": "fitness",
    "marketing": "marketing",
    "digitalmarketing": "marketing",
    "seo": "marketing",
    "ai": "artificial intelligence",
    "tech": "technology",
    "coding": "programming",
    "programming": "programming",
    "finance": "finance",
    "investing": "finance",
    "crypto": "cryptocurrency",
    "business": "business",
    "entrepreneur": "business",
    "startup": "business",
    "food": "food",
    "recipe": "food",
    "cooking": "food",
    "travel": "travel",
    "fashion": "fashion",
    "beauty": "beauty",
    "gaming": "gaming",
    "music": "music",
    "education": "education",
    "tutorial": "education",
    "howto": "education",
    "motivation": "self-improvement",
    "productivity": "self-improvement",
    "health": "health",
    "wellness": "health",
}

_TWEET_MAX = 270  # leave headroom for a thread numbering suffix

# Used when the page metadata carries no author name.
DEFAULT_AUTHOR = "the creator"


# ------------------------------------------------------------------ models
@dataclass
class VideoMeta:
    url: str
    platform: str
    video_id: str
    title: str = ""
    author: str = ""
    description: str = ""
    thumbnail: str = ""
    transcript: str = ""
    hashtags: list[str] = field(default_factory=list)

    @property
    def corpus(self) -> str:
        """All usable source text for generation."""
        parts = [p.strip() for p in (self.title, self.description, self.transcript) if p and p.strip()]
        return "\n".join(parts)


@dataclass
class ShredResult:
    job_id: int
    platform: str
    title: str
    source_url: str
    seo_article: dict
    x_thread: list[str]
    linkedin_post: str
    keywords: list[str]
    meta: dict


# ------------------------------------------------------------- URL parsing
def parse_video_url(url: str) -> tuple[str, str]:
    """Return (platform, video_id) for a supported short-form video URL."""
    raw = url.strip()
    if not raw:
        raise ValueError("No URL provided.")

    try:
        parsed = urllib.parse.urlparse(raw if "://" in raw else "https://" + raw)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"Unreadable URL: {exc}") from exc

    host = (parsed.netloc or "").lower()
    path = parsed.path or "/"
    query_id = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]

    if "tiktok.com" in host:
        m = re.search(r"/video/(\d+)", path)
        vid = m.group(1) if m else (query_id or path.strip("/").split("/")[-1])
        return "tiktok", vid or "unknown"

    if "instagram.com" in host:
        m = re.search(r"/(?:reel|reels|p|tv)/([^/]+)", path)
        return "instagram", (m.group(1) if m else "unknown")

    if ("youtube.com" in host or "youtu.be" in host) or "shorts" in path:
        if "youtu.be" in host:
            return "youtube", path.strip("/").split("/")[0] or "unknown"
        m = re.search(r"/shorts/([^/?]+)", path)
        if m:
            return "youtube", m.group(1)
        vid = query_id or urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        if vid:
            return "youtube", vid
        raise ValueError("Could not find a video id in that YouTube link.")

    if "facebook.com" in host or "fb.watch" in host:
        return "facebook", path.strip("/").split("/")[-1] or "unknown"

    # Fall back: treat as a generic public video page so the tool still works.
    return "web", path.strip("/").split("/")[-1] or host


# --------------------------------------------------------- page fetch + og
def _extract_og(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for prop in ("og:title", "og:description", "og:image", "og:site_name",
                 "twitter:title", "twitter:description", "twitter:image"):
        m = re.search(
            r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]*>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            tag = m.group(0)
            cm = re.search(r'content=["\'](.+?)["\']', tag, re.DOTALL)
            if cm and prop not in out:
                out[prop] = _decode(cm.group(1)).strip()
    # JSON-LD fallback
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                            html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        if isinstance(data, dict):
            name = data.get("name") or data.get("headline")
            desc = data.get("description")
            if name and "og:title" not in out:
                out["og:title"] = str(name)
            if desc and "og:description" not in out:
                out["og:description"] = str(desc)
            author = data.get("author")
            if isinstance(author, dict) and author.get("name"):
                out["author"] = str(author["name"])
    return out


def _decode(text: str) -> str:
    text = html_unescape(text)
    try:
        return unicodedata.normalize("NFKC", text)
    except Exception:  # pragma: no cover
        return text


def html_unescape(text: str) -> str:
    return (text.replace("&amp;", "&").replace("&quot;", '"')
                .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&nbsp;", " "))


def fetch_video_meta(url: str, timeout: float = 20.0) -> VideoMeta:
    platform, video_id = parse_video_url(url)
    meta = VideoMeta(url=url.strip(), platform=platform, video_id=video_id)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Follow redirects once: short links (vt.tiktok.com, instagram share URLs) resolve here.
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            resp = client.get(meta.url)
            body = resp.text
            final_url = str(resp.url)
    except Exception as exc:
        # Network blocked / region-locked. We still shred whatever the URL itself gives us.
        meta.title = f"{platform.capitalize()} video {video_id}"
        meta.description = ""
        meta.transcript = ""
        return meta

    if final_url != meta.url:
        # A redirect can point at a consent/interstitial page (YouTube does this
        # per region). Only adopt the resolved URL when it still names a video -
        # never let a redirect throw away an id we already parsed from the input.
        try:
            platform2, video_id2 = parse_video_url(final_url)
        except ValueError:
            platform2, video_id2 = meta.platform, meta.video_id
        if video_id2 != "unknown":
            meta.url, meta.platform, meta.video_id = final_url, platform2, video_id2

    og = _extract_og(body)
    meta.title = og.get("og:title") or og.get("twitter:title") or ""
    meta.description = og.get("og:description") or og.get("twitter:description") or ""
    meta.thumbnail = og.get("og:image") or og.get("twitter:image") or ""
    meta.author = og.get("author") or og.get("og:site_name") or ""

    meta.hashtags = list(dict.fromkeys(re.findall(r"#([A-Za-z0-9_]{2,40})", body)))

    # Captions are rarely embedded in the public HTML; try the YouTube timedtext
    # endpoint for shorts, and always fall back to the description text.
    meta.transcript = _fetch_transcript(meta, headers, timeout)

    if not meta.title:
        slug = re.sub(r"[-_]+", " ", urllib.parse.unquote(meta.video_id)).strip()
        meta.title = (slug or f"{platform.capitalize()} video").strip().title()

    return meta


def _fetch_transcript(meta: VideoMeta, headers: dict, timeout: float) -> str:
    if meta.platform != "youtube":
        return ""
    captions_url = (
        "https://www.youtube.com/api/timedtext"
        f"?v={meta.video_id}&lang=en&fmt=json3"
    )
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            resp = client.get(captions_url)
        data = resp.json()
        events = data.get("events", [])
        parts = [
            "".join(seg.get("utf8", "") for seg in ev.get("segs", []))
            for ev in events
        ]
        text = " ".join(p for p in parts if p)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


# ------------------------------------------------------------ text engine
def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [c.strip(" -•·") for c in chunks if len(c.strip()) > 25]


def extract_keywords(text: str, limit: int = 12) -> list[tuple[str, float]]:
    """Stopword-filtered term frequency with length + hashtag weighting."""
    tokens = re.findall(r"[A-Za-z0-9']+", text.lower())
    freq: dict[str, float] = {}
    for tok in tokens:
        if len(tok) < 3 or tok in STOPWORDS or tok.isdigit():
            continue
        freq[tok] = freq.get(tok, 0.0) + 1.0
    if not freq:
        return []
    total = sum(freq.values())
    for tok, count in freq.items():
        freq[tok] = (count / total) * 100.0
        if len(tok) > 7:
            freq[tok] *= 1.15
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:limit]


def score_sentences(sentences: list[str], keywords: list[str],
                    max_sentences: int) -> list[tuple[int, float]]:
    """Extractive rank: keyword overlap + early-position bonus + length bonus.

    `keywords` is an ordered list (strongest first); weight decays with rank so a
    sentence covering the top keyword outscores one covering the tenth.
    """
    kw = {k: 1.0 / (rank + 1) for rank, k in enumerate(keywords)}
    scored = []
    n = len(sentences)
    for idx, sent in enumerate(sentences):
        toks = {t for t in re.findall(r"[A-Za-z0-9']+", sent.lower()) if len(t) >= 3}
        if not toks:
            continue
        hits = toks & set(kw)
        if not hits:
            continue
        overlap = sum(kw[t] for t in hits) / math.sqrt(len(toks))
        position = 1.0 / (1.0 + idx)  # lead sentences matter in short video scripts
        length = min(len(sent), 200) / 200.0
        scored.append((idx, overlap + (0.35 * position) + (0.15 * length)))
    scored.sort(key=lambda item: -item[1])
    chosen = sorted(scored[:max_sentences], key=lambda item: item[0])
    return chosen


def _topic_niche(meta: VideoMeta, keywords: list[str]) -> str:
    tag_hits = [TOPIC_HASHTAGS[h.lower().lstrip("#")] for h in meta.hashtags
                if h.lower().lstrip("#") in TOPIC_HASHTAGS]
    if tag_hits:
        return tag_hits[0]
    kw_set = {k.lower() for k in keywords}
    for tag, niche in TOPIC_HASHTAGS.items():
        if tag in kw_set:
            return niche
    # The fallback is the bare adjectival form: every string that interpolates a
    # niche already supplies its own noun ("this {niche} video", "a {niche} clip"),
    # so a noun here would duplicate it.
    return "short-form"


def _clean_sentence(s: str) -> str:
    s = s.strip()
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if s and s[-1] not in ".!?\"'":
        s += "."
    return s


# ------------------------------------------------------------- generators
def build_seo_article(meta: VideoMeta, keywords: list[str],
                      tone: str = DEFAULT_TONE, language: str = DEFAULT_LANGUAGE) -> dict:
    corpus = meta.corpus
    sentences = split_sentences(corpus)
    niche_raw = _topic_niche(meta, keywords)
    niche = localize_niche(niche_raw, language)
    top_kw = list(keywords)
    author = meta.author or DEFAULT_AUTHOR

    def t(key: str, **fmt) -> str:
        return resolve(key, language, tone, **fmt)

    picked = score_sentences(sentences, keywords[:8], max_sentences=10)
    body_sentences = [_clean_sentence(sentences[i]) for i, _ in picked]
    if not body_sentences:
        body_sentences = [t("fallback_body", niche=niche)]

    niche_h = headline_niche(niche, language)
    headline_topic = top_kw[0].title() if top_kw else niche_h
    if headline_topic.lower() == niche.lower():
        title = t("title_playbook", niche=niche_h)
    else:
        title = t("title_breakdown", topic=headline_topic, niche=niche_h)

    # ASCII-fold accents (cafe->cafe) so slugs stay URL-safe in every language;
    # non-Latin scripts fold to nothing and fall back to a safe slug below.
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")[:70]
    if not slug:
        slug = f"article-{language}"

    primary = top_kw[0] if top_kw else niche
    secondary = top_kw[1:4] if len(top_kw) > 1 else [niche]
    if len(secondary) > 1:
        rest = (", " + ", ".join(secondary[:-1]) + " " + t("and")
                + " " + secondary[-1])
    else:
        rest = ""
    meta_desc = t("meta_desc", niche=niche, author=author, primary=primary,
                  rest=rest)[:158]

    takeaways = [
        t("take1", Primary=primary.title()),
        t("take2", Secondary=secondary[0].title() if secondary else niche_h),
        t("take3"),
    ]
    # Attach a sourced sentence to each takeaway when we have enough material.
    for i, sent in enumerate(body_sentences[1:4]):
        if i < len(takeaways):
            takeaways[i] += t("take_source", sentence=_clean_sentence(sent).rstrip("."))

    sections = [
        (
            t("sec_standout", niche=niche),
            [
                t("intro_p1", niche=niche, body0=body_sentences[0]),
                t("intro_p2", author=author),
            ],
        ),
        (
            t("sec_core"),
            body_sentences[1:5] if len(body_sentences) > 1 else body_sentences or
            [t("fallback_core", primary=primary)],
        ),
        (t("sec_takeaways"), takeaways),
        (
            t("sec_apply"),
            [
                t("apply_p1", primary=primary),
                t("apply_p2"),
                t("apply_p3"),
            ],
        ),
    ]
    if len(body_sentences) > 4:
        sections.append((t("sec_transcript"), body_sentences[4:]))

    # FAQ section generated from the ranked keywords - good for SEO and long tail.
    faq = []
    for kw in top_kw[:4]:
        faq.append(t("faq_q", kw=kw))
        match = next((s for s in body_sentences if kw in s.lower()), None)
        faq.append(_clean_sentence(match) if match else t("faq_a_none", kw=kw))
    sections.append((t("sec_faq"), faq))

    sections.append((t("sec_bottom"), [t("bottom_p1", primary=primary)]))

    word_count = sum(
        len(re.findall(r"\w+", para))
        for _, paras in sections
        for para in paras
    )

    return {
        "title": title,
        "slug": slug,
        "meta_description": meta_desc,
        "focus_keyword": primary,
        "secondary_keywords": secondary,
        "tags": (meta.hashtags[:6] if meta.hashtags else [niche_raw.replace(" ", "-")] + top_kw[:4]),
        "word_count": word_count,
        "language": language,
        "language_name": language_name(language),
        "tone": tone,
        "tone_name": tone_label(tone),
        "direction": "rtl" if is_rtl(language) else "ltr",
        "sections": [{"heading": h, "paragraphs": [p for p in paras if p]}
                     for h, paras in sections],
    }


def build_x_thread(meta: VideoMeta, keywords: list[str], article: dict,
                   tone: str = DEFAULT_TONE, language: str = DEFAULT_LANGUAGE) -> list[str]:
    corpus = meta.corpus
    sentences = split_sentences(corpus)
    picked = [sentences[i] for i, _ in score_sentences(sentences, keywords[:8], 8)]
    if not picked:
        picked = [meta.description or meta.title]

    niche = localize_niche(_topic_niche(meta, keywords), language)
    primary = keywords[0] if keywords else niche

    def t(key: str, **fmt) -> str:
        return resolve(key, language, tone, **fmt)

    tweets: list[str] = []
    tweets.append(t("thread_hook", niche=niche, primary=primary, n=9))

    for sent in picked[:6]:
        clean = _clean_sentence(sent)
        if len(clean) > _TWEET_MAX:
            clean = _truncate_at_word(clean, _TWEET_MAX)
        tweets.append(clean)

    tweets.append(t("thread_steal", primary=primary))
    tweets.append(t("thread_cta", niche=niche))

    numbered: list[str] = []
    n = len(tweets)
    for i, tw in enumerate(tweets, start=1):
        if i > 1:
            tw = f"{tw} ({i}/{n})"
        numbered.append(tw)
    return numbered


def build_linkedin_post(meta: VideoMeta, keywords: list[str], article: dict,
                        tone: str = DEFAULT_TONE, language: str = DEFAULT_LANGUAGE) -> str:
    corpus = meta.corpus
    sentences = split_sentences(corpus)
    picked = [sentences[i] for i, _ in score_sentences(sentences, keywords[:8], 5)]
    niche_raw = _topic_niche(meta, keywords)
    niche = localize_niche(niche_raw, language)
    primary = keywords[0] if keywords else niche

    def t(key: str, **fmt) -> str:
        return resolve(key, language, tone, **fmt)

    if picked:
        body = "\n\n".join(_clean_sentence(s) for s in picked)
    else:
        body = t("li_fallback", primary=primary)

    hashtags = " ".join(
        f"#{h.lstrip('#')}" for h in (meta.hashtags[:5] if meta.hashtags
                                      else [niche_raw.replace(" ", ""), "contentstrategy",
                                            "repurposing", "shortformvideo"])
    )

    return (
        f"{t('li_opener', niche=niche)}\n\n"
        f"{t('li_body_intro')}\n\n"
        f"{body}\n\n"
        f"{t('li_close')}\n\n"
        f"{t('li_link')}\n\n"
        f"{hashtags}"
    )


def _truncate_at_word(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip() + "…"


# --------------------------------------------------------------- optional
def llm_polish(meta: VideoMeta, draft: ShredResult, tone: str = DEFAULT_TONE,
               language: str = DEFAULT_LANGUAGE) -> ShredResult:
    """Replace the extractive draft with an LLM rewrite when an endpoint is set.

    Failure is non-fatal: we return the original draft untouched.
    """
    if not settings.llm_enabled:
        return draft
    prompt = (
        "You are a multilingual content repurposing engine. Rewrite the following "
        "draft assets about a short-form video.\n\n"
        f"TARGET LANGUAGE: {language_name(language)}. Write EVERYTHING (titles, "
        f"headings, meta description, tweets, post) in {language_name(language)}. "
        f"Never leave English fragments in the output.\n"
        f"TONE: {tone_label(tone)}.\n\n"
        "Keep the structure and the facts, improve flow, keep the SEO keywords, and "
        "stay under X's 280 character limit per tweet. Return strict JSON with keys: "
        "article_title, meta_description, article_paragraphs (list of strings), "
        "thread (list of strings), linkedin (string).\n\n"
        f"SOURCE TITLE: {meta.title}\nSOURCE DESCRIPTION: {meta.description}\n"
        f"TRANSCRIPT: {meta.transcript[:3000]}\nKEYWORDS: {', '.join(draft.keywords)}\n\n"
        f"DRAFT ARTICLE: {json.dumps(draft.seo_article)[:4000]}\n"
        f"DRAFT THREAD: {json.dumps(draft.x_thread)[:2000]}\n"
        f"DRAFT LINKEDIN: {draft.linkedin_post[:2000]}"
    )
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(
                settings.llm_api_base.rstrip("/") + "/chat/completions",
                json=payload, headers=headers,
            )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception:
        return draft

    try:
        art = draft.seo_article
        art["title"] = parsed.get("article_title", art["title"])
        art["meta_description"] = parsed.get("meta_description", art["meta_description"])
        paras = [p for p in parsed.get("article_paragraphs", []) if isinstance(p, str)]
        if paras:
            art["sections"] = [{"heading": art["title"], "paragraphs": paras}]
        thread = [t for t in parsed.get("thread", []) if isinstance(t, str)]
        if thread:
            draft.x_thread = thread
        if isinstance(parsed.get("linkedin"), str) and parsed["linkedin"].strip():
            draft.linkedin_post = parsed["linkedin"].strip()
        draft.seo_article = art
    except Exception:
        return draft
    return draft


# ------------------------------------------------------------------ entry
def shred(url: str, job_id: int = 0, tone: str = DEFAULT_TONE,
          language: str = DEFAULT_LANGUAGE) -> ShredResult:
    meta = fetch_video_meta(url)
    corpus = meta.corpus

    keywords = [k for k, _ in extract_keywords(corpus)]
    if not keywords and meta.hashtags:
        keywords = [h.lstrip("#").lower() for h in meta.hashtags[:8]]

    article = build_seo_article(meta, keywords, tone=tone, language=language)
    thread = build_x_thread(meta, keywords, article, tone=tone, language=language)
    linkedin = build_linkedin_post(meta, keywords, article, tone=tone, language=language)

    result = ShredResult(
        job_id=job_id,
        platform=meta.platform,
        title=meta.title,
        source_url=meta.url,
        seo_article=article,
        x_thread=thread,
        linkedin_post=linkedin,
        keywords=keywords,
        meta={
            "author": meta.author,
            "video_id": meta.video_id,
            "thumbnail": meta.thumbnail,
            "hashtags": meta.hashtags[:10],
            "transcript_chars": len(meta.transcript),
            "corpus_chars": len(corpus),
            "generator": "llm" if settings.llm_enabled else "local-extractive",
            "language": language,
            "language_name": language_name(language),
            "tone": tone,
            "tone_name": tone_label(tone),
            "direction": "rtl" if is_rtl(language) else "ltr",
        },
    )
    return llm_polish(meta, result, tone=tone, language=language)
