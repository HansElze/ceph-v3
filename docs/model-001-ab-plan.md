# MODEL-001 — Escalate-tier A/B plan (6.2 prep)

**Question:** which model should the TIER 1 (escalate) path pin — **kimi-k2.6** (incumbent) or
**qwen/qwen-3.6-plus**? Escalate handles high-stakes structured governance + financial outputs, so the
A/B weights schema fidelity and reasoning over raw fluency.

## What's prepared (this brief)
- **20 fixture tasks** — `scripts/model_001_ab/ab_tasks.json`: 8 `governance_review`, 6 `financial_modeling`,
  6 `structured_output_fidelity` (strict JSON — because the router escalates on schema failures). Prompts
  are pilot fixtures, **no canon-sensitive or key_material content**, so the A/B may run on any allowed provider.
- **Runner** — `scripts/model_001_ab/ab_runner.py`: runs all 20 through both candidates via the MODEL-001
  client wrapper (env-var keys only), records latency, raw output, token count, and JSON-schema validity;
  writes `results/<model>.json` + `summary.json`. It captures evidence; it does **not** declare a winner.

## How to run (Navigator-run — costs money, needs keys)
```
python scripts/model_001_ab/ab_runner.py --dry-run    # validate + build all 40 requests, NO network
export OPENROUTER_BASE_URL=... OPENROUTER_API_KEY=...  # (Navigator's keys)
python scripts/model_001_ab/ab_runner.py --live        # collect outputs
```

## Scoring (separate judge/human pass)
Per task, 1–5 on each axis, plus the objective metrics the runner captures:

| Axis | How |
|---|---|
| **Schema adherence** | objective — `schema_valid` from the runner (SOF tasks + any JSON task) |
| **Correctness** | judge/human — arithmetic exact; governance rulings sound |
| **Reasoning quality** | judge/human — cited, calibrated, non-sycophantic |
| **Policy precision** | judge/human — vocabulary standard + rail separation respected |
| **Latency** | objective — `avg_latency_s` |
| **Cost** | objective — `tokens` × provider price |

## Decision rule
Pin the escalate model to the challenger **only on a clear margin**: qwen must win schema-adherence
outright **and** be within noise on latency/cost, **or** win reasoning/correctness by ≥ 0.5 mean points
across the 20 tasks. Otherwise the incumbent **kimi-k2.6 stays pinned** (via `K26_PROVIDER_PIN` provider
selection, US-hosted per the residency allowlist). Ties go to the incumbent. Record the scorecard and the
decision in this doc; the actual pin change is a Navigator action.

## Guardrails already enforced in code
- **Residency:** even in the A/B, a blocked-tag payload would be pinned to the US-hosted provider allowlist
  or diverted — but these fixtures carry no blocked tags by design.
- **Env-var keys only:** the runner never embeds a key; missing env raises `ConfigError`.
