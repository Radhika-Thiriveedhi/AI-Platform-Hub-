"""Deterministic local image renderer used when no hosted image API is configured.

It creates a genuine SVG file, not a fake placeholder.  It is intentionally
labelled as a local renderer in the UI; users can switch to a hosted AI image
provider by setting OPENAI_API_KEY.
"""
from __future__ import annotations

import hashlib
import html
import math
import random
from pathlib import Path
from typing import Dict


def render(prompt: str, style: str, output_dir: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    seed = int(hashlib.sha256(f"{prompt}|{style}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    ident = hashlib.sha256(f"{prompt}|{style}|{seed}".encode()).hexdigest()[:16]
    filename = f"local_{ident}.svg"
    safe_prompt = html.escape(prompt[:140])

    palette = {
        "realistic": ("#0f172a", "#38bdf8", "#f8fafc"),
        "anime": ("#3b0764", "#f472b6", "#fef3c7"),
        "digital-art": ("#111827", "#a855f7", "#67e8f9"),
        "oil-painting": ("#422006", "#f59e0b", "#fef3c7"),
        "watercolor": ("#164e63", "#67e8f9", "#ecfeff"),
        "cyberpunk": ("#09090b", "#22d3ee", "#f43f5e"),
        "fantasy": ("#1e1b4b", "#8b5cf6", "#f5d0fe"),
        "minimalist": ("#f8fafc", "#334155", "#0f172a"),
        "3d-render": ("#172554", "#60a5fa", "#e0f2fe"),
        "pixel-art": ("#052e16", "#84cc16", "#fef08a"),
        "comic": ("#450a0a", "#ef4444", "#fef2f2"),
        "sketch": ("#f1f5f9", "#475569", "#0f172a"),
    }
    bg, accent, foreground = palette.get(style, palette["digital-art"])
    circles = []
    for _ in range(18):
        x = rng.randint(40, 984)
        y = rng.randint(40, 760)
        r = rng.randint(10, 75)
        opacity = round(rng.uniform(0.08, 0.42), 2)
        circles.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{accent}" opacity="{opacity}"/>')
    skyline = []
    for i in range(16):
        x = i * 64
        h = rng.randint(80, 300)
        y = 780 - h
        w = rng.randint(36, 58)
        skyline.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{foreground}" opacity="0.55"/>')
        for wy in range(y + 18, 760, 26):
            if rng.random() > 0.3:
                skyline.append(f'<rect x="{x+9}" y="{wy}" width="8" height="5" fill="{accent}" opacity="0.85"/>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{bg}"/><stop offset="1" stop-color="{accent}" stop-opacity="0.55"/></linearGradient></defs>
<rect width="1024" height="1024" fill="url(#g)"/>{''.join(circles)}
<path d="M0 820 Q180 690 360 790 T720 760 T1024 720 V1024 H0Z" fill="{bg}" opacity="0.82"/>{''.join(skyline)}
<rect x="48" y="52" width="928" height="110" rx="20" fill="{bg}" opacity="0.72"/>
<text x="80" y="102" fill="{foreground}" font-family="Arial, sans-serif" font-size="24" font-weight="700">AI Platform Hub · Local Renderer</text>
<text x="80" y="137" fill="{foreground}" opacity="0.85" font-family="Arial, sans-serif" font-size="17">{safe_prompt}</text>
<text x="80" y="952" fill="{foreground}" opacity="0.75" font-family="Arial, sans-serif" font-size="16">Style: {html.escape(style)} · Deterministic local artwork</text>
</svg>'''
    (output_dir / filename).write_text(svg, encoding="utf-8")
    return {"generation_id": ident, "filename": filename, "image_url": f"/static/generated/{filename}"}
