"""Create a tangible, layout-aware visual brief from short user input."""

from __future__ import annotations

import json
import unicodedata

import httpx
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.schemas.creative import CreativeBriefInput, CreativePackageOut, VisualBrief
from app.services import prompt_composer, settings_service
from app.services.style_presets import get_style

logger = get_logger(__name__)


_SUBJECT_RULES: list[tuple[tuple[str, ...], dict]] = [
    (("cloud", "kubernetes", "k8s", "server", "data center", "du lieu dam may", "ha tang"), {
        "subject": "a row of modern enterprise server racks as the clear hero subject",
        "objects": ["real network switches", "organized fiber cables", "status lights", "cooling infrastructure"],
        "environment": "a clean contemporary hyperscale data center with believable engineering details",
        "action": "operating as a connected cloud computing cluster with subtle active status lights",
    }),
    (("an ninh mang", "bao mat", "malware", "ransomware", "zero trust"), {
        "subject": "a professional cybersecurity operations workstation as the clear hero subject",
        "objects": ["multiple security monitoring displays", "network hardware", "analyst keyboard", "server rack"],
        "environment": "a realistic modern security operations center",
        "action": "monitoring a live enterprise network for credible security threats",
    }),
    (("database", "co so du lieu", "sql", "postgres", "du lieu"), {
        "subject": "modern enterprise database servers as the clear physical hero subject",
        "objects": ["organized server racks", "storage arrays", "network switches", "subtle status lights"],
        "environment": "a realistic contemporary data infrastructure facility",
        "action": "processing and replicating business data across connected systems",
    }),
    (("may tinh", "cong nghe", "phan mem", "ai", "laptop", "internet"), {
        "subject": "a Vietnamese professional actively working at a modern desktop computer",
        "objects": ["desktop monitor", "keyboard", "smartphone", "notebook"],
        "environment": "a believable modern workspace with practical technology",
        "action": "focused on completing meaningful digital work",
    }),
    (("tai chinh", "dau tu", "ngan hang", "kinh doanh", "doanh nghiep"), {
        "subject": "a Vietnamese small-business owner reviewing a financial plan on a laptop",
        "objects": ["laptop", "printed charts", "calculator", "coffee cup"],
        "environment": "a contemporary small-business office",
        "action": "making a confident evidence-based business decision",
    }),
    (("giao duc", "hoc tap", "sinh vien", "truong hoc", "dao tao"), {
        "subject": "a Vietnamese student learning with a teacher in an active study session",
        "objects": ["open books", "laptop", "notebook", "learning materials"],
        "environment": "a bright modern learning space",
        "action": "discussing and applying a practical new idea",
    }),
    (("suc khoe", "y te", "bac si", "benh vien", "dinh duong"), {
        "subject": "a Vietnamese healthcare professional helping a patient understand practical care",
        "objects": ["tablet", "medical notes", "simple health equipment"],
        "environment": "a clean welcoming healthcare setting",
        "action": "giving clear attentive guidance",
    }),
    (("san pham", "thiet bi", "dien thoai", "may anh", "dong ho"), {
        "subject": "one premium physical product presented as the unmistakable hero subject",
        "objects": ["purposeful supporting accessories", "subtle material details"],
        "environment": "a refined commercial studio set grounded in realistic materials",
        "action": "displayed from its most useful and recognizable angle",
    }),
    (("marketing", "quang cao", "noi dung", "thuong hieu", "mang xa hoi"), {
        "subject": "a Vietnamese creative team shaping a campaign around a table",
        "objects": ["campaign sketches", "laptop", "camera", "color swatches"],
        "environment": "a working creative studio with real production tools",
        "action": "turning a clear strategy into visual content",
    }),
]


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char)).replace("đ", "d")


def _safe_area(position: str) -> tuple[str, str]:
    if position == "right":
        return "subject on the left third, visual flow toward the center", "right 42 percent"
    if position == "bottom":
        return "subject in the upper-center area with grounded depth", "bottom 32 percent"
    return "subject on the right third, visual flow toward the center", "left 42 percent"


