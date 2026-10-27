# PromptForge AI — Self-Optimizing Prompt Engineering Lab

A runnable full-stack prototype with a FastAPI backend, responsive dark UI, SQLite experiment history, six prompt optimization strategies, analysis diagnostics, multiple model-provider support, and comparison/evaluation endpoints.

## Start in 3 minutes

Requires Python 3.10+.

```bash
cd promptforge_ai
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

**Default provider is `mock`: the whole workflow functions offline, but responses are explicitly simulated.** To use a real local LLM, install Ollama, run `ollama pull llama3.2`, and set in `.env`:

```env
PROVIDER=ollama
MODEL=llama3.2
BASE_URL=http://localhost:11434/v1
```

For an OpenAI-compatible hosted service, set `PROVIDER=openai_compatible`, `MODEL`, `BASE_URL` (including `/v1`), and `API_KEY` according to the provider's documentation. Keep `.env` secret.

## Features
- Prompt analysis with clarity, audience, formatting and constraint diagnostics
- Six deterministic optimization strategies
- Real model calls using OpenAI-compatible chat-completions API or Ollama
- Side-by-side experiments with heuristic scores, tokens and latency
- Optional reference-keyword recall
- Persistent experiment history, stats, experiment detail API
- API docs at `/docs`; health endpoint `/api/health`
- Offline mock mode for demonstrations

## Tests

```bash
pytest -q
```

## Research integrity
Heuristic scores are *not* true model accuracy, factuality or hallucination detection. Mock mode is *not* genuine LLM inference. For IA-3, compare an original-prompt baseline and multiple variants on a held-out benchmark. Use exact-match/unit tests for objectively gradable tasks and blinded human grading for open-ended responses. Repeat trials, report model/version, prompts, temperature, sample size and confidence intervals.

## Security / production checklist
This is a local-first academic prototype, not a public multi-tenant SaaS. Before public deployment add authentication, per-user authorization, rate limits, API quotas, secret management, CORS controls, request logging/redaction, migration tooling, background jobs, and hardened outbound model URL configuration. Never let users set arbitrary backend model URLs.

## Next milestones toward a larger research platform
1. Baseline-vs-optimized evaluation with held-out benchmark and exportable CSV.
2. Prompt version graph and multi-objective Pareto selection.
3. Grounded RAG evaluations with citation verification.
4. Model-provider adapters, retry/backoff, budgets and caching.
5. RBAC, team projects, audit trails, observability and queued experiments.
6. Human preference annotation and statistical significance analysis.

Do not inflate line count with generated filler. Extend only with tested, meaningful modules.

## Hybrid model routing (v1.1)

Configure `.env` with `OPENAI_API_KEY` (do not paste the key into the UI or source code), `OPENAI_MODEL`, and optionally the Ollama model. Install Ollama and run `ollama pull llama3.2` and `ollama serve` for local inference. The model must be installed locally. An OpenAI API key is billed separately from ChatGPT subscriptions.

`POST /api/run` and `POST /api/compare` accept `route`: `auto`, `local`, `cloud`, or `mock`, plus `prefer_local` (boolean). In `auto`, shorter tasks try Ollama first and then OpenAI; long tasks and complex coding tasks try OpenAI first and then Ollama. This is a transparent rule-based policy, not a trained routing model. Explicit routes do not silently fall back. The mock is never selected automatically. Response `generation` includes route, reason and attempts. Use `GET /api/providers` to inspect configuration without exposing secrets, and `POST /api/route-preview` to preview the policy.

**Security:** Keep `.env` server-side. Do not expose the API key in frontend JavaScript, logs or a public repository. For production, add login, rate limits, per-user quotas, cost ceilings, and abuse controls before allowing untrusted users to trigger paid API requests. OpenAI model names and access vary by account: set `OPENAI_MODEL` to one your account supports.

**Known limitations:** The dashboard UI does not yet expose a route selector; the API supports it. Automatic selection is rule-based; Ollama fallback only works while its server is running. Evaluation scores are heuristics, not validated accuracy. There is no 20,000-line enterprise implementation yet.
