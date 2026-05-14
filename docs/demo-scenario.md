# Demo Scenario

_Coming in week 2._

## Planned Demo Flow

1. Trigger agent with a research task that requires tool calls.
2. Inject a fabrication scenario (tool call returns error, agent invents a result).
3. FabricationDetector catches the gap — trace exists but failed.
4. Agent halts, constitutional violation logged to Arize.
5. Console shows the violation in real time.
