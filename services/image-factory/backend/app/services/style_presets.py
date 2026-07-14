"""Versioned style definitions shared by briefing, prompting, and layout."""

from __future__ import annotations


STYLE_PRESETS: dict[str, dict] = {
    "editorial-tech": {
        "label": "Editorial công nghệ",
        "description": "Ảnh kiểu tạp chí, sạch, hiện đại và có khoảng thở cho tiêu đề.",
        "render_style": "premium editorial technology photography",
        "palette": ["cyan", "clean white", "charcoal", "natural skin tones"],
        "lighting": "soft directional daylight with controlled contrast",
        "mood": "modern, intelligent, trustworthy",
        "camera": "editorial medium-wide photograph, eye-level, realistic 35mm lens",
        "layout": "spacious editorial composition",
    },
    "human-story": {
        "label": "Câu chuyện con người",
        "description": "Con người và hành động thật là trung tâm, ánh sáng tự nhiên.",
        "render_style": "authentic documentary lifestyle photography",
        "palette": ["natural skin tones", "soft blue", "leaf green", "warm neutral"],
        "lighting": "natural window light with gentle highlights",
        "mood": "human, optimistic, candid",
        "camera": "candid medium shot, eye-level, realistic 50mm lens",
        "layout": "clear human focal point with environmental context",
    },
    "product-hero": {
        "label": "Sản phẩm nổi bật",
        "description": "Đồ vật rõ nét, chất liệu đẹp và bố cục quảng cáo có chủ đích.",
        "render_style": "high-end commercial product photography",
        "palette": ["brand accent color", "graphite", "clean white", "cool gray"],
        "lighting": "studio key light with precise rim highlights",
        "mood": "premium, precise, desirable",
        "camera": "commercial close-to-medium product shot, realistic 70mm lens",
        "layout": "single dominant product with controlled supporting props",
    },
    "bold-thumbnail": {
        "label": "Thumbnail nổi bật",
        "description": "Chủ thể lớn, tương phản cao và dễ đọc khi thu nhỏ.",
        "render_style": "polished high-impact commercial thumbnail photography",
        "palette": ["vivid yellow", "electric cyan", "deep black", "clean white"],
        "lighting": "bright punchy key light with strong subject separation",
        "mood": "energetic, immediate, confident",
        "camera": "close medium shot with a large unmistakable focal subject",
        "layout": "bold simple composition readable at thumbnail size",
    },
    "corporate-clean": {
        "label": "Doanh nghiệp tinh gọn",
        "description": "Chuyên nghiệp, đáng tin cậy và tiết chế hiệu ứng.",
        "render_style": "refined corporate editorial photography",
        "palette": ["navy accent", "white", "neutral gray", "natural skin tones"],
        "lighting": "balanced soft office daylight",
        "mood": "credible, calm, capable",
        "camera": "natural medium-wide corporate photograph, realistic lens",
        "layout": "ordered composition with restrained visual density",
    },
    "illustration-modern": {
        "label": "Minh họa hiện đại",
        "description": "Minh họa có hình khối, chiều sâu và câu chuyện rõ ràng.",
        "render_style": "premium modern editorial illustration with tactile geometric forms",
        "palette": ["coral accent", "teal", "off-white", "charcoal"],
        "lighting": "soft dimensional illustrated lighting",
        "mood": "inventive, clear, approachable",
        "camera": "isometric-to-eye-level illustrative scene with believable depth",
        "layout": "narrative illustration with one clear focal subject",
    },
}


def get_style(style_id: str) -> dict:
    return STYLE_PRESETS.get(style_id, STYLE_PRESETS["editorial-tech"])


def public_styles() -> list[dict]:
    return [
        {"id": style_id, "label": data["label"], "description": data["description"]}
        for style_id, data in STYLE_PRESETS.items()
    ]

