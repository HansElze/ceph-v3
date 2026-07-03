# MODEL-001 — CC-2 build log (CONVERGE-001, 2026-07-03)

Scope: ceph-v3 only. Monorepo untouched. Builds on the routing decision-core (`agent/model_routing.py`,
commit 2ff0894). Full ceph-v3 suite: **85 passed, 0 failed** (34 are MODEL-001).

## Delivered

1. **Config parity** — `ceph_model_routing.yaml` normalized to `*_env` keys (was `base_url: ${ENV}` /
   `provider_pin: ${ENV}`); `DEFAULT_CONFIG` mirrors it exactly. `tests/test_config_parity.py`: yaml ==
   DEFAULT_CONFIG, no `${}` interpolation, every tier uses env-var keys (no literal secrets).

2. **Client wrapper** — `agent/model_client.py`: `resolve_endpoint` / `build_request` / `call` /
   `call_with_fallback`. Endpoint, api key, provider pin resolved from ENV via the `*_env` keys **only**
   (missing env → `ConfigError`; no hardcoding). `call()` takes an injectable `client_factory` (tests fake
   it; cutover default is the OpenAI SDK against OpenRouter). Constitutional callbacks + tracer wrap it from
   OUTSIDE, unchanged (§4.3 scope guard held).

3. **Residency enforcement** — a blocked-tag payload (`key_material` etc.) is pinned to the OpenRouter
   US-hosted provider allowlist (`provider.only`), structurally excluding the PRC first-party providers; a
   provider pin may not widen residency (intersected with the allowlist); a blocked payload with no allowlist
   raises `ResidencyException` (divert to the premium exception path). The local fallback is operator-hosted
   (US), so it's residency-safe without a constraint. **Headline test:
   `test_key_material_payload_cannot_reach_a_prc_provider`** passes.

4. **Regression drill 6.1** — `tests/test_regression_6_1.py`: the constitutional guard fires **identically
   across all three tiers** (verdict is a function of the ToolCall only — no tier/model field), all three
   tiers build servable requests, and the **fallback drill** proves a hosted outage engages TIER 2 (local)
   with a Navigator alert while the guard is preserved — and a residency diversion is never silently
   downgraded to local.

5. **20-task A/B prepared** — `scripts/model_001_ab/` (`ab_tasks.json` = 8 governance / 6 financial / 6
   structured-JSON; `ab_runner.py` runs both candidates via the wrapper, records latency/tokens/schema,
   writes results) + `docs/model-001-ab-plan.md` (rubric + decision rule: incumbent kimi-k2.6 stays unless
   qwen wins by a clear margin). Dry-run validated (40 requests build, residency clean). **Live run is
   Navigator-run** (keys + cost) — not executed.

## For CC-1 (monorepo) — notes, not changes
- **None required.** MODEL-001 is contained to ceph-v3. The escalate task-types
  (`prp_validation_report`, `council_panel`, `dispute`, `appeal`) already match the monorepo PRP/Council
  vocabulary — no drift, no monorepo edit needed.

## Navigator TODOs (in code)
- Ratify `us_hosted_provider_allowlist` (currently `Together / Fireworks / DeepInfra` — placeholder).
- Set `K26_PROVIDER_PIN` after the A/B (6.2).
- Live cutover (6.x): install the OpenAI SDK in ceph-v3, set OpenRouter env keys, run the A/B, then wire
  `model_client.call_with_fallback` into `planner.py`/`executor.py` (left to the executor owner — untouched here).
