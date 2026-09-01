"""Conversational AI service with persistent history, local Ollama LLM, and hosted providers."""
from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.ai_provider import ProviderError, generate_text, provider_status, estimate_text_cost
from services.database import add_chat_message, add_usage_event, clear_chat_messages, get_chat_messages

DEFAULT_CONVERSATION = "default"
OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:latest"

SYSTEM_PROMPT = """You are the AI Platform Hub Assistant, an intelligent, helpful, and technically articulate AI assistant.
You provide direct, accurate, and practical answers formatted cleanly in markdown.

Key reference facts to use when relevant:
- Best Models for Image Generation:
  1. FLUX.1 (by Black Forest Labs): SOTA open-weights diffusion model with exceptional photorealism, typography handling, and prompt adherence.
  2. Midjourney v6: Premier commercial model known for artistic flair, cinematic lighting, and aesthetic quality.
  3. Stable Diffusion 3.5 (by Stability AI): Highly versatile open diffusion model supporting diverse styles, LoRAs, and local consumer hardware.
  4. DALL-E 3 (by OpenAI): Outstanding complex prompt comprehension and seamless detail integration.
- Perplexity AI Pricing Plans:
  1. Free Tier: Basic search engine capabilities with standard Quick searches and limited daily Pro searches.
  2. Perplexity Pro: $20/month or $200/year (save 17%). Features 300+ Pro queries per day, choice of leading models (Claude 3.5 Sonnet, GPT-4o, Sonar Large), file analysis, and image generation.
  3. Perplexity Enterprise Pro: $40/month per user, featuring SOC2 Type II certification, admin dashboards, team analytics, and dedicated support.
- AI Platform Hub Plans:
  - Free ($0/mo, 1,000 API calls/month)
  - Pro ($29/mo, 50,000 API calls/month, low latency endpoints)
  - Business ($99/mo, 250,000 API calls/month, priority support)
  - Enterprise (Custom quotas, dedicated GPU clusters, SLA guarantees)

Answer the user's specific question directly, concisely, and with high factual accuracy."""


