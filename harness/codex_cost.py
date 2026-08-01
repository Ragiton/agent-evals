#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ragiton
"""
Agent Evals — codex_cost.py

Estimate per-call USD cost for a Codex `codex exec --json` event stream.

The stream emits turn.completed.usage events with token counts but no USD. We
sum the tokens across turns and apply published per-model rates from
harness/codex_pricing.json, a snapshot of
https://platform.openai.com/docs/pricing (retrieval date in the JSON's _source).

Usage:
  python harness/codex_cost.py path/to/event_stream.jsonl
  python harness/codex_cost.py -            # read JSONL from stdin
  from codex_cost import cost_from_event_stream
  cost_from_event_stream(["...\n", "...\n"])

Output JSON:
  {
    "cost_usd": float | None,
    "input_tokens": int,
    "cached_input_tokens": int,
    "cache_write_input_tokens": int,
    "output_tokens": int,
    "reasoning_output_tokens": int,
    "turns": int,
    "model": str | None,
    "pricing_source": str,
    "pricing_url": str,
    "rate_card": dict | None,
    "notes": list[str]
  }
"""
from __future__ import annotations
import json, pathlib, sys, datetime
from typing import Any, Iterable

HARNESS = pathlib.Path(__file__).resolve().parent
PRICING_PATH = HARNESS / "codex_pricing.json"


def _load_pricing(path: pathlib.Path = PRICING_PATH) -> dict:
    return json.loads(path.read_text())


def _resolve_rate(model: str | None, pricing: dict) -> tuple[dict | None, str, str]:
    if not model:
        return None, "", "no model in stream"
    models = pricing.get("models", {})
    aliases = pricing.get("_aliases", {})
    if model in models:
        return models[model], model, ""
    if model in aliases:
        target = aliases[model]
        if target in models:
            return models[target], target, f"alias {model} -> {target}"
    needle = model.lower()
    for key in models:
        if needle in key.lower() or key.lower() in needle:
            return models[key], key, f"fuzzy match {model} -> {key}"
    return None, "", f"unknown model {model!r}"


