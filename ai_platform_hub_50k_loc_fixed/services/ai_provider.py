"""Provider abstraction for production AI calls.

No API secret is ever sent to the browser.  When OPENAI_API_KEY is configured,
this module uses OpenAI's HTTPS API directly.  When it is not configured, chat
uses the local assistant and image generation uses a clearly labelled local
renderer rather than pretending that a remote model ran.
"""
from __future__ import annotations

import base64
import json
import os
import random
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


def _load_local_env() -> None:
    """Load a simple project .env file without adding a dotenv dependency."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("\'")
        os.environ.setdefault(key, value)


_load_local_env()


class ProviderError(RuntimeError):
    """Raised when a remote AI provider cannot complete a request."""


@dataclass
class ProviderConfig:
    api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    text_model: str = os.getenv("OPENAI_TEXT_MODEL", "gpt-5.6-luna")
    image_model: str = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    timeout: int = int(os.getenv("AI_PROVIDER_TIMEOUT", "90"))
    use_remote: bool = os.getenv("AI_USE_REMOTE", "true").lower() in {"1", "true", "yes", "on"}

    @property
    def configured(self) -> bool:
        return bool(self.api_key) and self.use_remote


CONFIG = ProviderConfig()


def provider_status() -> Dict[str, Any]:
    return {
        "provider": "openai" if CONFIG.configured else "local",
        "remote_configured": CONFIG.configured,
        "text_model": CONFIG.text_model,
        "image_model": CONFIG.image_model,
        "message": (
            "Remote AI provider is configured."
            if CONFIG.configured
            else "Running in local mode. Set OPENAI_API_KEY to enable real hosted AI generation."
        ),
    }


def _post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not CONFIG.api_key:
        raise ProviderError("OPENAI_API_KEY is not configured")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{CONFIG.base_url}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {CONFIG.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AI-Platform-Hub/2.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=CONFIG.timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            message = parsed.get("error", {}).get("message", detail)
        except json.JSONDecodeError:
            message = detail or str(exc)
        raise ProviderError(f"AI provider error ({exc.code}): {message}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(f"AI provider connection failed: {exc}") from exc


def generate_text(prompt: str, history: Optional[list[dict[str, str]]] = None) -> Dict[str, Any]:
    """Generate a chat response using the configured provider."""
    if not CONFIG.configured:
        raise ProviderError("Remote text generation is not configured")

    messages = []
    for item in history or []:
        if item.get("role") in {"user", "assistant", "system"}:
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": CONFIG.text_model,
        "input": messages,
        "instructions": (
            "You are the production assistant for AI Platform Hub. "
            "Be accurate, concise, transparent about uncertainty, and never claim "
            "a feature exists unless the platform exposes it."
        ),
        "max_output_tokens": 1200,
    }
    data = _post_json("/responses", payload)
    text = data.get("output_text", "").strip()
    if not text:
        # Be tolerant of response shapes from compatible providers.
        chunks = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    chunks.append(content["text"])
        text = "\n".join(chunks).strip()
    if not text:
        raise ProviderError("The provider returned no text content")
    return {"text": text, "model": CONFIG.text_model, "usage": data.get("usage", {})}


def generate_image(prompt: str, output_dir: Path, style_name: str, size: str = "1024x1024") -> Dict[str, Any]:
    """Generate and persist an image using the hosted image model."""
    if not CONFIG.configured:
        raise ProviderError("Remote image generation is not configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": CONFIG.image_model,
        "prompt": prompt,
        "size": size,
        "n": 1,
    }
    data = _post_json("/images/generations", payload)
    item = (data.get("data") or [{}])[0]
    raw_b64 = item.get("b64_json")
    remote_url = item.get("url")
    if not raw_b64 and not remote_url:
        raise ProviderError("The provider returned no image data")

    generation_id = f"img_{random.randint(10000000, 99999999)}"
    filename = f"{generation_id}.png"
    target = output_dir / filename
    if raw_b64:
        target.write_bytes(base64.b64decode(raw_b64))
    else:
        try:
            with urllib.request.urlopen(remote_url, timeout=CONFIG.timeout) as response:
                target.write_bytes(response.read())
        except Exception as exc:
            raise ProviderError(f"Could not save generated image: {exc}") from exc

    return {
        "generation_id": generation_id,
        "filename": filename,
        "image_url": f"/static/generated/{filename}",
        "provider": "openai",
        "model": CONFIG.image_model,
        "size": size,
        "usage": data.get("usage", {}),
    }


def estimate_text_cost(usage: Dict[str, Any]) -> float:
    """Conservative estimate using configured model pricing assumptions.

    This is an application estimate, not an invoice.  Providers may change
    pricing; the dashboard labels it accordingly.
    """
    inp = float(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
    out = float(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
    # Approximate Luna-class rates from the current platform configuration.
    return round((inp / 1_000_000) * 0.20 + (out / 1_000_000) * 1.20, 8)
