# HyperEdit Deterministic Execution Contract Template

Use this contract block in agent prompts to enforce bounded, deterministic runs and avoid stalls/freezes.

## Project Context
- Repo:
- Worktree path:
- Objective:
- Constraints:

## Task (Single Scope)
- One concrete task only:
- Explicit non-goals:

## Files allowed
- 

## Definition of done
- Required edits completed:
- Validation command(s) pass:
- Local commit created:

## Validation commands
```bash
# Example
rg -n "Project Context|Files allowed|Do NOT push|BLOCKED:|DONE:" <file1> <file2>
```

## Output format
- BLOCKED: <reason>
- DONE: files changed + validation output + commit hash

## Git rule
- Do NOT push.
- Commit locally only.
