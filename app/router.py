"""Hybrid LLM routing: explicit policies, cost-aware local preference, cloud fallback."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Literal
from .core import classify

Route = Literal['auto', 'local', 'cloud', 'mock']

@dataclass(frozen=True)
class Target:
    provider: str
    model: str
    base_url: str
    api_key: str

def _detect_local_model(base_url: str = 'http://localhost:11434/v1') -> str | None:
    try:
        import httpx
        url = base_url.replace('/v1', '').rstrip('/') + '/api/tags'
        with httpx.Client(timeout=0.8) as client:
            res = client.get(url)
            if res.status_code == 200:
                models = res.json().get('models', [])
                if models:
                    return models[0].get('name')
    except Exception:
        pass
    return None

def targets() -> dict[str, Target]:
    ollama_base = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
    ollama_model = os.getenv('OLLAMA_MODEL')
    if not ollama_model:
        ollama_model = _detect_local_model(ollama_base) or 'llama3.2'
    return {
        'local': Target('ollama', ollama_model, ollama_base, ''),
        'cloud': Target('openai_compatible', os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'), os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'), os.getenv('OPENAI_API_KEY', '')),
        'mock': Target('mock', 'demo', '', ''),
    }

def choose_route(prompt: str, route: Route = 'auto', prefer_local: bool = True) -> tuple[list[str], str]:
    """Return ordered attempts and an auditable selection reason.

    No silent mock fallback: demonstration output must be explicitly requested.
    """
    if route not in {'auto', 'local', 'cloud', 'mock'}:
        raise ValueError('route must be auto, local, cloud or mock')
    if route != 'auto':
        return [route], f'User selected {route} route'
    task = classify(prompt)
    long_task = len(prompt.split()) >= int(os.getenv('CLOUD_COMPLEXITY_WORDS', '180'))
    cloud_first = (task == 'coding' and len(prompt.split()) > 60) or long_task
    if prefer_local and not cloud_first:
        return ['local', 'cloud'], 'Local-first for cost control; cloud fallback on local failure'
    return ['cloud', 'local'], 'Cloud-first for longer or complex tasks; local fallback on cloud failure'

async def hybrid_generate(prompt: str, route: Route = 'auto', prefer_local: bool = True) -> dict:
    from .core import generate
    order, reason = choose_route(prompt, route, prefer_local)
    configured = targets()
    errors = []
    for name in order:
        target = configured[name]
        if name == 'cloud' and not target.api_key:
            errors.append({'route': name, 'error': 'OPENAI_API_KEY is not configured'})
            continue
        try:
            result = await generate(prompt, target.provider, target.model, target.base_url, target.api_key)
            return {**result, 'route': name, 'routing_reason': reason, 'attempts': [*errors, {'route': name, 'status': 'success'}]}
        except Exception as exc:
            # Never expose provider error bodies: they may contain sensitive data.
            errors.append({'route': name, 'error': type(exc).__name__})
    err_summary = ', '.join(f"{e['route']} ({e['error']})" for e in errors)
    raise RuntimeError(f'No LLM route succeeded: {err_summary}. To test without active LLM services, select the Mock route.')

