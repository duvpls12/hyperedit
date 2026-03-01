# HEARTBEAT.md — hyperedit

## Every heartbeat
1. Check newest pipeline run state.
2. If failed/stalled, report blocker + one next fix action.
3. If healthy, return HEARTBEAT_OK.
4. Verify grading/RAG queue health when applicable.


## Metacognition & self-improvement (hourly)
- Run a 30–60s reflection: what went well, what failed, what to improve next.
- If an improvement is found, add one concise line to MEMORY.md (Lessons learned) or open a blocker.
- If nothing to improve, no-op.
