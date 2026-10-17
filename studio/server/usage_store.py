"""Local usage ledger for Drama Studio API calls (CC Switch-style stats)."""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_projects_root: Path | None = None

# USD per 1M tokens (rough public list prices; Studio first-pass estimates)
_PRICE_PER_M: dict[str, dict[str, float]] = {
    "deepseek-chat": {"in": 0.28, "out": 0.42},
    "deepseek-reasoner": {"in": 0.55, "out": 2.19},
    "gpt-4o": {"in": 2.5, "out": 10.0},
    "gpt-4o-mini": {"in": 0.15, "out": 0.6},
    "claude-sonnet-4-5": {"in": 3.0, "out": 15.0},
    "claude-sonnet-4": {"in": 3.0, "out": 15.0},
    "gemini-2.0-flash": {"in": 0.1, "out": 0.4},
    "grok-2-latest": {"in": 2.0, "out": 10.0},
    "moonshot-v1-128k": {"in": 0.6, "out": 2.4},
    "qwen-plus": {"in": 0.4, "out": 1.2},
    "glm-4-plus": {"in": 0.7, "out": 2.8},
    "auto": {"in": 3.0, "out": 15.0},
    "default": {"in": 3.0, "out": 15.0},
}

# Flat USD estimates for media calls when tokens are absent
_MEDIA_FLAT: dict[str, float] = {
    "image": 0.04,
    "video": 0.25,
}


def init_usage(projects_root: Path) -> None:
    global _projects_root
    _projects_root = Path(projects_root)
    # Disk→PG merge happens in pg_backend.migrate_disk_state_to_pg at boot.


def usage_path(projects_root: Path | None = None) -> Path:
    root = projects_root or _projects_root
    if root is None:
        raise RuntimeError("usage store not initialized")
    return Path(root) / ".studio_usage.jsonl"


def _pg_enabled() -> bool:
    try:
        import pg_backend as _pg

        return bool(_pg.enabled())
    except Exception:
        return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_model(model: str) -> str:
    raw = (model or "").strip().lower()
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1]
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw or "unknown"


def estimate_cost(
    *,
    kind: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cache_read: int = 0,
    cache_write: int = 0,
) -> float:
    if kind in _MEDIA_FLAT and tokens_in == 0 and tokens_out == 0:
        return float(_MEDIA_FLAT[kind])
    mid = _norm_model(model)
    price = _PRICE_PER_M.get(mid)
    if not price:
        for key, val in _PRICE_PER_M.items():
            if key in mid or mid in key:
                price = val
                break
    if not price:
        price = {"in": 1.0, "out": 3.0}
    cost = (tokens_in / 1_000_000) * price["in"] + (tokens_out / 1_000_000) * price["out"]
    # Rough cache: read ~0.1x in, write ~1.25x in when present
    cost += (cache_read / 1_000_000) * price["in"] * 0.1
    cost += (cache_write / 1_000_000) * price["in"] * 1.25
    return round(cost, 6)


def record_usage(
    *,
    provider: str,
    model: str,
    kind: str = "text",
    ok: bool = True,
    status: int = 200,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cache_read: int = 0,
    cache_write: int = 0,
    latency_ms: int = 0,
    ttft_ms: int | None = None,
    streaming: bool = False,
    error: str = "",
    projects_root: Path | None = None,
) -> dict[str, Any]:
    """Append one usage event. Safe no-op if store not initialized."""
    try:
        path = usage_path(projects_root)
    except RuntimeError:
        return {}
    event = {
        "ts": _now_iso(),
        "provider": (provider or "unknown").strip() or "unknown",
        "model": (model or "unknown").strip() or "unknown",
        "kind": kind if kind in {"text", "image", "video"} else "text",
        "ok": bool(ok),
        "status": int(status or (200 if ok else 500)),
        "tokens_in": max(0, int(tokens_in or 0)),
        "tokens_out": max(0, int(tokens_out or 0)),
        "cache_read": max(0, int(cache_read or 0)),
        "cache_write": max(0, int(cache_write or 0)),
        "latency_ms": max(0, int(latency_ms or 0)),
        "ttft_ms": int(ttft_ms) if ttft_ms is not None else None,
        "streaming": bool(streaming),
        "error": (error or "")[:500],
    }
    event["tokens_total"] = (
        event["tokens_in"] + event["tokens_out"] + event["cache_read"] + event["cache_write"]
    )
    event["cost_usd"] = estimate_cost(
        kind=event["kind"],
        model=event["model"],
        tokens_in=event["tokens_in"],
        tokens_out=event["tokens_out"],
        cache_read=event["cache_read"],
        cache_write=event["cache_write"],
    )
    if _pg_enabled():
        try:
            import pg_backend as _pg

            key = "usage:.studio_usage"
            with _lock:
                existing = _pg.load_kv(key)
                events = list(existing.get("events") or []) if isinstance(existing, dict) else []
                events.append(event)
                _pg.upsert_kv(key, {"events": events[-8000:], "updatedAt": event["ts"]})
            return event
        except Exception:
            # Fall through to disk so the event is not lost.
            pass
    line = json.dumps(event, ensure_ascii=False)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return event


