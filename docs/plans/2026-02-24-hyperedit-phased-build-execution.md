# HyperEdit Phased Build + Execution System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish a deterministic, context-rich, terminal-first delivery system for HyperEdit that prevents CLI freeze, preserves durable session continuity, and ships work in phases/waves with local-only commits.

**Architecture:** Add a lightweight execution layer around coding-agent prompts: mission-context templates, bounded task waves, durable run logs, and heartbeat-driven session continuity checks. Implement in small vertical slices so each wave is independently verifiable and recoverable. Keep implementation local-first and avoid `/tmp` for durable state.

**Tech Stack:** Node.js scripts, existing local-ffmpeg server (`scripts/local-ffmpeg-server.js`), Markdown docs, git local commits.

---

### Task 1: Baseline context + constraints lock

**Files:**
- Modify: `CLAUDE.md`
- Create: `docs/plans/hyperedit-execution-contract.md`

**Step 1: Write the failing test/check (manual contract check)**
- Define required contract fields for every coding run:
  - Project Context
  - Task (single-scope)
  - Files allowed
  - Definition of done
  - Validation commands
  - Output format (BLOCKED/DONE)
  - Git local-only rule

**Step 2: Run check to verify missing/partial contract exists today**
Run:
```bash
rg -n "Project Context|Files allowed|Do NOT push|BLOCKED:|DONE:" CLAUDE.md docs/plans/hyperedit-execution-contract.md
```
Expected: FAIL or partial coverage.

**Step 3: Write minimal implementation**
- Add explicit contract section in `CLAUDE.md`.
- Add detailed reusable contract in `docs/plans/hyperedit-execution-contract.md`.

**Step 4: Run check to verify it passes**
Run:
```bash
rg -n "Project Context|Files allowed|Do NOT push|BLOCKED:|DONE:" CLAUDE.md docs/plans/hyperedit-execution-contract.md
```
Expected: PASS with all required sections found.

**Step 5: Commit**
```bash
git add CLAUDE.md docs/plans/hyperedit-execution-contract.md
git commit -m "docs: add deterministic execution contract for HyperEdit agent runs"
```

---

### Task 2: Wave planner (phases + waves)

**Files:**
- Create: `docs/plans/hyperedit-phases-and-waves.md`
- Modify: `TODO.md`

**Step 1: Write failing check**
- Require explicit phase/wave structure:
  - Phase 0: Context + safety rails
  - Phase 1: Durable session foundation
  - Phase 2: Continuity/health instrumentation
  - Phase 3: Workflow fit + operator UX
  - Phase 4: hardening + launch gates

**Step 2: Run check**
```bash
rg -n "Phase 0|Phase 1|Phase 2|Phase 3|Phase 4|Wave" docs/plans/hyperedit-phases-and-waves.md TODO.md
```
Expected: FAIL before file exists.

**Step 3: Implement**
- Add each phase with 2–5 waves, each wave with:
  - objective
  - entry criteria
  - tasks
  - validation
  - rollback
  - local commit checkpoint

**Step 4: Run check**
```bash
rg -n "Phase 0|Phase 1|Phase 2|Phase 3|Phase 4|Wave|Entry criteria|Validation|Rollback|Checkpoint" docs/plans/hyperedit-phases-and-waves.md
```
Expected: PASS.

**Step 5: Commit**
```bash
git add docs/plans/hyperedit-phases-and-waves.md TODO.md
git commit -m "plan: define phased wave execution model for HyperEdit"
```

---

### Task 3: Durable run ledger (anti-compaction memory)

**Files:**
- Create: `state/run-ledger/README.md`
- Create: `state/run-ledger/current.json`
- Create: `scripts/run-ledger.js`

**Step 1: Write failing check**
- Need durable local ledger keys:
  - currentWave
  - lastPrompt
  - lastCommand
  - lastResult
  - nextAction
  - updatedAt

**Step 2: Run check**
```bash
node -e "const fs=require('fs');const p='state/run-ledger/current.json';if(!fs.existsSync(p))process.exit(1);const j=JSON.parse(fs.readFileSync(p));['currentWave','lastPrompt','lastCommand','lastResult','nextAction','updatedAt'].forEach(k=>{if(!(k in j))process.exit(2)});"
```
Expected: FAIL before implementation.

**Step 3: Implement**
- Add script to initialize/update/read ledger with deterministic schema.
- Ensure directory created under repo path (not `/tmp`).

**Step 4: Run check**
```bash
node scripts/run-ledger.js init
node scripts/run-ledger.js status
```
Expected: PASS with valid JSON state.

**Step 5: Commit**
```bash
git add state/run-ledger scripts/run-ledger.js
git commit -m "feat: add durable local run ledger for phased execution continuity"
```

---

### Task 4: Prompt scaffolder for deterministic CLI runs

