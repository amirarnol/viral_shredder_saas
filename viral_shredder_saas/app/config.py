"""Application configuration.

Values are read from environment variables / .env with sensible defaults so the
app runs out of the box with `python run.py`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv is optional; .env is also picked up by the shell
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # pragma: no cover - dotenv not installed
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def _get(key: str, default: str) -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class Settings:
    # --- server -----------------------------------------------------------
    host: str = _get("HOST", "127.0.0.1")
    port: int = int(_get("PORT", "8000"))

    # --- database ---------------------------------------------------------
    database_url: str = _get("DATABASE_URL", "sqlite:///viral_shredder.db")

    # --- payments ---------------------------------------------------------
    payment_demo_mode: bool = _get("PAYMENT_DEMO_MODE", "1") == "1"
    payment_demo_confirm_after: int = int(_get("PAYMENT_DEMO_CONFIRM_AFTER", "45"))
    pro_plan_price_usd: int = int(_get("PRO_PLAN_PRICE_USD", "9"))

    # --- wallets ----------------------------------------------------------
    usdt_trc20_wallet: str = _get(
        "USDT_TRC20_WALLET", "TKcGim9AWivJhySpbuR7FHC738anMsSSz3"
    )
    usdt_bep20_wallet: str = _get(
        "USDT_BEP20_WALLET", "0xee2d811a8c7c851c54fb2695f458983028e6a9fa"
    )
    binance_id: str = _get("BINANCE_ID", "736985053")

    # --- support ----------------------------------------------------------
    whatsapp_number: str = _get("WHATSAPP_NUMBER", "963934641795")
    telegram_username: str = _get("TELEGRAM_USERNAME", "avdv3")

    # --- optional LLM -----------------------------------------------------
    llm_api_base: str = _get("LLM_API_BASE", "")
    llm_api_key: str = _get("LLM_API_KEY", "")
    llm_model: str = _get("LLM_MODEL", "")

    @property
    def sqlite_path(self) -> Path:
        url = self.database_url
        if url.startswith("sqlite:///"):
            return BASE_DIR / url.replace("sqlite:///", "", 1)
        return BASE_DIR / "viral_shredder.db"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_base and self.llm_api_key and self.llm_model)


settings = Settings()


PLANS = {
    "free": {
        "id": "free",
        "name": "Free",
        "price_usd": 0,
        "credits_per_month": 5,
        "max_input_chars": 4000,
        "outputs": ["seo_article", "x_thread"],
        "stripe_like_description": "5 credits / month, SEO article + X thread",
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price_usd": 9,
        "credits_per_month": 150,
        "max_input_chars": 40000,
        "outputs": ["seo_article", "x_thread", "linkedin_post"],
        "stripe_like_description": "150 credits / month, all output formats",
    },
}


def plan_for(plan_id: str) -> dict:
    return PLANS.get(plan_id, PLANS["free"])