def _parse_range(range_key: str, date_from: str = "", date_to: str = "") -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if date_from and date_to:
        start = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        end = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return start, end
    key = (range_key or "7d").lower()
    if key in {"today", "1d", "day"}:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif key in {"30d", "30"}:
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=7)
    return start, now


def _iter_raw_events() -> list[dict[str, Any]]:
    """Load usage events from Postgres when enabled, else disk jsonl."""
    if _pg_enabled():
        try:
            import pg_backend as _pg

            with _lock:
                hit = _pg.load_kv("usage:.studio_usage")
            events = hit.get("events") if isinstance(hit, dict) else None
            if isinstance(events, list):
                return [e for e in events if isinstance(e, dict)]
        except Exception:
            pass
    try:
        path = usage_path()
    except RuntimeError:
        return []
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with _lock:
        raw = path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            out.append(ev)
    return out


def _load_events(
    *,
    start: datetime,
    end: datetime,
    provider: str = "",
    model: str = "",
    kind: str = "",
    status: str = "",
    limit: int = 5000,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ev in _iter_raw_events():
        try:
            ts = datetime.fromisoformat(str(ev.get("ts") or "").replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts < start or ts > end:
            continue
        if provider and str(ev.get("provider") or "") != provider:
            continue
        if model and model.lower() not in str(ev.get("model") or "").lower():
            continue
        if kind and kind != "all" and str(ev.get("kind") or "") != kind:
            continue
        if status and status != "all":
            code = int(ev.get("status") or 0)
            if status == "2xx" and not (200 <= code < 300):
                continue
            if status == "4xx" and not (400 <= code < 500):
                continue
            if status == "5xx" and not (500 <= code < 600):
                continue
            if status.isdigit() and code != int(status):
                continue
        out.append(ev)
        if len(out) >= limit:
            break
    out.sort(key=lambda e: str(e.get("ts") or ""), reverse=True)
    return out


def _bucket_key(ts: datetime, granularity: str) -> str:
    if granularity == "hour":
        return ts.strftime("%Y-%m-%d %H:00")
    return ts.strftime("%Y-%m-%d")


def query_usage(
    *,
    range_key: str = "7d",
    date_from: str = "",
    date_to: str = "",
    provider: str = "",
    model: str = "",
    kind: str = "all",
    status: str = "all",
    log_limit: int = 100,
    log_offset: int = 0,
) -> dict[str, Any]:
    start, end = _parse_range(range_key, date_from, date_to)
    events = _load_events(
        start=start,
        end=end,
        provider=provider,
        model=model,
        kind=kind,
        status=status,
    )
    total = len(events)
    ok_n = sum(1 for e in events if e.get("ok"))
    tokens_in = sum(int(e.get("tokens_in") or 0) for e in events)
    tokens_out = sum(int(e.get("tokens_out") or 0) for e in events)
    cache_read = sum(int(e.get("cache_read") or 0) for e in events)
    cache_write = sum(int(e.get("cache_write") or 0) for e in events)
    tokens_total = tokens_in + tokens_out + cache_read + cache_write
    cost = sum(float(e.get("cost_usd") or 0) for e in events)
    cacheable = tokens_in + cache_read
    cache_hit = (cache_read / cacheable) if cacheable else 0.0

    granularity = "hour" if (end - start) <= timedelta(days=1, hours=12) else "day"
    req_trend: dict[str, int] = defaultdict(int)
    tok_in: dict[str, int] = defaultdict(int)
    tok_out: dict[str, int] = defaultdict(int)
    tok_cr: dict[str, int] = defaultdict(int)
    tok_cw: dict[str, int] = defaultdict(int)
    cost_trend: dict[str, float] = defaultdict(float)
    for e in events:
        try:
            ts = datetime.fromisoformat(str(e.get("ts") or "").replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        b = _bucket_key(ts, granularity)
        req_trend[b] += 1
        tok_in[b] += int(e.get("tokens_in") or 0)
        tok_out[b] += int(e.get("tokens_out") or 0)
        tok_cr[b] += int(e.get("cache_read") or 0)
        tok_cw[b] += int(e.get("cache_write") or 0)
        cost_trend[b] += float(e.get("cost_usd") or 0)

    buckets = sorted(set(req_trend) | set(tok_in) | set(cost_trend))
    trend = {
        "granularity": granularity,
        "buckets": buckets,
        "requests": [req_trend[b] for b in buckets],
        "tokens_in": [tok_in[b] for b in buckets],
        "tokens_out": [tok_out[b] for b in buckets],
        "cache_read": [tok_cr[b] for b in buckets],
        "cache_write": [tok_cw[b] for b in buckets],
        "cost_usd": [round(cost_trend[b], 6) for b in buckets],
    }

    by_provider: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    for e in events:
        p = str(e.get("provider") or "unknown")
        m = str(e.get("model") or "unknown")
        bp = by_provider.setdefault(
            p,
            {"provider": p, "requests": 0, "ok": 0, "fail": 0, "tokens": 0, "cost_usd": 0.0, "latency_ms": 0},
        )
        bp["requests"] += 1
        if e.get("ok"):
            bp["ok"] += 1
        else:
            bp["fail"] += 1
        bp["tokens"] += int(e.get("tokens_total") or 0)
        bp["cost_usd"] += float(e.get("cost_usd") or 0)
        bp["latency_ms"] += int(e.get("latency_ms") or 0)

        bm = by_model.setdefault(
            m,
            {
                "model": m,
                "provider": p,
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
                "latency_ms": 0,
            },
        )
        bm["requests"] += 1
        bm["tokens_in"] += int(e.get("tokens_in") or 0)
        bm["tokens_out"] += int(e.get("tokens_out") or 0)
        bm["cost_usd"] += float(e.get("cost_usd") or 0)
        bm["latency_ms"] += int(e.get("latency_ms") or 0)

    providers = []
    for row in by_provider.values():
        n = row["requests"] or 1
        row["success_rate"] = round(row["ok"] / n, 4)
        row["avg_latency_ms"] = int(row["latency_ms"] / n)
        row["cost_usd"] = round(row["cost_usd"], 6)
        del row["latency_ms"]
        providers.append(row)
    providers.sort(key=lambda r: r["requests"], reverse=True)

    models = []
    for row in by_model.values():
        n = row["requests"] or 1
        row["avg_latency_ms"] = int(row["latency_ms"] / n)
        row["cost_usd"] = round(row["cost_usd"], 6)
        del row["latency_ms"]
        models.append(row)
    models.sort(key=lambda r: r["requests"], reverse=True)

    limit = max(1, min(int(log_limit or 100), 500))
    offset = max(0, int(log_offset or 0))
    if offset >= total and total > 0:
        offset = (max(0, (total - 1) // limit)) * limit
    page = (offset // limit) + 1 if total else 1
    page_count = max(1, (total + limit - 1) // limit) if total else 1
    logs_slice = events[offset : offset + limit]

    return {
        "range": {"from": start.isoformat(), "to": end.isoformat(), "key": range_key or "7d"},
        "hero": {
            "requests": total,
            "tokens": tokens_total,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "cache_hit_rate": round(cache_hit, 4),
            "cost_usd": round(cost, 6),
            "success_rate": round((ok_n / total) if total else 0.0, 4),
        },
        "trend": trend,
        "logs": logs_slice,
        "logsMeta": {
            "total": total,
            "offset": offset,
            "limit": limit,
            "page": page,
            "pageCount": page_count,
            "hasPrev": offset > 0,
            "hasNext": offset + limit < total,
        },
        "byProvider": providers,
        "byModel": models,
        "filters": {
            "providers": sorted({str(e.get("provider") or "") for e in events if e.get("provider")}),
            "models": sorted({str(e.get("model") or "") for e in events if e.get("model")}),
        },
        "updatedAt": _now_iso(),
        "serverTime": int(time.time()),
    }


def seed_demo_if_empty(projects_root: Path | None = None) -> int:
    """Insert a few sample rows so the usage UI can be reviewed with data."""
    try:
        path = usage_path(projects_root)
    except RuntimeError:
        return 0
    if path.is_file() and path.stat().st_size > 0:
        return 0
    now = datetime.now(timezone.utc)
    samples = [
        ("cursor", "auto", "text", True, 1200, 800, 1800),
        ("deepseek", "deepseek-chat", "text", True, 2400, 1600, 2200),
        ("openai", "gpt-4o-mini", "text", True, 900, 600, 1100),
        ("volcengine", "seedream", "image", True, 0, 0, 4500),
        ("volcengine", "seedance", "video", False, 0, 0, 12000),
        ("anthropic", "claude-sonnet-4-5", "text", True, 3000, 2000, 3500),
        ("qwen", "qwen-plus", "text", True, 1500, 900, 1600),
        ("cursor", "auto", "text", True, 1100, 700, 2000),
    ]
    n = 0
    for i, (prov, model, kind, ok, tin, tout, lat) in enumerate(samples):
        ts = (now - timedelta(hours=i * 5)).isoformat()
        event = {
            "ts": ts,
            "provider": prov,
            "model": model,
            "kind": kind,
            "ok": ok,
            "status": 200 if ok else 500,
            "tokens_in": tin,
            "tokens_out": tout,
            "cache_read": 200 if kind == "text" and i % 2 == 0 else 0,
            "cache_write": 100 if kind == "text" and i % 3 == 0 else 0,
            "latency_ms": lat,
            "ttft_ms": 400 if kind == "text" else None,
            "streaming": kind == "text",
            "error": "" if ok else "demo failure",
        }
        event["tokens_total"] = (
            event["tokens_in"] + event["tokens_out"] + event["cache_read"] + event["cache_write"]
        )
        event["cost_usd"] = estimate_cost(
            kind=kind,
            model=model,
            tokens_in=tin,
            tokens_out=tout,
            cache_read=event["cache_read"],
            cache_write=event["cache_write"],
        )
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        n += 1
    return n