def _fallback_brief(req: CreativeBriefInput) -> VisualBrief:
    style = get_style(req.style_preset)
    search_text = _plain(" ".join([req.title_text, req.topic, req.content_summary]))
    selected = None
    for keywords, rule in _SUBJECT_RULES:
        if any(keyword in search_text for keyword in keywords):
            selected = rule
            break
    if selected is None:
        selected = {
            "subject": "a Vietnamese professional interacting with meaningful real-world tools",
            "objects": ["recognizable practical objects", "a clear contextual prop", "a working surface"],
            "environment": "a believable contemporary setting directly connected to the topic",
            "action": "demonstrating the central idea through a clear purposeful action",
        }

    composition, text_safe_area = _safe_area(req.title_position)
    required = list(dict.fromkeys([*req.must_include]))
    avoid = list(dict.fromkeys([
        "empty background",
        "plain gradient",
        "floating decorative shapes",
        "text",
        "watermark",
        *req.must_avoid,
    ]))
    topic = req.topic or req.title_text
    return VisualBrief(
        concept=f"A tangible editorial scene that communicates: {topic}",
        primary_subject=selected["subject"],
        supporting_objects=selected["objects"],
        environment=selected["environment"],
        action=selected["action"],
        composition=f"{composition}; {style['layout']}",
        camera=style["camera"],
        lighting=style["lighting"],
        palette=style["palette"],
        mood=style["mood"],
        render_style=style["render_style"],
        text_safe_area=text_safe_area,
        must_include=required,
        must_avoid=avoid,
        confidence=0.72 if selected else 0.58,
    )


def _extract_json(text: str) -> dict:
    clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("LLM did not return a JSON object")
    return json.loads(clean[start : end + 1])


def _flatten_strings(value) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_flatten_strings(item))
        return flattened
    return []


def _as_text(value, fallback: str) -> str:
    values = _flatten_strings(value)
    return ", ".join(values) if values else fallback


def _as_list(value, fallback: list[str]) -> list[str]:
    values = _flatten_strings(value)
    return values or fallback


def _llm_brief(req: CreativeBriefInput, db: Session) -> VisualBrief | None:
    cfg = settings_service.get_all(db)
    if not cfg.get("prompt_llm_enabled"):
        return None
    base_url = str(cfg.get("prompt_llm_base_url") or "").rstrip("/")
    if not base_url:
        return None

    style = get_style(req.style_preset)
    composition, text_safe_area = _safe_area(req.title_position)
    system = """You are an art director for commercial editorial images. Convert the user's Vietnamese content into one concrete English visual brief. The image MUST contain a clear person, physical object, or recognizable place unless the user explicitly requests an abstract illustration. Do not put title text or logos inside the generated scene. Return ONLY valid JSON with these exact keys: concept, primary_subject, supporting_objects, environment, action, composition, camera, lighting, palette, mood, render_style, text_safe_area, must_include, must_avoid, confidence. supporting_objects, palette, must_include and must_avoid are arrays. confidence is 0 to 1. All descriptive values must be in English."""
    user_payload = {
        "title": req.title_text,
        "topic": req.topic,
        "summary": req.content_summary[:8000],
        "audience": req.audience,
        "purpose": req.purpose,
        "required_elements": req.must_include,
        "avoid": req.must_avoid,
        "style": style,
        "required_composition": composition,
        "required_text_safe_area": text_safe_area,
    }
    payload = {
        "model": cfg.get("prompt_llm_model") or "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.35,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {cfg.get('prompt_llm_api_key') or 'ollama'}"},
            timeout=90.0,
        )
        response.raise_for_status()
        raw = _extract_json(response.json()["choices"][0]["message"]["content"])
        fallback = _fallback_brief(req)
        primary_subject = _as_text(raw.get("primary_subject"), fallback.primary_subject)
        if primary_subject.lower().strip(" .") in {"person", "a person", "human", "people"}:
            primary_subject = fallback.primary_subject
        action = _as_text(raw.get("action"), fallback.action)
        environment = _as_text(raw.get("environment"), fallback.environment)
        if any("desktop computer" in item.lower() for item in req.must_include):
            action = action.replace("a laptop", "a desktop computer").replace("laptop", "desktop computer")
            environment = environment.replace("a laptop", "a desktop computer").replace("laptop", "desktop computer")

        supporting_objects = _as_list(raw.get("supporting_objects"), fallback.supporting_objects)
        for required in req.must_include:
            if required.lower() not in {"person", "people", "human"} and required not in supporting_objects:
                supporting_objects.append(required)

        data = {
            "concept": _as_text(raw.get("concept"), fallback.concept),
            "primary_subject": primary_subject,
            "supporting_objects": supporting_objects,
            "environment": environment,
            "action": action,
            "composition": composition,
            "camera": _as_text(raw.get("camera"), style["camera"]),
            "lighting": _as_text(raw.get("lighting"), style["lighting"]),
            "palette": _as_list(raw.get("palette"), style["palette"]),
            "mood": _as_text(raw.get("mood"), style["mood"]),
            "render_style": _as_text(raw.get("render_style"), style["render_style"]),
            "text_safe_area": text_safe_area,
            "confidence": raw.get("confidence") if isinstance(raw.get("confidence"), (int, float)) else 0.82,
        }
        data["must_include"] = list(dict.fromkeys([
            *req.must_include,
            *_as_list(raw.get("must_include"), []),
        ]))
        data["must_avoid"] = list(dict.fromkeys([
            "empty background",
            "plain gradient",
            "text",
            "watermark",
            *req.must_avoid,
            *_as_list(raw.get("must_avoid"), []),
        ]))
        brief = VisualBrief.model_validate(data)
        if not brief.primary_subject.strip():
            return None
        return brief
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Creative Director LLM failed; using heuristic brief: %s", exc)
        return None


