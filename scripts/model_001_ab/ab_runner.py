"""MODEL-001 escalate-tier A/B runner (6.2 prep) — kimi-k2.6 vs qwen-3.6-plus.

Runs the 20 fixture tasks through BOTH candidate models via the MODEL-001 client wrapper (env-var keys
only), records latency + raw output + schema-validity, and writes per-candidate results. Content quality
is scored in a SEPARATE judge/human pass (see docs/model-001-ab-plan.md) — this runner captures evidence,
it does not declare a winner.

Usage (Navigator-run at cutover):
    python scripts/model_001_ab/ab_runner.py --dry-run     # validate tasks + build requests, NO network/keys
    python scripts/model_001_ab/ab_runner.py --live        # needs OPENROUTER_BASE_URL + OPENROUTER_API_KEY

Nothing here is auto-run; live calls cost money and require the Navigator's keys.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]           # ceph-v3 repo root
sys.path.insert(0, str(ROOT))

from agent import model_routing as mr                 # noqa: E402
from agent import model_client as mc                  # noqa: E402

TASKS_PATH = Path(__file__).resolve().parent / "ab_tasks.json"
OUT_DIR = Path(__file__).resolve().parent / "results"


def _config_for(model: str) -> dict:
    cfg = copy.deepcopy(mr.DEFAULT_CONFIG)
    cfg["tiers"]["escalate"]["model"] = model         # A/B swaps only the escalate model
    return cfg


def _schema_valid(text: str, schema: dict) -> bool:
    try:
        parsed = json.loads(text)
    except Exception:
        return False
    ok, _ = mr.validate_tool_call(parsed if isinstance(parsed, dict) else {"_": parsed}, schema)
    return ok


def run(candidate: str, tasks: list, live: bool, client_factory=None) -> dict:
    cfg = _config_for(candidate)
    rows = []
    for t in tasks:
        messages = [{"role": "user", "content": t["prompt"]}]
        req = mc.build_request(mr.ESCALATE, messages, payload_tags=None, config=cfg)  # residency-safe fixtures
        row = {"id": t["id"], "domain": t["domain"], "task_type": t["task_type"], "model": candidate,
               "request_ok": True}
        if not live:
            rows.append({**row, "mode": "dry-run"})
            continue
        t0 = time.time()
        try:
            resp = mc.call(mr.ESCALATE, messages, payload_tags=None, config=cfg, client_factory=client_factory)
            text = resp.choices[0].message.content if hasattr(resp, "choices") else str(resp)
            row["latency_s"] = round(time.time() - t0, 3)
            row["output"] = text
            usage = getattr(resp, "usage", None)
            row["tokens"] = getattr(usage, "total_tokens", None) if usage else None
            if "schema" in t:
                row["schema_valid"] = _schema_valid(text, t["schema"])
        except Exception as exc:                       # capture, never crash the batch
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return {"candidate": candidate, "n": len(rows), "rows": rows}


def summarize(result: dict) -> dict:
    rows = result["rows"]
    scored = [r for r in rows if "schema_valid" in r]
    lat = [r["latency_s"] for r in rows if "latency_s" in r]
    return {
        "candidate": result["candidate"],
        "tasks": result["n"],
        "errors": sum(1 for r in rows if "error" in r),
        "schema_pass_rate": (sum(r["schema_valid"] for r in scored) / len(scored)) if scored else None,
        "avg_latency_s": (sum(lat) / len(lat)) if lat else None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MODEL-001 escalate A/B runner")
    ap.add_argument("--live", action="store_true", help="make live calls (needs OpenRouter env keys)")
    ap.add_argument("--dry-run", action="store_true", help="validate + build requests only (default)")
    args = ap.parse_args(argv)
    live = args.live and not args.dry_run

    data = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    tasks, candidates = data["tasks"], data["_meta"]["candidates"]
    assert len(tasks) == 20, f"expected 20 tasks, found {len(tasks)}"

    print(f"MODEL-001 A/B — {len(tasks)} tasks x {len(candidates)} candidates "
          f"({'LIVE' if live else 'DRY-RUN'})")
    OUT_DIR.mkdir(exist_ok=True)
    summaries = []
    for cand in candidates:
        result = run(cand, tasks, live=live)
        (OUT_DIR / f"{cand.replace('/', '_')}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        s = summarize(result)
        summaries.append(s)
        print(f"  {cand:28} tasks={s['tasks']} errors={s['errors']} "
              f"schema_pass={s['schema_pass_rate']} avg_latency={s['avg_latency_s']}")
    (OUT_DIR / "summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    if not live:
        print("dry-run OK: all requests built, residency clean, tasks validated. "
              "Run --live with keys to collect outputs, then score per the plan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
