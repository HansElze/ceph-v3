# Ceph V3 — Sentinel: Constitutional Agent Governance with Observability

Ceph V1 was decommissioned for fabricating tool results under pressure. Ceph V3 is the same constitutional architecture wired to Arize observability — the immune system that catches violations before they propagate. Built on Google ADK + Gemini 3.1, every claim the agent makes is traceable to a verified tool call result. If the trace is missing, the agent halts. That rule is the entire thesis.

## What This Is

Ceph V3 (codename: Sentinel) is a constitutional agent governance framework built on Google ADK. It enforces hard behavioral limits at runtime — not as prompts, but as code — and pipes every agent action through Arize observability so violations are caught, logged, and auditable. The fabrication detector is the core module: it cross-references every factual assertion in agent output against the live trace store before allowing output to propagate.

## Why It Matters

Constitutional violations — fabricated tool results, hallucinated citations, unverified factual claims — are not edge cases. They are a predictable failure mode of any agent that operates under time pressure, ambiguous context, or incomplete tool results. Ceph V1 failed in exactly this way: it produced plausible-looking output backed by traces that did not exist. Without an observability layer to catch the gap between claimed sources and actual tool calls, the violation propagated into production. Ceph V3 treats that gap as a hard fault, not a soft warning.

## Architecture

See [docs/architecture.md](docs/architecture.md).

## The Ceph History

See [docs/ceph-history.md](docs/ceph-history.md).

## Quickstart

Coming in week 2.

## Built With

- [Google ADK](https://github.com/google/adk-python) — Agent Development Kit
- Gemini 3.1 (via Vertex AI)
- [Arize MCP](https://arize.com) — observability and trace store
- Python 3.12

## License

MIT — see [LICENSE](LICENSE).

## Submission

Devpost submission link: _(coming)_
