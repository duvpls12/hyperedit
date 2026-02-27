#!/usr/bin/env python3
"""
GPU-side shot classifier for HyperEdit.
Runs on Vast.ai — extracts frames + classifies via local Ollama.

Usage (called remotely via SSH):
  python3 /workspace/gpu-classify.py /tmp/clip.mp4
  python3 /workspace/gpu-classify.py /tmp/clip.mp4 --fps 5 --res 720 --model qwen2.5vl:7b

Returns JSON to stdout. All logs go to stderr.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

OLLAMA_URL = "http://localhost:11434"

PASS1_PROMPT = """You are a real estate video shot classifier. Analyze this frame from a property listing video.

Return STRICT JSON only (no markdown, no commentary):
{"primary":"wide|tight|detail|drone|agent-on-camera","sub":"establishing|low-angle|high-angle|eye-level|close-up|medium-close-up|hardware|fixture|texture|architectural|landscape|aerial-wide|aerial-orbit|aerial-reveal|aerial-tracking|talking-head|walk-through|stand-up","location":"interior|exterior","room":"kitchen|bathroom|bedroom|living|dining|office|garage|pool|yard|hallway|foyer|patio|balcony|exterior|unknown","lighting":"natural|artificial|mixed|golden-hour","confidence":0.0}"""

PASS2_PROMPT = """You are an expert cinematographer analyzing a FULL RESOLUTION frame from a real estate listing video.

Return STRICT JSON only:
{"primary":"wide|tight|detail|drone|agent-on-camera","sub":"establishing|low-angle|high-angle|eye-level|close-up|medium-close-up|hardware|fixture|texture|architectural|landscape|aerial-wide|aerial-orbit|aerial-reveal|aerial-tracking|talking-head|walk-through|stand-up","location":"interior|exterior","room":"kitchen|bathroom|bedroom|living|dining|office|garage|pool|yard|hallway|foyer|patio|balcony|exterior|unknown","lighting":"natural|artificial|mixed|golden-hour","color_notes":"describe: flat/desaturated (log), normal contrast (rec709), or stylized?","quality_flags":["sharp|soft","well-exposed|over-exposed|under-exposed"],"confidence":0.0}"""


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def get_duration(video_path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_entries", "format=duration", str(video_path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0


def extract_frames(video_path, out_dir, fps=5, max_res=720):
    """Extract low-res frames at given FPS. Returns list of frame paths."""
    scale = f"'if(gt(iw\\,ih)\\,{max_res}\\,-2)':'if(gt(iw\\,ih)\\,-2\\,{max_res})'"
    cmd = [
        "ffmpeg", "-hwaccel", "auto", "-i", str(video_path),
        "-vf", f"fps={fps},scale={scale}",
        "-q:v", "3",
        str(Path(out_dir) / "f_%06d.jpg"),
        "-y", "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True, timeout=300)
    frames = sorted(Path(out_dir).glob("f_*.jpg"))
    return frames


def extract_fullres_frame(video_path, out_path, duration):
    """Extract single full-res frame at midpoint."""
    mid = duration / 2
    cmd = [
        "ffmpeg", "-hwaccel", "auto", "-ss", f"{mid:.3f}",
        "-i", str(video_path),
        "-frames:v", "1", "-q:v", "2",
        str(out_path), "-y", "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True, timeout=60)


def ollama_vision(prompt, image_path, model):
    """Send image to local Ollama vision model."""
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [b64]}],
            "stream": False,
            "options": {"temperature": 0.1},
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def parse_json(text):
    """Extract JSON from response (handles markdown fences)."""
    import re
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    s = m.group(1).strip() if m else text.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def majority_vote(results):
    """Pick most common classification across frames."""
    counts = {}
    sub_counts = {}
    loc_counts = {}
    room_counts = {}
    light_counts = {}
    total_conf = 0

    for fr in results:
        if not fr:
            continue
        p = fr.get("primary", "")
        if p:
            counts[p] = counts.get(p, 0) + 1
        s = fr.get("sub", "")
        if s:
            sub_counts[s] = sub_counts.get(s, 0) + 1
        loc = fr.get("location", "")
        if loc:
            loc_counts[loc] = loc_counts.get(loc, 0) + 1
        rm = fr.get("room", "")
        if rm:
            room_counts[rm] = room_counts.get(rm, 0) + 1
        lt = fr.get("lighting", "")
        if lt:
            light_counts[lt] = light_counts.get(lt, 0) + 1
        total_conf += fr.get("confidence", 0)

    def pick(d):
        return max(d, key=d.get) if d else "unknown"

    n = len(results) or 1
    return {
        "primary": pick(counts),
        "sub": pick(sub_counts),
        "location": pick(loc_counts),
        "room": pick(room_counts),
        "lighting": pick(light_counts),
        "confidence": round(total_conf / n, 2),
        "frame_count": len(results),
        "vote_distribution": counts,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--fps", type=int, default=5)
    parser.add_argument("--res", type=int, default=720)
    parser.add_argument("--model", default="qwen2.5vl:7b")
    args = parser.parse_args()

    video = Path(args.video)
    if not video.exists():
        log(f"ERROR: {video} not found")
        sys.exit(1)

    log(f"Processing: {video.name}")

    with tempfile.TemporaryDirectory(prefix="hyperedit_") as tmpdir:
        tmpdir = Path(tmpdir)
        frames_dir = tmpdir / "frames"
        frames_dir.mkdir()

        # Duration
        duration = get_duration(video)
        log(f"  duration={duration:.1f}s")

        # Pass 1: low-res 5fps
        log(f"  Pass 1: extracting {args.fps}fps @ {args.res}px...")
        frames = extract_frames(video, frames_dir, args.fps, args.res)
        log(f"  Pass 1: {len(frames)} frames → classifying...")

        frame_results = []
        for i, fp in enumerate(frames):
            try:
                raw = ollama_vision(PASS1_PROMPT, fp, args.model)
                parsed = parse_json(raw)
                frame_results.append(parsed)
            except Exception as e:
                log(f"  frame {i} error: {str(e)[:80]}")
                frame_results.append(None)

        classification = majority_vote([r for r in frame_results if r])
        log(f"  Pass 1: {classification['primary']}/{classification['sub']} (conf={classification['confidence']})")

        # Pass 2: full-res single frame
        fullres_path = tmpdir / "fullres.jpg"
        log("  Pass 2: full-res screenshot...")
        pass2 = None
        try:
            extract_fullres_frame(video, fullres_path, duration)
            raw = ollama_vision(PASS2_PROMPT, fullres_path, args.model)
            pass2 = parse_json(raw)
            if pass2:
                log(f"  Pass 2: {pass2.get('primary')}/{pass2.get('sub')} color=\"{str(pass2.get('color_notes',''))[:60]}\"")
                if (pass2.get("confidence", 0) or 0) > (classification.get("confidence", 0) or 0):
                    classification["primary"] = pass2.get("primary", classification["primary"])
                    classification["sub"] = pass2.get("sub", classification["sub"])
        except Exception as e:
            log(f"  Pass 2 error: {str(e)[:80]}")

    # Output JSON to stdout
    result = {
        "filename": video.name,
        "duration": duration,
        "classification": classification,
        "pass2": pass2,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
