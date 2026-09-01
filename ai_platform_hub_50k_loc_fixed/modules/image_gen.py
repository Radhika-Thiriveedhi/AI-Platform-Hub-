"""Production-oriented image generation service for AI Platform Hub."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.ai_image_service import generate_flux_image
from services.ai_provider import ProviderError, generate_image as remote_generate_image, provider_status
from services.database import add_generation, add_usage_event, get_recent_generations as db_recent
from services.local_image_renderer import render as render_local

BASE_DIR = Path(__file__).resolve().parents[1]
GENERATED_DIR = BASE_DIR / "static" / "generated"

IMAGE_STYLES = [
    {"id":"realistic","name":"Photorealistic","description":"Natural lighting, realistic materials and photographic detail.","preview_color":"#4A90D9"},
    {"id":"anime","name":"Anime / Manga","description":"Expressive characters, clean linework and vivid animation aesthetics.","preview_color":"#E91E63"},
    {"id":"digital-art","name":"Digital Art","description":"Modern digital illustration with bold composition and polished detail.","preview_color":"#9C27B0"},
    {"id":"oil-painting","name":"Oil Painting","description":"Rich pigments, brush texture and traditional fine-art composition.","preview_color":"#FF9800"},
    {"id":"watercolor","name":"Watercolor","description":"Soft washes, paper texture and translucent color transitions.","preview_color":"#00BCD4"},
    {"id":"cyberpunk","name":"Cyberpunk","description":"Neon lighting, futuristic architecture and cinematic contrast.","preview_color":"#FF1744"},
    {"id":"fantasy","name":"Fantasy Art","description":"Epic environments, magical atmosphere and dramatic lighting.","preview_color":"#7C4DFF"},
    {"id":"minimalist","name":"Minimalist","description":"Simple geometry, restrained composition and generous negative space.","preview_color":"#607D8B"},
    {"id":"3d-render","name":"3D Render","description":"Physically inspired materials, depth and studio-quality rendering.","preview_color":"#009688"},
    {"id":"pixel-art","name":"Pixel Art","description":"Crisp low-resolution forms inspired by classic games.","preview_color":"#8BC34A"},
    {"id":"comic","name":"Comic Book","description":"Bold outlines, graphic shading and dynamic panel-art aesthetics.","preview_color":"#F44336"},
    {"id":"sketch","name":"Pencil Sketch","description":"Hand-drawn graphite lines, shading and paper texture.","preview_color":"#795548"},
]


def get_image_styles() -> List[Dict[str, Any]]:
    return [dict(item) for item in IMAGE_STYLES]


def get_style_by_id(style_id: str) -> Optional[Dict[str, Any]]:
    return next((dict(s) for s in IMAGE_STYLES if s["id"] == style_id), None)


def enhance_prompt(prompt: str, style_obj: Dict[str, Any]) -> str:
    style = style_obj["name"]
    return f"{prompt.strip()}, {style.lower()} style, strong composition, coherent lighting, highly detailed, professional quality"


def validate_prompt(prompt: str) -> Dict[str, Any]:
    cleaned = (prompt or "").strip()
    if len(cleaned) < 3:
        return {"valid": False, "message": "Prompt must contain at least 3 characters."}
    if len(cleaned) > 1500:
        return {"valid": False, "message": "Prompt is too long. Keep it under 1500 characters."}
    words = cleaned.split()
    suggestions = []
    if len(words) < 6:
        suggestions.append("Add subject, setting, lighting and mood for more control.")
    if "negative" not in cleaned.lower():
        suggestions.append("If supported by your provider, consider negative constraints for unwanted details.")
    return {"valid": True, "word_count": len(words), "char_count": len(cleaned), "feedback": suggestions or ["Prompt is ready to generate."]}


def generate_image(prompt: str, style: str = "realistic", size: str = "1024x1024") -> Dict[str, Any]:
    cleaned = (prompt or "").strip()
    validation = validate_prompt(cleaned)
    if not validation["valid"]:
        return {"status": "error", "error": validation["message"]}
    style_obj = get_style_by_id(style) or IMAGE_STYLES[0]
    enhanced = enhance_prompt(cleaned, style_obj)
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    seed = int(hashlib.sha256(f"{cleaned}|{style}|{size}".encode()).hexdigest()[:8], 16)
    provider = provider_status()

    base = {
        "prompt": cleaned,
        "enhanced_prompt": enhanced,
        "style": style_obj["id"],
        "style_name": style_obj["name"],
        "seed": seed,
        "width": int(size.split("x")[0]),
        "height": int(size.split("x")[1]),
        "created_at": created_at,
    }

    try:
        if provider["remote_configured"]:
            remote = remote_generate_image(enhanced, GENERATED_DIR, style_obj["name"], size=size)
            result = {
                **base,
                "status": "success",
                "generation_id": remote["generation_id"],
                "image_url": remote["image_url"],
                "provider": "openai",
                "model": remote.get("model"),
                "estimated_cost": 0.0,
                "message": f"Image generated successfully using {remote.get('model', 'hosted image model')}.",
            }
        else:
            flux_res = generate_flux_image(cleaned, style_obj["id"], base["width"], base["height"], seed, GENERATED_DIR)
            result = {
                **base,
                "status": "success",
                "generation_id": flux_res["generation_id"],
                "image_url": flux_res["image_url"],
                "provider": flux_res.get("provider", "FLUX.1 AI"),
                "model": flux_res.get("model", "FLUX.1"),
                "estimated_cost": 0.0,
                "message": f"Generated successfully using {flux_res.get('model', 'FLUX.1')} generative AI model.",
            }
    except ProviderError as exc:
        return {**base, "status": "error", "error": str(exc), "provider": "openai"}

    add_generation(result)
    add_usage_event("image_generation", result.get("model", "local-renderer"), 1, result.get("estimated_cost", 0), {"style": style_obj["id"]})
    return result


def get_recent_generations(limit: int = 10) -> List[Dict[str, Any]]:
    return db_recent(limit)


def get_prompt_suggestions() -> List[str]:
    return [
        "A serene mountain landscape at sunrise with misty valleys",
        "Futuristic smart city skyline with autonomous transit and vertical gardens",
        "A cozy coffee shop interior with warm lighting and indoor plants",
        "A product hero shot of a premium AI workstation on a glass desk",
        "An underwater research station surrounded by colorful coral reefs",
        "A cinematic space station orbiting a blue planet at night",
    ]


# Backward-compatible name used by older integrations.
def generate_mock_image_prompt(prompt: str, style: str = "realistic") -> Dict[str, Any]:
    return generate_image(prompt, style)