def _events_to_summaries(events: Iterable[dict]) -> list[dict]:
    """Extract (model, usage) pairs from a Codex JSONL stream.

    The stream shape (codex exec --json):
      {"type": "thread.started", "thread_id": "..."}
      {"type": "turn.started"}
      {"type": "item.completed", "item": {...}}
      {"type": "turn.completed", "usage": {
          "input_tokens": int,
          "cached_input_tokens": int,
          "cache_write_input_tokens": int,
          "output_tokens": int,
          "reasoning_output_tokens": int,
      }}
    Some events also carry a `model` field; thread metadata may carry it under
    `thread.model` or `model`.
    """
    summaries = []
    model = None
    for ev in events:
        if not isinstance(ev, dict):
            continue
        ev_type = ev.get("type")
        if not model:
            for k in ("model", "model_name", "selected_model", "selectedModel"):
                if ev.get(k):
                    model = ev[k]
                    break
            thread = ev.get("thread")
            if not model and isinstance(thread, dict):
                for k in ("model", "model_name"):
                    if thread.get(k):
                        model = thread[k]
                        break
        if ev_type == "turn.completed":
            usage = ev.get("usage") or {}
            if not model and isinstance(ev.get("thread"), dict):
                model = ev["thread"].get("model")
            summaries.append({
                "model": model,
                "input_tokens": int(usage.get("input_tokens") or 0),
                "cached_input_tokens": int(usage.get("cached_input_tokens") or 0),
                "cache_write_input_tokens": int(usage.get("cache_write_input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
                "reasoning_output_tokens": int(usage.get("reasoning_output_tokens") or 0),
            })
    return summaries


def cost_from_event_stream(lines: list[str] | Iterable[str], pricing: dict | None = None) -> dict:
    """Parse JSONL lines and return a per-stream cost summary."""
    pricing = pricing or _load_pricing()
    events: list[dict] = []
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    summaries = _events_to_summaries(events)
    # Aggregate tokens across turns.
    agg = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }
    model = None
    for s in summaries:
        for k in agg:
            agg[k] += s.get(k, 0)
        if s.get("model") and not model:
            model = s["model"]
    # If the stream never had a turn.completed, still try to detect a model
    if not model:
        for ev in events:
            if isinstance(ev, dict) and ev.get("model"):
                model = ev["model"]
                break

    rate, used_key, alias_note = _resolve_rate(model, pricing)
    notes: list[str] = []
    if alias_note:
        notes.append(alias_note)
    if not summaries:
        notes.append("no turn.completed events in stream")

    if rate is None:
        return {
            "cost_usd": None,
            "input_tokens": agg["input_tokens"],
            "cached_input_tokens": agg["cached_input_tokens"],
            "cache_write_input_tokens": agg["cache_write_input_tokens"],
            "output_tokens": agg["output_tokens"],
            "reasoning_output_tokens": agg["reasoning_output_tokens"],
            "turns": len(summaries),
            "model": model,
            "pricing_source": "codex_pricing_unknown_model",
            "pricing_url": pricing.get("_source", {}).get("url", ""),
            "rate_card": None,
            "notes": notes + ["no rate card matched — cost left null"],
        }

    def usd(tokens: int, rate_value: float | None) -> float:
        if not tokens or not rate_value:
            return 0.0
        return (tokens / 1_000_000.0) * float(rate_value)

    # Codex stream tracks input_tokens INCLUDING cached. So charge:
    #   fresh_input  = input_tokens - cached_input_tokens - cache_write_input_tokens
    #   cached       = cached_input_tokens
    #   cache_write  = cache_write_input_tokens
    #   output       = output_tokens (+ reasoning_output_tokens at output rate)
    fresh_input = max(
        0,
        agg["input_tokens"]
        - agg["cached_input_tokens"]
        - agg["cache_write_input_tokens"],
    )
    cost = (
        usd(fresh_input, rate.get("input_usd"))
        + usd(agg["cached_input_tokens"], rate.get("cached_input_usd"))
        + usd(agg["cache_write_input_tokens"], rate.get("cache_write_usd"))
        + usd(agg["output_tokens"], rate.get("output_usd"))
        + usd(agg["reasoning_output_tokens"], rate.get("output_usd"))
    )
    return {
        "cost_usd": round(cost, 6),
        "input_tokens": agg["input_tokens"],
        "cached_input_tokens": agg["cached_input_tokens"],
        "cache_write_input_tokens": agg["cache_write_input_tokens"],
        "output_tokens": agg["output_tokens"],
        "reasoning_output_tokens": agg["reasoning_output_tokens"],
        "turns": len(summaries),
        "model": model or used_key,
        "model_rate_key": used_key,
        "pricing_source": "codex_pricing_estimate",
        "pricing_url": pricing.get("_source", {}).get("url", ""),
        "pricing_retrieved_at": pricing.get("_source", {}).get("retrieved_at", ""),
        "rate_card": {
            "input_usd_per_million": rate.get("input_usd"),
            "cached_input_usd_per_million": rate.get("cached_input_usd"),
            "cache_write_usd_per_million": rate.get("cache_write_usd"),
            "output_usd_per_million": rate.get("output_usd"),
        },
        "notes": notes + [
            "estimate — Codex CLI does not return per-call USD; rates from platform.openai.com/docs/pricing"
        ],
    }


def main() -> int:
    args = sys.argv[1:]
    model = None
    if "--model" in args:
        i = args.index("--model")
        model = args[i + 1]
        del args[i:i + 2]
    if args and args[0] != "-":
        text = pathlib.Path(args[0]).read_text()
    else:
        text = sys.stdin.read()
    lines = text.splitlines()
    # If --model was given, attach it to every event so the resolver sees it.
    if model:
        new_lines = []
        for ln in lines:
            try:
                ev = json.loads(ln)
            except Exception:
                new_lines.append(ln)
                continue
            if "model" not in ev:
                ev["model"] = model
            new_lines.append(json.dumps(ev))
        lines = new_lines
    out = cost_from_event_stream(lines)
    out["computed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(json.dumps(out, indent=2))
    return 0 if out.get("cost_usd") is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
