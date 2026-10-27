"""Prompt analysis, multi-strategy optimization and reproducible evaluation."""
from __future__ import annotations
import re
import time
import math
from dataclasses import dataclass
from typing import Any

STRATEGIES = ("structured", "few_shot", "role_based", "decomposition", "constraints", "self_refine")
STOP = {"the", "and", "for", "with", "this", "that", "from", "into", "your", "have", "about", "will", "what", "when", "where", "which"}

def keywords(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]+", text.lower()) if len(x) > 3 and x not in STOP}

def analyze(prompt: str) -> dict[str, Any]:
    words = prompt.split()
    missing = []
    if len(words) < 12: missing.append("Provide more context and task details")
    if not re.search(r"\b(table|json|list|paragraph|code|steps|format|markdown)\b", prompt, re.I): missing.append("Specify the desired output format")
    if not re.search(r"\b(for|audience|student|beginner|expert|customer|developer)\b", prompt, re.I): missing.append("Specify the target audience")
    if not re.search(r"\b(must|avoid|limit|only|at least|no more than|maximum)\b", prompt, re.I): missing.append("Add constraints and acceptance criteria")
    clarity = max(0, min(100, 100 - len(missing) * 17 - (12 if len(words) < 5 else 0)))
    return {"clarity": clarity, "word_count": len(words), "missing": missing, "task_type": classify(prompt), "suggestions": missing or ["Prompt has clear initial instructions; validate it on a test set."]}

def classify(prompt: str) -> str:
    p = prompt.lower()
    if any(w in p for w in ("python", "code", "javascript", "function", "algorithm", "sql")): return "coding"
    if any(w in p for w in ("summarize", "summary", "brief")): return "summarization"
    if any(w in p for w in ("compare", "difference", "versus")): return "comparison"
    if any(w in p for w in ("story", "poem", "creative")): return "creative"
    return "general"

def optimize(prompt: str, strategy: str, audience: str = "a university student") -> str:
    if strategy not in STRATEGIES: raise ValueError(f"Unknown strategy: {strategy}")
    head = f"Task: {prompt.strip()}\nTarget audience: {audience.strip() or 'general audience'}.\n"
    patterns = {
        "structured": "Provide: (1) concise answer, (2) key reasoning or steps, (3) concrete example, (4) final checklist. Use clear headings.",
        "few_shot": "Follow this demonstration of a high-quality response style:\nInput: Explain caching.\nOutput: Definition: Caching stores frequently used data for faster access. Example: a browser caches images. Tradeoff: stale content.\nNow answer the task in the same clear, example-driven style.",
        "role_based": "Act as an experienced university professor and technical reviewer. Be precise, accessible, and transparent about uncertainty. Explain key concepts with an example.",
        "decomposition": "Break the task into manageable subproblems, solve each, then synthesize a final response. Provide concise justifications, not private reasoning traces.",
        "constraints": "Requirements: Be accurate; do not invent citations or results; flag missing information; use concrete examples; keep the response well organized and actionable.",
        "self_refine": "Draft a response, check it for correctness, completeness, clarity and unsupported claims, then output only the improved final response with a short verification checklist."
    }
    return head + patterns[strategy]

def evaluate(response: str, prompt: str, expected: str = "") -> dict[str, Any]:
    """Transparent heuristics, not a substitute for human evaluation or ground truth."""
    answer = keywords(response)
    request = keywords(prompt)
    overlap = len(answer & request) / max(1, len(request))
    relevance = round(100 * overlap, 1)
    completeness = round(min(100, 15 + len(response.split()) * 0.7), 1)
    structure = 100.0 if re.search(r"(^|\n)([-*#]|\d+[.)])", response) else 55.0
    result = {"relevance_proxy": relevance, "length_proxy": completeness, "structure_proxy": structure}
    if expected.strip():
        target = keywords(expected)
        result["reference_keyword_recall"] = round(100 * len(answer & target) / max(1, len(target)), 1)
    result["heuristic_score"] = round(sum(result.values()) / len(result), 1)
    return result

async def generate(prompt: str, provider: str, model: str, base_url: str, api_key: str) -> dict[str, Any]:
    start = time.perf_counter()
    if provider == "mock":
        task = prompt.split("Task:", 1)[-1].split("\n", 1)[0].strip()
        answer = f"## Overview\n{task}\n\n## Explanation\nThis is a deterministic demo response. Connect Ollama or an OpenAI-compatible API for genuine model generation.\n\n## Example\nUse a concrete example relevant to the task.\n\n## Checklist\n- Verify facts\n- Test outputs\n- Review limitations"
        tokens = len(answer.split())
    elif provider in {"ollama", "openai_compatible"}:
        import httpx
        url = base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key: headers["Authorization"] = "Bearer " + api_key
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(url, headers=headers, json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2})
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("LLM provider returned empty choices")
        answer = choices[0].get("message", {}).get("content") or ""
        tokens = data.get("usage", {}).get("total_tokens", len(answer.split()))
    else: raise ValueError("Unsupported provider")
    return {"text": answer, "latency_ms": round((time.perf_counter() - start) * 1000, 1), "tokens": tokens, "model": model, "provider": provider}

