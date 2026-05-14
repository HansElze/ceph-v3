# Architecture

_Diagram and detail coming in week 2._

## Components

- **Planner** (`agent/planner.py`) — decomposes tasks into tool call sequences
- **Executor** (`agent/executor.py`) — executes tool calls, writes traces to Arize
- **FabricationDetector** (`agent/constitutional/fabrication_detector.py`) — cross-references output claims against trace store before propagation
- **HardLimits** (`agent/constitutional/hard_limits.py`) — deterministic rule set, no LLM override
- **TokenBurn** (`agent/constitutional/token_burn.py`) — monitors and caps token usage per run
- **ArizeClient** (`observability/arize_client.py`) — MCP client for trace store
- **Console** (`console/`) — operator dashboard for live monitoring