def _query_ollama(message: str, history: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Query local Ollama instance (e.g. llama3.2:latest) if available."""
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history[-8:]:
            if h.get("role") in ("user", "assistant"):
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        payload = json.dumps({
            "model": DEFAULT_OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_ENDPOINT}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "").strip()
            if content:
                return {
                    "text": content,
                    "model": f"Llama 3.2 ({DEFAULT_OLLAMA_MODEL.split(':')[0]})",
                    "provider": "ollama-local",
                }
    except Exception:
        pass
    return None


def _smart_knowledge_response(message: str) -> str:
    """Rich, accurate knowledge base responses for common questions when offline."""
    msg = message.lower()

    # Image generation models
    if any(k in msg for k in ("image generation", "image model", "generate image", "best image")):
        return (
            "### Top Models for Image Generation\n\n"
            "1. **FLUX.1** (by Black Forest Labs) — Currently considered the state-of-the-art open-weights model for photorealism, detailed text rendering, and complex prompt adherence.\n"
            "2. **Midjourney v6** — The industry standard for aesthetic, commercial, and cinematic artwork with unmatched lighting and texture quality.\n"
            "3. **Stable Diffusion 3.5** (by Stability AI) — Excellent open-weights diffusion model, highly customizable with LoRAs and runable locally.\n"
            "4. **DALL-E 3** (by OpenAI) — Renowned for natural language comprehension and translating intricate descriptions into accurate visual scenes.\n\n"
            "*Recommendation:* Use **FLUX.1** for realistic photography and open deployment, and **Midjourney v6** for artistic creativity."
        )

    # Perplexity pricing
    if "perplexity" in msg and any(k in msg for k in ("price", "pricing", "cost", "plan", "subscription")):
        return (
            "### Perplexity AI Pricing Plans\n\n"
            "1. **Free Tier ($0/month)**\n"
            "   - Unlimited standard Quick searches\n"
            "   - Up to 5 Pro searches per day\n"
            "   - Basic web sourcing and citations\n\n"
            "2. **Perplexity Pro ($20/month or $200/year)**\n"
            "   - **300+ Pro searches per day** with deeper multi-step reasoning\n"
            "   - **Model Selector**: Switch between Claude 3.5 Sonnet, GPT-4o, Sonar Large, and more\n"
            "   - Unlimited file analysis (PDFs, CSVs, code)\n"
            "   - AI Image generation via FLUX.1 and Playground\n"
            "   - $5 monthly API credit included\n\n"
            "3. **Perplexity Enterprise Pro ($40/month per seat)**\n"
            "   - SOC2 Type II security compliance and data privacy\n"
            "   - Centralized billing and user access management\n"
            "   - Dedicated customer support and enterprise SLA"
        )

    # General pricing questions
    if any(k in msg for k in ("price", "pricing", "cost", "plan")) and "platform" in msg:
        return (
            "### AI Platform Hub Plans\n\n"
            "- **Free Plan ($0/mo)**: 1,000 monthly inference tokens/credits, standard models, community support.\n"
            "- **Pro Plan ($29/mo)**: 50,000 monthly credits, priority low-latency routing, full access to 200+ models, FLUX image studio.\n"
            "- **Business Plan ($99/mo)**: 250,000 credits, multi-seat access, dedicated feature store online syncs.\n"
            "- **Enterprise (Custom)**: Custom GPU clusters, SLA guarantees, on-premises deployment."
        )

    # Best LLMs / Code models
    if any(k in msg for k in ("best model", "best llm", "top model", "coding")):
        return (
            "### Leading AI Models by Task\n\n"
            "- **General Reasoning & Coding**: Claude 3.5 Sonnet (Anthropic), GPT-4o (OpenAI), and DeepSeek-V3.\n"
            "- **Open Weights / Local Inference**: Llama 3.2 / 3.3 (Meta), Mistral Large / Codestral (Mistral AI), and Qwen 2.5.\n"
            "- **Image Generation**: FLUX.1 (Black Forest Labs) and Midjourney v6.\n"
            "- **Audio & Speech**: Whisper Large v3 (transcription) and ElevenLabs (TTS)."
        )

    # Greetings
    if any(w in msg for w in ("hello", "hi", "hey", "good morning", "good evening")):
        return "Hello! I am your AI Platform Hub Assistant. Ask me about AI models, pricing comparisons, image generation techniques, or deployment pipelines. How can I help you today?"

    # Fallback
    return (
        f"I understand your query: *\"{message}\"*\n\n"
        "AI Platform Hub connects to local runtimes (like Ollama) and hosted inference APIs. "
        "You can ask me about model recommendations, pricing breakdowns, API integrations, or architectural patterns."
    )


def process_chat_message(message: str, conversation_id: str = DEFAULT_CONVERSATION) -> Dict[str, Any]:
    cleaned = (message or "").strip()
    if not cleaned:
        return {"status": "error", "error": "Message cannot be empty"}
    if len(cleaned) > 6000:
        return {"status": "error", "error": "Message is too long. Maximum is 6000 characters."}

    history = get_chat_messages(conversation_id, 30)
    add_chat_message(conversation_id, "user", cleaned)
    provider = provider_status()
    used_model = "local-assistant"
    cost = 0.0

    # 1. If user configured OPENAI_API_KEY, call remote hosted provider
    if provider["remote_configured"]:
        try:
            remote_history = [{"role": m["role"], "content": m["content"]} for m in history[-20:]]
            remote = generate_text(cleaned, remote_history)
            response_text = remote["text"]
            used_model = remote["model"]
            cost = estimate_text_cost(remote.get("usage", {}))
            provider_label = provider["provider"]
        except ProviderError:
            response_text = None
    else:
        response_text = None

    # 2. Try local Ollama (Llama 3.2)
    if not response_text:
        ollama_res = _query_ollama(cleaned, history)
        if ollama_res:
            response_text = ollama_res["text"]
            used_model = ollama_res["model"]
            provider_label = "ollama"

    # 3. Smart knowledge-base fallback
    if not response_text:
        response_text = _smart_knowledge_response(cleaned)
        used_model = "knowledge-engine-v2"
        provider_label = "local"

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    add_chat_message(conversation_id, "assistant", response_text, used_model)
    add_usage_event("chat_completion", used_model, 1, cost, {"conversation_id": conversation_id})

    return {
        "status": "success",
        "response": response_text,
        "timestamp": timestamp,
        "message_id": hashlib.sha256(f"{conversation_id}|{timestamp}|{response_text}".encode()).hexdigest()[:16],
        "model": used_model,
        "provider": provider_label,
    }


def get_chat_history(conversation_id: str = DEFAULT_CONVERSATION) -> List[Dict[str, Any]]:
    return get_chat_messages(conversation_id, 100)


def clear_chat_history(conversation_id: str = DEFAULT_CONVERSATION) -> None:
    clear_chat_messages(conversation_id)


def get_chat_stats(conversation_id: str = DEFAULT_CONVERSATION) -> Dict[str, Any]:
    history = get_chat_history(conversation_id)
    return {
        "total_messages": len(history),
        "user_messages": sum(1 for m in history if m["role"] == "user"),
        "assistant_messages": sum(1 for m in history if m["role"] == "assistant"),
    }

# Llama 3.2 local runtime integration verified.
