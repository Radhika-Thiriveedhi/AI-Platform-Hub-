"""Dependency-light text analytics suitable for local production deployments.

The original implementation returned random confidence values and random topics.
This version is deterministic, stores every run, and clearly labels its local
NLP engine. Optional LLM enrichment can be added without changing the UI.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from services.database import add_analysis_run, add_usage_event

ANALYSIS_TYPES = [
    {"id":"sentiment","name":"Sentiment Analysis","description":"Detect the overall emotional tone of the text (positive, negative, neutral).","icon":"😊"},
    {"id":"entities","name":"Named Entity Recognition","description":"Extract people, organizations, locations, and other entities from text.","icon":"🏷️"},
    {"id":"keywords","name":"Keyword Extraction","description":"Identify the most important keywords and key phrases.","icon":"🔑"},
    {"id":"summary","name":"Text Summarization","description":"Generate a concise extractive summary of longer text.","icon":"📝"},
    {"id":"language","name":"Language Detection","description":"Detect likely language from character and word patterns.","icon":"🌐"},
    {"id":"readability","name":"Readability Score","description":"Calculate readability metrics and suggested audience level.","icon":"📊"},
    {"id":"toxicity","name":"Toxicity Detection","description":"Flag potentially toxic or harmful language using transparent local signals.","icon":"🛡️"},
    {"id":"topics","name":"Topic Modeling","description":"Identify likely topics from weighted vocabulary signals.","icon":"📚"},
]

STOPWORDS = set("a an the and or but if then than is are was were be been being to of in for on with at by from as into through during before after above below this that these those it its i me my we our you your he she they them his her their have has had do does did will would could should may might must can cannot not no nor so yet very just about over under again further once here there when where why how all any both each few more most other some such only own same too s t re ve ll d m o".split())
POSITIVE = {"good","great","excellent","amazing","love","happy","wonderful","fantastic","best","awesome","positive","beautiful","perfect","enjoy","success","successful","helpful","fast","easy","reliable","secure","innovative","improve","improved","benefit"}
NEGATIVE = {"bad","terrible","awful","hate","poor","worst","horrible","negative","sad","angry","disappointed","ugly","fail","failed","problem","slow","broken","error","risk","unsafe","difficult","expensive"}
TOXIC = {"idiot","stupid","moron","hate","kill","die","violence","attack","threat","abuse"}
TOPIC_TERMS = {
    "Artificial Intelligence":{"ai","model","machine","learning","neural","llm","prompt","inference"},
    "Software Development":{"code","python","javascript","api","backend","frontend","database","deploy","software"},
    "Business":{"business","customer","sales","revenue","market","company","product","strategy"},
    "Data Analytics":{"data","analytics","dashboard","metric","report","insight","analysis","dataset"},
    "Education":{"student","course","learn","teacher","college","university","exam","education"},
    "Technology":{"technology","cloud","server","computer","internet","digital","platform","system"},
    "Finance":{"finance","money","price","cost","investment","bank","budget","revenue","profit"},
    "Health":{"health","doctor","patient","medical","hospital","disease","medicine","fitness"},
}


def get_analysis_types() -> List[Dict[str, Any]]:
    return [dict(x) for x in ANALYSIS_TYPES]


def _words(text: str) -> List[str]:
    return re.findall(r"\b[a-zA-Z][a-zA-Z'-]{2,}\b", text.lower())


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def _sentiment(text: str) -> Dict[str, Any]:
    words = _words(text)
    pos = sum(1 for w in words if w in POSITIVE)
    neg = sum(1 for w in words if w in NEGATIVE)
    total = max(len(words), 1)
    raw = (pos - neg) / total
    score = round(min(0.99, max(0.01, 0.5 + abs(raw) * 2.5)), 3)
    label = "positive" if pos > neg else "negative" if neg > pos else "neutral"
    return {"label": label, "score": score, "positive_signals": pos, "negative_signals": neg, "confidence_note": "Deterministic lexicon-based estimate; not a clinical or legal classifier."}


def _entities(text: str) -> List[Dict[str, Any]]:
    patterns = [
        ("EMAIL", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        ("URL", r"https?://[^\s]+"),
        ("MONEY", r"(?:\$|₹|€|£)\s?\d+(?:[,.]\d+)*"),
        ("DATE", r"\b(?:\d{1,2}[/-])?\d{1,2}[/-]\d{2,4}\b"),
        ("PERSON_OR_ORG", r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b"),
    ]
    found, seen = [], set()
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(0).strip(".,")
            key = (kind, value.lower())
            if key in seen: continue
            seen.add(key)
            found.append({"text": value, "type": kind, "start": match.start(), "end": match.end()})
            if len(found) >= 30: return found
    return found


def _keywords(text: str) -> List[Dict[str, Any]]:
    words = [w for w in _words(text) if w not in STOPWORDS]
    freq = Counter(words)
    total = max(len(words), 1)
    return [{"keyword": word, "count": count, "score": round(count / total, 4)} for word, count in freq.most_common(15)]


def _summary(text: str) -> str:
    sentences = _sentences(text)
    if len(sentences) <= 2: return text.strip()
    freq = Counter(w for w in _words(text) if w not in STOPWORDS)
    scored = []
    for idx, sentence in enumerate(sentences):
        words = _words(sentence)
        score = sum(freq[w] for w in words) / max(len(words), 1)
        scored.append((score, idx, sentence))
    take = max(1, min(3, len(sentences) // 3))
    chosen = sorted(scored, reverse=True)[:take]
    return " ".join(sentence for _, _, sentence in sorted(chosen, key=lambda x: x[1]))


def _language(text: str) -> Dict[str, Any]:
    # Strong ASCII English signal, plus common Unicode ranges for major scripts.
    if re.search(r"[\u0900-\u097F]", text):
        return {"primary":"hi","primary_name":"Hindi","confidence":0.94}
    if re.search(r"[\u4E00-\u9FFF]", text):
        return {"primary":"zh","primary_name":"Chinese","confidence":0.94}
    if re.search(r"[\u3040-\u30FF]", text):
        return {"primary":"ja","primary_name":"Japanese","confidence":0.94}
    if re.search(r"[\uAC00-\uD7AF]", text):
        return {"primary":"ko","primary_name":"Korean","confidence":0.94}
    return {"primary":"en","primary_name":"English","confidence":0.90}


def _syllables(word: str) -> int:
    groups = re.findall(r"[aeiouy]+", word.lower())
    count = len(groups)
    if word.lower().endswith("e") and count > 1: count -= 1
    return max(1, count)


def _readability(text: str) -> Dict[str, Any]:
    words = _words(text)
    sentences = _sentences(text)
    syllables = sum(_syllables(w) for w in words)
    wc, sc = max(1, len(words)), max(1, len(sentences))
    score = 206.835 - 1.015 * (wc / sc) - 84.6 * (syllables / wc)
    score = round(max(0, min(100, score)), 1)
    if score >= 90: level = "Very Easy"
    elif score >= 80: level = "Easy"
    elif score >= 70: level = "Fairly Easy"
    elif score >= 60: level = "Standard"
    elif score >= 50: level = "Fairly Difficult"
    elif score >= 30: level = "Difficult"
    else: level = "Very Difficult"
    return {"flesch_score": score, "level": level, "word_count": wc, "sentence_count": sc, "avg_words_per_sentence": round(wc/sc,1), "syllables": syllables}


def _toxicity(text: str) -> Dict[str, Any]:
    words = _words(text)
    hits = sorted({w for w in words if w in TOXIC})
    score = round(min(1.0, len(hits) / max(3, len(words) * 0.08)), 3)
    return {"is_toxic": score >= 0.5, "score": score, "matched_terms": hits, "categories": {"toxicity": score, "insult": round(min(1, score * 0.8),3), "threat": round(min(1, score * 0.6),3)}}


def _topics(text: str) -> List[Dict[str, Any]]:
    words = set(_words(text))
    scored = []
    for topic, terms in TOPIC_TERMS.items():
        hits = sorted(words & terms)
        if hits: scored.append({"topic": topic, "relevance": round(min(1, len(hits)/4), 3), "matched_terms": hits})
    return sorted(scored, key=lambda x: x["relevance"], reverse=True)[:5]


def analyze_text(text: str, analysis_type: str = "sentiment") -> Dict[str, Any]:
    cleaned = (text or "").strip()
    if not cleaned: return {"status":"error","error":"Text is required"}
    if len(cleaned) > 20000: return {"status":"error","error":"Text exceeds the 20,000 character limit."}
    if analysis_type not in {x["id"] for x in ANALYSIS_TYPES}: return {"status":"error","error":f"Unknown analysis type: {analysis_type}"}

    operations = {
        "sentiment": lambda: _sentiment(cleaned),
        "entities": lambda: {"entities": _entities(cleaned)},
        "keywords": lambda: {"keywords": _keywords(cleaned)},
        "summary": lambda: {"summary": _summary(cleaned)},
        "language": lambda: _language(cleaned),
        "readability": lambda: _readability(cleaned),
        "toxicity": lambda: _toxicity(cleaned),
        "topics": lambda: {"topics": _topics(cleaned)},
    }
    result_data = operations[analysis_type]()
    analysis_id = hashlib.sha256(f"{analysis_type}|{cleaned}".encode()).hexdigest()[:16]
    result = {
        "status":"success", "analysis_id":analysis_id, "type":analysis_type,
        "input_length":len(cleaned), "word_count":len(_words(cleaned)),
        "result":result_data, "processed_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "engine":"local-deterministic-nlp-v2",
    }
    add_analysis_run(analysis_type, len(cleaned), result)
    add_usage_event("text_analysis", "local-deterministic-nlp-v2", 1, 0, {"type": analysis_type})
    return result
