"""
main.py — FastAPI server cho Stock Quant Dashboard
Chạy: uvicorn main:app --reload
"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from data_fetcher import get_full_snapshot, get_price_history, get_foreign_flow, get_proprietary_flow
from quant_engine import compute_quant_matrix, run_and_save

app = FastAPI(
    title="Stock Quant Dashboard API",
    description="API cào dữ liệu chứng khoán Việt Nam",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Simple in-memory cache ────────────────────────────────────────────────────
_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 300  # 5 phút


def _cached(key: str, fn, ttl: int = CACHE_TTL):
    now = time.time()
    if key in _cache:
        ts, val = _cache[key]
        if now - ts < ttl:
            return val
    val = fn()
    _cache[key] = (now, val)
    return val


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    preview_path = Path(__file__).resolve().parent.parent / "frontend" / "public" / "preview.html"
    if preview_path.exists():
        return HTMLResponse(content=preview_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>Dashboard preview not found</h2>")


@app.get("/output_data.json")
def serve_output_json():
    json_path = Path(__file__).resolve().parent / "output_data.json"
    if json_path.exists():
        return FileResponse(json_path, media_type="application/json")
    raise HTTPException(status_code=404, detail="output_data.json not found")


@app.get("/api/price/{symbol}")
def price_history(symbol: str, days: int = Query(default=30, ge=1, le=365)):
    key = f"price:{symbol.upper()}:{days}"
    df = _cached(key, lambda: get_price_history(symbol, days))
    records = []
    for _, row in df.iterrows():
        records.append({
            "Date": str(row["Date"])[:10],
            "Open": float(row["Open"]),
            "High": float(row["High"]),
            "Low":  float(row["Low"]),
            "Close": float(row["Close"]),
            "Volume": int(row["Volume"]),
        })
    return {"symbol": symbol.upper(), "data": records}


@app.get("/api/foreign-flow/{symbol}")
def foreign_flow(symbol: str, days: int = Query(default=20, ge=1, le=120)):
    key = f"foreign:{symbol.upper()}:{days}"
    df = _cached(key, lambda: get_foreign_flow(symbol, days))
    records = [
        {"Date": str(r["Date"])[:10], "NetValue_Billion": float(r["NetValue_Billion"])}
        for r in df.to_dict(orient="records")
    ]
    return {"symbol": symbol.upper(), "data": records}


@app.get("/api/proprietary-flow/{symbol}")
def proprietary_flow(symbol: str, days: int = Query(default=20, ge=1, le=120)):
    key = f"prop:{symbol.upper()}:{days}"
    df = _cached(key, lambda: get_proprietary_flow(symbol, days))
    records = [
        {"Date": str(r["Date"])[:10], "NetValue_Billion": float(r["NetValue_Billion"])}
        for r in df.to_dict(orient="records")
    ]
    return {"symbol": symbol.upper(), "data": records}


@app.get("/api/snapshot/{symbol}")
def snapshot(symbol: str, price_days: int = Query(default=30), flow_days: int = Query(default=20)):
    key = f"snapshot:{symbol.upper()}:{price_days}:{flow_days}"
    data = _cached(key, lambda: get_full_snapshot(symbol, price_days, flow_days))
    return data


@app.get("/api/quant/{symbol}")
def quant_matrix(symbol: str):
    key = f"quant:{symbol.upper()}"
    data = _cached(key, lambda: compute_quant_matrix(symbol))
    return data
