"""Autonomous directory submission engine.

Submits the product to a curated list of startup / AI-tool directories. Two
submission modes:

  "get"  - the directory has no public form endpoint (login or captcha gated).
           We build the prefilled submission URL and record it as a MANUAL action.
  "post" - a public form endpoint exists; we POST the payload and record the
           HTTP status we got back.

Every run is logged to the submissions table and to a JSONL file so it can be
re-run, audited and resumed. DRY_RUN=1 performs everything except the final
network call.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .config import settings
from . import database as db

log = logging.getLogger("viral_shredder.marketing")

DIRECTORIES_FILE = Path(__file__).resolve().parent.parent / "static" / "data" / "directories.json"
LOG_FILE = Path(__file__).resolve().parent.parent / "submissions.jsonl"


@dataclass
class SubmissionResult:
    directory: str
    url: str
    mode: str
    status: str
    detail: str = ""
    http_code: int | None = None
    payload: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "directory": self.directory,
            "url": self.url,
            "mode": self.mode,
            "status": self.status,
            "detail": self.detail,
            "http_code": self.http_code,
            "payload": self.payload,
            "ts": time.time(),
        }


def default_product() -> dict:
    """Product facts used to fill directory submission forms."""
    return {
        "name": "Viral Shredder",
        "tagline": "Turn TikTok, Reels and Shorts links into SEO articles, X threads and LinkedIn posts",
        "url": "http://127.0.0.1:8000",
        "description": (
            "Viral Shredder is an AI content repurposing tool. Paste a link to any "
            "TikTok video, Instagram Reel or YouTube Short and it extracts the script, "
            "ranks the key ideas and writes a full SEO article, an X thread and a "
            "LinkedIn post from the same clip - so one video feeds a week of content."
        ),
        "category": "AI Tools",
        "topics": ["AI", "Marketing", "Content Creation", "SEO", "Social Media"],
        "pricing": "Freemium - $9/month Pro",
        "contact_email": "support@viralshredder.app",
        "twitter": "@avdv3",
    }


def load_directories() -> list[dict]:
    if not DIRECTORIES_FILE.exists():
        return []
    try:
        data = json.loads(DIRECTORIES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.error("could not read directories.json: %s", exc)
        return []


def _query(params: dict) -> str:
    return urllib.parse.urlencode({k: v for k, v in params.items() if v})


def submit_one(entry: dict, product: dict, dry_run: bool = False,
               client: httpx.Client | None = None) -> SubmissionResult:
    mode = (entry.get("mode") or "get").lower()
    submit_url = entry["submit_url"]
    name = entry["name"]
    base = {
        "name": product["name"],
        "tagline": product["tagline"],
        "url": product["url"],
        "email": product["contact_email"],
        "description": product["description"],
        "category": product["category"],
        "topics": ", ".join(product["topics"]),
        "price": product["pricing"],
    }

    if dry_run:
        return SubmissionResult(name, submit_url, mode, "dry_run",
                                "payload prepared, network call skipped", None, base)

    if mode == "post":
        own_client = client is None
        client = client or httpx.Client(timeout=30.0, follow_redirects=True)
        try:
            resp = client.post(submit_url, data=base,
                               headers={"User-Agent": "ViralShredderBot/1.0"})
            code = resp.status_code
            ok = code < 500
            return SubmissionResult(
                name, submit_url, "post", "submitted" if ok else "failed",
                f"HTTP {code}", code, base,
            )
        except Exception as exc:
            return SubmissionResult(name, submit_url, "post", "error", str(exc), None, base)
        finally:
            if own_client:
                client.close()

    # mode == "get": build a prefilled URL the operator opens once.
    prefill = {k: v for k, v in base.items() if k in ("name", "tagline", "url", "email")}
    ready = f"{submit_url}?{_query(prefill)}"
    return SubmissionResult(name, ready, "get", "manual",
                            "Open this URL and submit the prefilled form.", None, base)


def run_submission(dry_run: bool = False,
                   only: list[str] | None = None) -> list[SubmissionResult]:
    """Submit to every directory. Autonomous: no human input required per site."""
    product = default_product()
    directories = load_directories()
    if only:
        wanted = {o.lower() for o in only}
        directories = [d for d in directories if d["name"].lower() in wanted]

    results: list[SubmissionResult] = []
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for entry in directories:
            try:
                result = submit_one(entry, product, dry_run=dry_run, client=client)
            except Exception as exc:
                result = SubmissionResult(
                    entry.get("name", "?"), entry.get("submit_url", ""),
                    "unknown", "error", str(exc), None,
                )
            results.append(result)
            db.record_submission(result.directory, result.url, result.status,
                                 result.as_dict())
            _append_log(result)
            log.info("[%s] %s -> %s %s", result.mode, result.directory,
                     result.status, result.http_code or "")
            time.sleep(1.0)  # be polite between submissions

    return results


def _append_log(result: SubmissionResult) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result.as_dict(), ensure_ascii=False) + "\n")
    except Exception:  # pragma: no cover - logging must never break a run
        pass


def summary(results: list[SubmissionResult]) -> dict:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {"total": len(results), "by_status": counts}