def canvas_profile(aspect_ratio: str, quality_profile: str, model: str) -> tuple[int, int, int, float]:
    model_name = model.lower().replace("_", "-")
    if "z-image" in model_name:
        # The local Z-Image profile targets CPU-only machines. 1024px takes
        # roughly twenty minutes per image on the supported reference machine.
        long_edge = {"draft": 384, "standard": 512, "publish": 768}[quality_profile]
    else:
        long_edge = {"draft": 512, "standard": 768, "publish": 1024}[quality_profile]
    if aspect_ratio == "1:1":
        width, height = long_edge, long_edge
    elif aspect_ratio == "4:5":
        width, height = (long_edge * 4 // 5 // 8 * 8), long_edge
    elif aspect_ratio == "9:16":
        width, height = (long_edge * 9 // 16 // 8 * 8), long_edge
    else:
        width, height = long_edge, (long_edge * 9 // 16 // 8 * 8)

    if "z-image" in model_name:
        # Z-Image-Turbo is distilled for eight NFEs. More steps do not act like
        # a conventional SD quality control and can reduce consistency.
        steps = 6 if quality_profile == "draft" else 8
        cfg = 1.0
    elif "turbo" in model_name:
        # SD-Turbo reaches its useful quality range quickly. Two steps keeps
        # 768px editorial thumbnails fast on CPU; publish gets one refinement
        # step without doubling generation time.
        steps = 2 if quality_profile == "draft" else 3
        cfg = 1.0
    else:
        steps = {"draft": 18, "standard": 25, "publish": 30}[quality_profile]
        cfg = 6.5
    return width, height, steps, cfg


def build_creative_package(
    req: CreativeBriefInput,
    db: Session,
    *,
    user_negative: str = "",
) -> CreativePackageOut:
    brief = _llm_brief(req, db)
    source = "llm" if brief is not None else "heuristic"
    if brief is None:
        brief = _fallback_brief(req)

    model = str(settings_service.get_value(db, "default_model") or "sdxl")
    width, height, steps, cfg = canvas_profile(req.aspect_ratio, req.quality_profile, model)
    compiled = req.visual_prompt_override or prompt_composer.compile_prompt(brief, req.style_preset)
    negative = prompt_composer.compile_negative_prompt(brief, user_negative)
    return CreativePackageOut(
        brief=brief,
        compiled_prompt=compiled,
        negative_prompt=negative,
        source=source,
        style_preset=req.style_preset,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
    )
