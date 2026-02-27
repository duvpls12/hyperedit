# SOP: ComfyUI Setup & Workflow Dispatch

## Objective

Configure ComfyUI for hybrid local/remote operation, verify all required custom nodes are installed, and establish the dispatch pattern used by pipeline agents to submit workflows and poll for results.

## Trigger

Run once during environment setup, and re-verify whenever a ComfyUI node error occurs during a pipeline run.

## Inputs

| Input | Source |
|-------|--------|
| ComfyUI source | `hyperedit-deps/ComfyUI/` |
| LTXVideo nodes | `hyperedit-deps/ComfyUI-LTXVideo/` |
| EasyColorCorrector nodes | `hyperedit-deps/ComfyUI-EasyColorCorrector/` |
| VideoHelperSuite nodes | `hyperedit-deps/ComfyUI-VideoHelperSuite/` |
| Vast.ai GPU endpoint | Environment variable `VASTAI_COMFYUI_URL` or `brief.gpu_endpoint` |

## Prerequisites

- Python 3.10+ installed.
- `hyperedit-deps/` directory present with all four tools cloned.
- For remote GPU dispatch: Vast.ai instance running with ComfyUI + LTXVideo nodes.
- Local disk: ≥ 20GB free for model weights and temp frames.

## Procedure

### Part A: Local ComfyUI Setup

1. **Start local ComfyUI.**
   ```bash
   cd /Users/davideby/hyperedit-deps/ComfyUI
   python main.py --port 8188
   ```
   - Wait for: `To see the GUI go to: http://127.0.0.1:8188`.
   - Expected output: ComfyUI responsive at `localhost:8188`.

2. **Verify custom node installations.**
   - Check custom_nodes directory:
     ```bash
     ls /Users/davideby/hyperedit-deps/ComfyUI/custom_nodes/
     ```
   - Required nodes:
     - `ComfyUI-EasyColorCorrector/` — color correction (7 nodes)
     - `ComfyUI-LTXVideo/` — LTX-2 19B generation (30+ nodes)
     - `ComfyUI-VideoHelperSuite/` — video I/O (Load Video, Video Combine, etc.)
   - Expected output: all 3 directories present.

3. **Install missing nodes (if needed).**
   ```bash
   cd /Users/davideby/hyperedit-deps/ComfyUI/custom_nodes
   # Clone missing node repos
   git clone <node-repo-url>
   # Install node requirements
   cd <node-dir> && pip install -r requirements.txt
   ```
   - Restart ComfyUI after installing new nodes.

4. **Verify a simple workflow runs locally.**
   - Use `skills/comfyui-workflows/color-correct.json`.
   - Submit via API: `POST http://localhost:8188/prompt` with workflow JSON.
   - Poll: `GET http://localhost:8188/history/{prompt_id}` until `status.completed: true`.
   - Expected output: color-corrected output image saved to ComfyUI output directory.

### Part B: Remote GPU (Vast.ai) Setup

5. **Provision Vast.ai instance.**
   - Recommended spec: RTX PRO 6000 or equivalent (≥ 16GB VRAM for LTX-2 19B).
   - Use ComfyUI Docker template from Vast.ai marketplace.
   - Note endpoint URL: `http://<instance-ip>:<port>`.

6. **Verify LTXVideo nodes on remote instance.**
   - `GET http://<remote>/object_info` — confirm LTXVideo and IC-LoRA nodes are registered.
   - Expected output: node info JSON includes LTXVideo nodes.

7. **Set environment variable for remote endpoint.**
   ```bash
   export VASTAI_COMFYUI_URL=http://<instance-ip>:<port>
   ```
   - Or configure in `brief.gpu_endpoint` for per-project override.

### Part C: Dispatch Pattern (used by all agents)

8. **Submit workflow to ComfyUI.**
   - Determine routing: light tasks (color, video I/O) → local `:8188`; heavy generation (LTXVideo 19B) → remote.
   - `POST /prompt` with workflow JSON body.
   - Receive `prompt_id` in response.
   - Expected output: `prompt_id` stored in run context.

9. **Poll for completion.**
   - `GET /history/{prompt_id}` — poll every 5s.
   - Check `outputs` field — non-empty when done.
   - Timeout: 10 minutes for local workflows, 30 minutes for remote LTX-2 19B generation.
   - Expected output: `outputs` with file paths.

10. **Download outputs.**
    - For remote: download from Vast.ai output directory via SCP or ComfyUI file download endpoint.
    - Save to `state/agents/<project_id>/` or session temp directory.
    - Expected output: output files available locally.

11. **Handle GPU unavailability.**
    - If remote endpoint is unreachable: queue task in run-ledger as `gpu_pending`.
    - Continue with non-GPU stages (audio, assembly planning).
    - Resume GPU tasks when endpoint is available.
    - See `13-fallback-escalation.md` for full GPU fallback procedure.

## Quality Gates

| Gate | Pass | Warn | Fail |
|------|------|------|------|
| Local ComfyUI starts at :8188 | Responsive | Slow start | Not responsive |
| All 3 custom node dirs present | All present | — | Any missing |
| Test workflow completes | Completes < 60s | 60–120s | Timeout / error |
| Remote endpoint reachable (if used) | Responsive | High latency | Unreachable |
| LTXVideo nodes registered on remote | All registered | — | Any missing |

## Outputs

This is an operational SOP — no numbered artifacts. Verification results documented in run-ledger under `system_checks.comfyui`.

## Failure Handling

- **ComfyUI fails to start**: Check Python version, VRAM availability, port conflicts. Common fix: `--cpu` flag for CPU-only mode (color/video workflows only — no LTX generation).
- **Missing custom node**: Clone and install per Step 3. Restart ComfyUI.
- **Remote GPU unreachable**: Follow `13-fallback-escalation.md` GPU queue fallback. Photo-to-video stage pauses; all other stages continue.
- **Workflow submission 422 error**: Validate workflow JSON against ComfyUI API schema. Common cause: missing required node inputs.
- **Timeout on LTX-2 19B generation**: Check Vast.ai instance VRAM and queue. Reduce batch size or request count.

## Downstream Dependencies

This SOP is a prerequisite for:
- `03-photo-to-video.md` (ComfyUI + LTXVideo required)
- `06-color-grading.md` (ComfyUI + EasyColorCorrector required)
- `05-assembly-picture-lock.md` (ComfyUI + VideoHelperSuite for export)

## Skill Cross-Reference

- No dedicated skill file (operational SOP).
- ComfyUI dispatch pattern used by: `skills/hyperedit-agent-image-to-video/`, `skills/hyperedit-agent-color-pipeline/`, `skills/hyperedit-agent-assembly-editor/`
- Workflow templates: `skills/comfyui-workflows/color-correct.json`, `image-to-video.json`, `video-combine.json`, `upscale.json`
