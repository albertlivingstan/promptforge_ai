from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from contextlib import contextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .core import STRATEGIES, analyze, optimize, evaluate
from .router import hybrid_generate, choose_route, targets

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DB = Path(os.getenv("DATABASE_PATH", str(ROOT / "promptforge.db")))
if not DB.is_absolute(): DB = ROOT / DB
DB.parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="PromptForge AI", version="1.0.0", description="Adaptive prompt optimization with explicit evaluation")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

@contextmanager
def db():
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally: conn.close()

with db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, original TEXT NOT NULL,
        strategy TEXT NOT NULL, optimized TEXT NOT NULL, response TEXT NOT NULL,
        metrics TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, latency_ms REAL NOT NULL, tokens INTEGER NOT NULL
    )""")

class PromptRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=10000)

class OptimizeRequest(PromptRequest):
    strategies: list[str] = Field(default_factory=lambda: list(STRATEGIES))
    audience: str = Field(default="a university student", max_length=200)

class RunRequest(PromptRequest):
    strategy: str = "structured"
    audience: str = "a university student"
    expected: str = Field(default="", max_length=10000)
    route: Literal["auto", "local", "cloud", "mock"] = "auto"
    prefer_local: bool = True

class CompareRequest(PromptRequest):
    strategies: list[str] = Field(default_factory=lambda: ["structured", "role_based", "decomposition"])
    audience: str = "a university student"
    expected: str = Field(default="", max_length=10000)
    route: Literal["auto", "local", "cloud", "mock"] = "auto"
    prefer_local: bool = True

@app.get("/")
def index(): return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/health")
def health():
    configured = targets()
    local_m = configured["local"].model
    cloud_m = configured["cloud"].model
    return {
        "status": "ok",
        "provider": "ollama" if local_m else "hybrid",
        "model": local_m or "demo",
        "local_model": local_m,
        "cloud_model": cloud_m,
        "cloud_configured": bool(configured["cloud"].api_key),
    }

@app.get("/api/providers")
def providers():
    configured = targets()
    is_local_ready = False
    try:
        import httpx
        url = configured["local"].base_url.replace("/v1", "").rstrip("/") + "/api/tags"
        with httpx.Client(timeout=0.8) as client:
            res = client.get(url)
            is_local_ready = (res.status_code == 200)
    except Exception:
        is_local_ready = False
    return {
        "routes": ["auto", "local", "cloud", "mock"],
        "local_ready": is_local_ready,
        "local_model": configured["local"].model,
        "cloud_configured": bool(configured["cloud"].api_key),
        "cloud_model": configured["cloud"].model,
        "note": "Local readiness is dynamically verified. Keys are never returned."
    }


@app.post("/api/route-preview")
def route_preview(request: RunRequest):
    order, reason = choose_route(request.prompt, request.route, request.prefer_local)
    return {"attempt_order": order, "reason": reason}

@app.get("/api/strategies")
def strategies(): return {"strategies": STRATEGIES}

@app.post("/api/analyze")
def analyze_prompt(request: PromptRequest): return analyze(request.prompt)

@app.post("/api/optimize")
def optimize_prompt(request: OptimizeRequest):
    if not request.strategies or any(s not in STRATEGIES for s in request.strategies): raise HTTPException(400, "Invalid strategies")
    return {"analysis": analyze(request.prompt), "candidates": [{"strategy": s, "prompt": optimize(request.prompt, s, request.audience)} for s in dict.fromkeys(request.strategies)]}

async def run_one(request: RunRequest):
    if request.strategy not in STRATEGIES: raise HTTPException(400, "Invalid strategy")
    improved = optimize(request.prompt, request.strategy, request.audience)
    try:
        result = await hybrid_generate(improved, request.route, request.prefer_local)
    except Exception as exc:
        raise HTTPException(502, f"LLM request failed: {type(exc).__name__}: {str(exc)[:250]}") from exc
    metrics = evaluate(result["text"], request.prompt, request.expected)
    with db() as c:
        cursor = c.execute("INSERT INTO experiments(created_at,original,strategy,optimized,response,metrics,provider,model,latency_ms,tokens) VALUES(?,?,?,?,?,?,?,?,?,?)", (
            datetime.now(timezone.utc).isoformat(), request.prompt, request.strategy, improved, result["text"], json.dumps(metrics), result["provider"], result["model"], result["latency_ms"], result["tokens"]))
        id_ = cursor.lastrowid
    return {"id": id_, "original": request.prompt, "strategy": request.strategy, "optimized": improved, "response": result["text"], "metrics": metrics, "generation": result}

@app.post("/api/run")
async def run(request: RunRequest): return await run_one(request)

@app.post("/api/compare")
async def compare(request: CompareRequest):
    if not 1 <= len(request.strategies) <= 6: raise HTTPException(400, "Choose 1–6 strategies")
    if any(s not in STRATEGIES for s in request.strategies): raise HTTPException(400, "Invalid strategy")
    results = [await run_one(RunRequest(prompt=request.prompt, strategy=s, audience=request.audience, expected=request.expected, route=request.route, prefer_local=request.prefer_local)) for s in dict.fromkeys(request.strategies)]
    # Heuristic selection; not evidence of true factual correctness.
    best = max(results, key=lambda r: r["metrics"]["heuristic_score"])
    return {"results": results, "best_strategy": best["strategy"], "selection_note": "Selected by heuristic proxy only; validate with task-specific ground truth."}

@app.get("/api/history")
def history(limit: int = 30):
    with db() as c:
        rows = c.execute("SELECT id,created_at,original,strategy,metrics,provider,model,latency_ms,tokens FROM experiments ORDER BY id DESC LIMIT ?", (max(1, min(200, limit)),)).fetchall()
    return [{**dict(r), "metrics": json.loads(r["metrics"])} for r in rows]

@app.get("/api/experiments/{experiment_id}")
def experiment(experiment_id: int):
    with db() as c: row = c.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
    if not row: raise HTTPException(404, "Experiment not found")
    return {**dict(row), "metrics": json.loads(row["metrics"])}

@app.get("/api/stats")
def stats():
    with db() as c:
        row = c.execute("SELECT COUNT(*) as total, AVG(latency_ms) as latency, SUM(tokens) as tokens FROM experiments").fetchone()
        grouped = c.execute("SELECT strategy, COUNT(*) as count FROM experiments GROUP BY strategy ORDER BY count DESC").fetchall()
    return {"total": row["total"], "avg_latency_ms": round(row["latency"] or 0, 1), "tokens": row["tokens"] or 0, "strategies": [dict(r) for r in grouped]}
