#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ragiton
"""
Agent Evals — cursor_cost.py

Estimate per-call USD cost for a Cursor `cursor-agent --output-format json` envelope.

The envelope exposes only token counts (inputTokens / outputTokens / cacheReadTokens /
cacheWriteTokens). USD is derived by applying published per-model rates from
harness/cursor_pricing.json, which is a snapshot of
https://cursor.com/docs/models-and-pricing (retrieval date in the JSON's _source).

Usage:
  python harness/cursor_cost.py path/to/stdout.json
  python harness/cursor_cost.py -            # read from stdin
  from cursor_cost import cost_from_envelope
  cost_from_envelope({"usage": {...}, "model": "..."})

Output JSON:
  {
    "cost_usd": float | None,
    "input_tokens": int,
    "output_tokens": int,
    "cache_read_tokens": int,
    "cache_write_tokens": int,
    "model": str | None,
    "pricing_source": str,   # "cursor_pricing_estimate" | "cursor_pricing_unknown_model"
    "pricing_url": str,
    "rate_card": dict | None,
    "notes": list[str]
  }
"""
from __future__ import annotations
import json, pathlib, sys, datetime
from typing import Any

HARNESS = pathlib.Path(__file__).resolve().parent
PRICING_PATH = HARNESS / "cursor_pricing.json"


def _load_pricing(path: pathlib.Path = PRICING_PATH) -> dict:
    return json.loads(path.read_text())


def _resolve_rate(model: str | None, pricing: dict) -> tuple[dict | None, str, str]:
    """Return (rate_dict, model_key_used, alias_reason)."""
    if not model:
        return None, "", "no model in envelope"
    models = pricing.get("models", {})
    aliases = pricing.get("_aliases", {})
    if model in models:
        return models[model], model, ""
    if model in aliases:
        target = aliases[model]
        if target in models:
            return models[target], target, f"alias {model} -> {target}"
    # Fuzzy match: look for any key that contains the model name
    needle = model.lower()
    for key in models:
        if needle in key.lower() or key.lower() in needle:
            return models[key], key, f"fuzzy match {model} -> {key}"
    return None, "", f"unknown model {model!r}"


def cost_from_envelope(envelope: dict, pricing: dict | None = None) -> dict:
    """Compute estimated USD cost from a Cursor JSON envelope.

    The envelope shape (cursor-agent --output-format json):
      {
        "type": "result",
        "subtype": "success",
        "is_error": false,
        "duration_ms": ...,
        "result": "...",
        "session_id": "...",
        "usage": {
          "inputTokens": int,
          "outputTokens": int,
          "cacheReadTokens": int,
          "cacheWriteTokens": int
        },
        "model": "gpt-5.6-luna"   # may be present; some envelopes omit it
      }
    """
    pricing = pricing or _load_pricing()
    usage = (envelope or {}).get("usage") or {}
    input_tokens = int(usage.get("inputTokens") or 0)
    output_tokens = int(usage.get("outputTokens") or 0)
    cache_read = int(usage.get("cacheReadTokens") or 0)
    cache_write = int(usage.get("cacheWriteTokens") or 0)
    # Cursor's envelope may or may not include a top-level `model` field.
    # Some builds put it in a sibling like `model_name` or `selectedModel`.
    model = (
        envelope.get("model")
        or envelope.get("model_name")
        or envelope.get("selectedModel")
        or envelope.get("selected_model")
    )

    rate, used_key, alias_note = _resolve_rate(model, pricing)
    notes: list[str] = []
    if alias_note:
        notes.append(alias_note)

    if rate is None:
        return {
            "cost_usd": None,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "model": model,
            "pricing_source": "cursor_pricing_unknown_model",
            "pricing_url": pricing.get("_source", {}).get("url", ""),
            "rate_card": None,
            "notes": notes + ["no rate card matched — cost left null"],
        }

    def usd(tokens: int, rate_value: float | None) -> float:
        if not tokens or not rate_value:
            return 0.0
        return (tokens / 1_000_000.0) * float(rate_value)

    # Non-cached input = total input minus what came from the cache (cache read).
    # Cursor splits tokens by class in the envelope, so we charge each class at
    # its own published rate. The fresh-input rate is `input_usd`; cache reads
    # are charged at `cache_read_usd`; cache writes at `cache_write_usd`.
    cost = (
        usd(input_tokens, rate.get("input_usd"))
        + usd(cache_read, rate.get("cache_read_usd"))
        + usd(cache_write, rate.get("cache_write_usd"))
        + usd(output_tokens, rate.get("output_usd"))
    )
    return {
        "cost_usd": round(cost, 6),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "model": model or used_key,
        "model_rate_key": used_key,
        "pricing_source": "cursor_pricing_estimate",
        "pricing_url": pricing.get("_source", {}).get("url", ""),
        "pricing_retrieved_at": pricing.get("_source", {}).get("retrieved_at", ""),
        "rate_card": {
            "input_usd_per_million": rate.get("input_usd"),
            "cache_read_usd_per_million": rate.get("cache_read_usd"),
            "cache_write_usd_per_million": rate.get("cache_write_usd"),
            "output_usd_per_million": rate.get("output_usd"),
            "source_pool": rate.get("source_pool"),
        },
        "notes": notes + [
            "estimate — Cursor's CLI does not return per-call USD; rates from cursor.com/docs/models-and-pricing"
        ],
    }


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        envelope = json.loads(pathlib.Path(sys.argv[1]).read_text())
    else:
        envelope = json.loads(sys.stdin.read())
    out = cost_from_envelope(envelope)
    out["computed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(json.dumps(out, indent=2))
    return 0 if out.get("cost_usd") is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