**Files:**
- Create: `scripts/scaffold-agent-prompt.js`
- Create: `docs/plans/prompt-templates.md`

**Step 1: Write failing check**
- Scaffolder must output all required sections from execution contract.

**Step 2: Run check**
```bash
node scripts/scaffold-agent-prompt.js --task "test" --files "scripts/local-ffmpeg-server.js,CLAUDE.md" > /tmp/prompt.txt
rg -n "Project Context|Task:|Files allowed|Definition of done|Validation|Output format|Do NOT push" /tmp/prompt.txt
```
Expected: FAIL before implementation.

**Step 3: Implement**
- Add CLI that generates prompts from args + ledger context.
- Template includes scope, timebox, blocker exit condition.

**Step 4: Run check**
```bash
node scripts/scaffold-agent-prompt.js --task "durable session status" --files "scripts/local-ffmpeg-server.js,CLAUDE.md" > /tmp/prompt.txt
rg -n "Project Context|BLOCKED:|DONE:|Do NOT push" /tmp/prompt.txt
```
Expected: PASS.

**Step 5: Commit**
```bash
git add scripts/scaffold-agent-prompt.js docs/plans/prompt-templates.md
git commit -m "feat: add deterministic prompt scaffolder for coding CLI runs"
```

---

### Task 5: Session continuity endpoint verification harness

**Files:**
- Modify: `scripts/local-ffmpeg-server.js`
- Create: `scripts/check-session-continuity.js`

**Step 1: Write failing check**
- Verify endpoint contract includes:
  - `dataRoot`
  - `sessionsDir`
  - `activeSessionCount`
  - `staleSessionCount`
  - `staleSessionIds`
  - `checkedAt`

**Step 2: Run check**
```bash
node scripts/check-session-continuity.js
```
Expected: FAIL until endpoint + parser are aligned.

**Step 3: Implement**
- Harden response shape and stale threshold behavior.
- Add checker script for local CI-like validation.

**Step 4: Run check**
```bash
node scripts/check-session-continuity.js
node --check scripts/local-ffmpeg-server.js
```
Expected: PASS.

**Step 5: Commit**
```bash
git add scripts/local-ffmpeg-server.js scripts/check-session-continuity.js
git commit -m "feat: verify session continuity endpoint contract"
```

---

### Task 6: Non-freeze execution wrapper (watchdog)

**Files:**
- Create: `scripts/agent-wave-runner.sh`
- Create: `docs/plans/agent-runner-ops.md`

**Step 1: Write failing check**
- Runner must enforce:
  - max runtime
  - idle-output timeout
  - periodic heartbeat logs
  - auto stop with BLOCKED summary

**Step 2: Run check**
```bash
bash -n scripts/agent-wave-runner.sh
```
Expected: FAIL before script exists.

**Step 3: Implement**
- Add wrapper supporting codex/claude CLI commands.
- Log to `state/run-ledger/runner.log`.

**Step 4: Run check**
```bash
bash -n scripts/agent-wave-runner.sh
```
Expected: PASS.

**Step 5: Commit**
```bash
git add scripts/agent-wave-runner.sh docs/plans/agent-runner-ops.md
git commit -m "feat: add watchdog runner for deterministic agent wave execution"
```

---

### Task 7: Local-only guardrail

**Files:**
- Create: `scripts/git-local-guard.sh`
- Modify: `docs/plans/agent-runner-ops.md`

**Step 1: Write failing check**
- Any automated run must reject `git push`.

**Step 2: Run check**
```bash
bash -n scripts/git-local-guard.sh
```
Expected: FAIL before script exists.

**Step 3: Implement**
- Script verifies local branch state and explicitly blocks push commands in runner flow.

**Step 4: Run check**
```bash
bash -n scripts/git-local-guard.sh
```
Expected: PASS.

**Step 5: Commit**
```bash
git add scripts/git-local-guard.sh docs/plans/agent-runner-ops.md
git commit -m "chore: enforce local-only git workflow for HyperEdit runs"
```

---

### Task 8: Final verification wave

**Files:**
- Modify: `docs/plans/hyperedit-phases-and-waves.md`

**Step 1: Verify all wave artifacts exist**
Run:
```bash
ls -la docs/plans state/run-ledger scripts | cat
```

**Step 2: Verify key scripts parse**
Run:
```bash
node --check scripts/local-ffmpeg-server.js
node --check scripts/run-ledger.js
node --check scripts/scaffold-agent-prompt.js
bash -n scripts/agent-wave-runner.sh
bash -n scripts/git-local-guard.sh
```

**Step 3: Verify continuity endpoint contract**
Run:
```bash
node scripts/check-session-continuity.js
```

**Step 4: Document verification evidence**
- Add command outputs + timestamp to plan file.

**Step 5: Commit**
```bash
git add docs/plans/hyperedit-phases-and-waves.md
git commit -m "chore: record HyperEdit phased execution verification evidence"
```
