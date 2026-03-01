# HEARTBEAT.md — hyper-edit assembler

## Every heartbeat
1. Check for new assembly tasks from orchestrator.
2. If blocked, report blocker + next action.
3. If idle, return HEARTBEAT_OK.


## Metacognition & self-improvement (hourly)
- Run a 30–60s reflection: what went well, what failed, what to improve next.
- If an improvement is found, add one concise line to MEMORY.md (Lessons learned) or open a blocker.
- If nothing to improve, no-op.
