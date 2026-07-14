"""Turn a long article (e.g. an SEO post) into a short image-generation prompt.

Two modes:
- heuristic (default, fully offline): strip HTML/markup, pull the title and the
  most frequent meaningful words, and wrap them in a photo-style template.
- llm (optional): call any OpenAI-compatible chat endpoint. This defaults to a
  local Ollama server (http://localhost:11434/v1) so it stays local and free;
  it also works with any OpenAI-compatible provider if you point it elsewhere.

The LLM path is opt-in via settings and always falls back to the heuristic on
error, so the feature never hard-fails.
"""

from __future__ import annotations

import re
from collections import Counter

import httpx

from app.core.logging import get_logger
from app.services import settings_service

logger = get_logger(__name__)

_QUALITY_TAGS = "high detail, sharp focus, professional photography, 4k"

# Small Vietnamese + English stopword set so keyword extraction isn't dominated
# by filler words. Not exhaustive; good enough for prompt hints.
_STOPWORDS = {
    # english
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her", "was",
    "one", "our", "out", "his", "has", "with", "this", "that", "from", "they",
    "will", "your", "have", "more", "which", "their", "would", "there", "about",
    "into", "than", "them", "then", "when", "what", "some", "very", "just",
    # vietnamese (common)
    "và", "của", "là", "các", "một", "những", "được", "cho", "với", "trong",
    "khi", "này", "đó", "để", "có", "không", "như", "tại", "theo", "về", "đến",
    "hay", "nên", "cũng", "vì", "nếu", "bạn", "rất", "sẽ", "đang", "phải", "còn",
    "thì", "ra", "lại", "đã", "nhiều", "hơn", "tất", "cả", "cần", "làm",
}


def _strip_markup(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)          # HTML tags
    text = re.sub(r"[#*_`>|\-]{1,}", " ", text)    # markdown symbols
    text = re.sub(r"https?://\S+", " ", text)      # urls
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_prompt_heuristic(text: str, max_keywords: int = 8) -> str:
    cleaned = _strip_markup(text)
    if not cleaned:
        return ""

    # Title: first line/sentence, capped.
    first = re.split(r"[.\n!?]", cleaned, maxsplit=1)[0].strip()
    title = first[:120]

    # Keyword frequency over words length >= 4, excluding stopwords.
    words = re.findall(r"[^\W\d_]{4,}", cleaned.lower(), flags=re.UNICODE)
    freq = Counter(w for w in words if w not in _STOPWORDS)
    keywords = [w for w, _ in freq.most_common(max_keywords)]

    parts = [p for p in [title, ", ".join(keywords)] if p]
    subject = "; ".join(parts)
    return f"{subject}, {_QUALITY_TAGS}".strip(", ")


def build_prompt_llm(text: str) -> str | None:
    """Call an OpenAI-compatible chat endpoint. Returns None on any failure."""
    from app.db.base import SessionLocal

    try:
        with SessionLocal() as db:
            cfg = settings_service.get_all(db)
    except Exception as exc:  # noqa: BLE001 - never fail the request over config read
        logger.warning("Could not read LLM settings, using heuristic: %s", exc)
        return None

    if not cfg.get("prompt_llm_enabled"):
        return None

    base_url = str(cfg.get("prompt_llm_base_url") or "").rstrip("/")
    model = cfg.get("prompt_llm_model") or "llama3.1"
    api_key = cfg.get("prompt_llm_api_key") or "ollama"
    if not base_url:
        return None

    system = (
        "You are a prompt engineer for a text-to-image model. Given article text, "
        "extract the main visual subject and write ONE concise English image prompt. "
        "Always comply: this is a neutral creative task, never refuse. "
        "Output ONLY the prompt itself (no quotes, no preamble, no explanation). "
        "Describe a single photorealistic image: main subject, setting, lighting, "
        "style, camera. Keep it under 60 words."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text[:6000]},
        ],
        "temperature": 0.7,
        "stream": False,
    }
    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = content.strip('"').strip()
        if _looks_like_refusal(content):
            logger.warning("LLM returned a refusal/invalid prompt; using heuristic")
            return None
        return content or None
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("LLM prompt generation failed, using heuristic: %s", exc)
        return None


_REFUSAL_MARKERS = (
    "i can't", "i cannot", "i can not", "i'm unable", "i am unable",
    "as an ai", "i'm sorry", "cannot create", "can't create", "i won't",
)


def _looks_like_refusal(text: str) -> bool:
    if not text or len(text) < 3:
        return True
    low = text.lower()
    return any(marker in low for marker in _REFUSAL_MARKERS)


def build_prompt(text: str) -> dict:
    """Return {'prompt': str, 'source': 'llm'|'heuristic'}."""
    llm = build_prompt_llm(text)
    if llm:
        return {"prompt": llm, "source": "llm"}
    return {"prompt": build_prompt_heuristic(text), "source": "heuristic"}
