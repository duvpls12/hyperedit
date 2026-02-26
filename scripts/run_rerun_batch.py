#!/usr/bin/env python3
"""
GPU Re-Run Batch Script
Target: 4x NVIDIA RTX PRO 6000 Blackwell Server Edition
Model: qwen2.5vl:32b via Ollama (localhost:11434)
Purpose: Re-analyze 62 bad/404-poisoned videos

Run on Vast.ai instance:
  pip install -q librosa yt-dlp
  python3 /workspace/run_rerun_batch.py

VRAM note: 4x 96GB = 384GB total. qwen2.5vl:32b needs ~70GB in 4-bit.
Use: OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1

Results written to: /workspace/results/<video_id>/
Sync back: rsync -avz root@ssh.vast.ai:/workspace/results/ state/final-analysis/
"""

import os, json, re, time, subprocess, concurrent.futures, requests
from pathlib import Path
from datetime import datetime

# ─── CONFIG ───────────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434"
MODEL        = "qwen2.5vl:32b"
DISK_CAP_GB  = 31
FPS          = 5
MAX_RES      = 720
PASS1_WORKERS = 4          # concurrent frame workers (reduce if OOM)
PASS1_NUM_PREDICT = 300
PASS2_NUM_PREDICT = 1400
NUM_CTX      = 4096
PASS2_FRAMES = 40
TIMEOUT_PASS1 = 60
TIMEOUT_PASS2 = 360
TIMEOUT_AUDIO = 300

RESULTS_DIR = Path("/workspace/results")
FRAMES_TMP  = Path("/workspace/tmp_frames")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_TMP.mkdir(parents=True, exist_ok=True)

# ─── VIDEO TARGETS ────────────────────────────────────────────────────────────
# Vimeo targets (video_id, vimeo_id)
VIMEO_TARGETS = [
    ("2023-03-26__811765311__MLS_Video_Example", "811765311"),
    ("2023-08-15__854652905__Cinematic_Property_Tour_240_N_Ocean", "854652905"),
    ("2023-10-13__873941164__7_Oaks_Cinematic", "873941164"),
    ("2023-11-07__882289383__MLS_Video", "882289383"),
    ("2024-04-08__932077011__Chad_Carroll_-_Jade_Signature_Cinematic", "932077011"),
    ("2024-04-19__936713829__Chad_Carroll_-_Main_Cinematic_Video_Website_Banner", "936713829"),
    ("2024-05-24__950051988__John_Foti_-_133_Regatta_Drive_Cinematic", "950051988"),
    ("2024-08-01__993602324__11432_Turtle_Beach_Rd_-_Branded_Cinematic", "993602324"),
    ("2024-09-11__1008551220__Ceci_Sutcliffe_-_991_Greenway_Lane_-_MLS_Horizontal_Cinematic", "1008551220"),
    ("2024-09-23__1012070690__991_Greenway_Lane_-_Cinematic", "1012070690"),
]

# YouTube targets (video_id, youtube_id)
YOUTUBE_TARGETS = [
    ("2024-09-21__FCy7iuamrZ0__CINEMATIC_REAL_ESTATE_TEASER_｜_DAY-NIGHT_TRANSITIONS_｜_SONY_FX3", "FCy7iuamrZ0"),
    ("2024-09-25__2v_7UH_nLv4__CINEMATIC_REAL_ESTATE_VIDEO_｜_MODERN_LUXURY_｜_SONY_FX3_&_DJI_MAVIC_3_PRO", "2v_7UH_nLv4"),
    ("2024-10-05__i0ZtjTdjjX4__CINEMATIC_REAL_ESTATE_VIDEO_｜_SONY_FX3_｜_MAVIC_3_PRO", "i0ZtjTdjjX4"),
    ("2024-11-01__hyKPiC-Uxas__CINEMATIC_REAL_ESTATE_TOUR_｜_SONY_FX3_｜_MAVIC_3_PRO", "hyKPiC-Uxas"),
    ("2025-03-19__3tZiwI4TKSs__CINEMATIC_REAL_ESTATE_TOUR_｜_SONY_FX3_｜_LAOWA_12MM", "3tZiwI4TKSs"),
    ("2025-04-08__DHD9tA9ZYA8__CINEMATIC_REAL_ESTATE_TOUR_｜_SONY_FX3_｜_LAOWA_12MM", "DHD9tA9ZYA8"),
    ("2025-06-04__vwgcKspm868__LUXURY_VILLA_IN_MYKONOS_｜_CINEMATIC_REAL_ESTATE_TOUR_｜_SONY_FX3", "vwgcKspm868"),
    ("2025-07-22___Zg--vAb4A4__Cinematic_Luxury_Real_Estate_Tour_｜_Yorba_Linda_｜_Sony_FX3_+_DJI_Air3S.f251", "_Zg--vAb4A4"),
    ("2025-07-22___Zg--vAb4A4__Cinematic_Luxury_Real_Estate_Tour_｜_Yorba_Linda_｜_Sony_FX3_+_DJI_Air3S.f313", "_Zg--vAb4A4"),
    ("2025-07-22___Zg--vAb4A4__Cinematic_Luxury_Real_Estate_Tour_｜_Yorba_Linda_｜_Sony_FX3_+_DJI_Air3S.temp", "_Zg--vAb4A4"),
    ("2025-07-24__EU4JIX-SIpo__Cinematic_Luxury_Real_Estate_Tour_｜_Newport_Beach_｜_Sony_FX3_+_DJI_Air3S", "EU4JIX-SIpo"),
    ("2025-08-03__rUIGuNCb4bk__Cinematic_Luxury_Real_Estate_Tour_｜_Newport_Coast_｜_Sony_FX3_+_DJI_Air3S", "rUIGuNCb4bk"),
    ("2025-08-07__WzyEyic8L6s__LIFESTYLE_WATERFRONT_CINEMATIC_PROPERTY_TOUR_｜_SONY_FX3", "WzyEyic8L6s"),
    ("2025-08-12__HnnqoAiGJB0__Cinematic_Luxury_Real_Estate_Tour_｜_Coto_De_Caza_｜Sony_FX3_+_DJI_Air3S", "HnnqoAiGJB0"),
    ("2025-08-26__IoQPP3dkJMk__Cinematic_Luxury_Real_Estate_Tour_｜_San_Clemente_｜_Sony_FX3_+_DJI_Air3S", "IoQPP3dkJMk"),
    ("2025-08-31__BcijjibFeWY__Cinematic_Luxury_Real_Estate_Tour_｜_Costa_Mesa_｜_Sony_FX3_+_DJI_Air3S", "BcijjibFeWY"),
    ("2025-10-07__VDALsBYdkHU__Cinematic_Luxury_Real_Estate_Tour_｜_Costa_Mesa_｜_Sony_FX3_+_DJI_Air3S", "VDALsBYdkHU"),
    ("2025-11-05__tbmrwMBSgjg__Cinematic_Luxury_Real_Estate_Tour_｜_San_Diego_｜_Sony_FX3", "tbmrwMBSgjg"),
    ("2025-11-22__GiH59SmOpQo__Cinematic_Luxury_Real_Estate_Tour_｜_Dana_Point_｜_Sony_FX3_+_DJI_Air3S", "GiH59SmOpQo"),
    ("2025-11-26__tS4aUpTm2EE__CINEMATIC_REAL_ESTATE_VIDEO_｜_SONY_FX3", "tS4aUpTm2EE"),
    ("2025-12-03__pSfPTCRlQz4__Cinematic_Luxury_Real_Estate_Tour_｜_Newport_Beach_｜_Sony_FX3_+_DJI_Air3S", "pSfPTCRlQz4"),
    ("2025-12-07__9GvjJmgrxQ4__Cinematic_Luxury_Real_Estate_Tour_｜_Laguna_Beach_｜_Sony_FX3_+_DJI_Air3S", "9GvjJmgrxQ4"),
    ("2026-01-05__VQW8wcoqazs__Cinematic_Luxury_Real_Estate_Tour_｜_Dana_Point_｜_Sony_FX3_+_DJI_Air3S", "VQW8wcoqazs"),
    ("2026-01-12__iR3GjVl_DqQ__Cinematic_Luxury_Real_Estate_Tour_｜_Laguna_Beach_｜_Sony_FX3_+_DJI_Air3S.f251", "iR3GjVl_DqQ"),
    ("2026-01-12__iR3GjVl_DqQ__Cinematic_Luxury_Real_Estate_Tour_｜_Laguna_Beach_｜_Sony_FX3_+_DJI_Air3S", "iR3GjVl_DqQ"),
    ("2026-02-01__YNcDRCnyZfs__CINEMATIC_FITNESS_AD_SHOT_ON_SONY_FX3", "YNcDRCnyZfs"),
]

# ─── PREFLIGHT ────────────────────────────────────────────────────────────────
def check_ollama():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        tags = [m["name"] for m in r.json().get("models", [])]
        if MODEL in tags:
            print(f"✓ {MODEL} ready")
            return True
        print(f"✗ {MODEL} not found. Pulling...")
        subprocess.run(["ollama", "pull", MODEL], check=True)
        return True
    except Exception as e:
        print(f"✗ Ollama not reachable: {e}")
        return False

def disk_usage_gb():
    result = subprocess.run(["du", "-sb", "/workspace"], capture_output=True, text=True)
    bytes_used = int(result.stdout.split()[0])
    return bytes_used / 1e9

def check_disk():
    gb = disk_usage_gb()
    print(f"  Disk: {gb:.1f}GB / {DISK_CAP_GB}GB")
    return gb < DISK_CAP_GB

# ─── DOWNLOAD ─────────────────────────────────────────────────────────────────
def download_vimeo(video_id, vimeo_id, out_dir):
    out_path = out_dir / f"{video_id}.mp4"
    if out_path.exists():
        return out_path
    url = f"https://vimeo.com/{vimeo_id}"
    cmd = ["yt-dlp", "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
           "--merge-output-format", "mp4", "-o", str(out_path), url]
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {r.stderr.decode()[:200]}")
    return out_path

def download_youtube(video_id, yt_id, out_dir):
    out_path = out_dir / f"{video_id}.mp4"
    if out_path.exists():
        return out_path
    url = f"https://www.youtube.com/watch?v={yt_id}"
    cmd = ["yt-dlp", "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
           "--merge-output-format", "mp4", "-o", str(out_path), url]
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {r.stderr.decode()[:200]}")
    return out_path

# ─── FRAME EXTRACTION ─────────────────────────────────────────────────────────
def extract_frames(video_path, frames_dir, fps=FPS, max_res=MAX_RES):
    frames_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"fps={fps},scale='if(gt(iw\,ih)\,{max_res}\,-2)':'if(gt(iw\,ih)\,-2\,{max_res})'",
        "-q:v", "3",
        str(frames_dir / "f_%06d.jpg"),
        "-y", "-loglevel", "error"
    ]
    subprocess.run(cmd, check=True, timeout=300)
    return sorted(frames_dir.glob("f_*.jpg"))

def get_video_duration(video_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return float(r.stdout.strip())

# ─── OLLAMA INFERENCE ─────────────────────────────────────────────────────────
import base64

def image_to_b64(path):
    return base64.b64encode(path.read_bytes()).decode()

PASS1_PROMPT = """Analyze this real estate video frame. Return ONLY valid JSON, no markdown fences.
{
  "shot_type": "wide_establishing|exterior|interior|aerial_oblique|aerial_overhead|panoramic|medium|close-up|detail_insert|title_card|static|pan|landscape|still",
  "room_or_amenity": "living room|bedroom|bathroom|kitchen|dining room|outdoor|patio|pool|balcony|garage|staircase|entrance|closet|none",
  "typography_present": true or false,
  "composition": "wide|symmetrical|depth_layering|rule_of_thirds|centered|panoramic|asymmetrical|landscape",
  "color_grade": "neutral|natural|warm|vivid|saturated|dark|warm_neutral|bright|black and white",
  "camera_movement": "static|horizontal|pan|panning|drone_flyover|gimbal_walk_forward|tilt|none",
  "sequence_role": "intro_hook|introductory|room_showcase|establishing|overview|detail|background|transition"
}"""

PASS2_PROMPT = """You are analyzing a real estate property video. I am providing {n_frames} evenly sampled frames.

Analyze the full temporal arc and return ONLY valid JSON (no markdown), with this structure:
{{
  "narrative_arc": "string describing the video story arc",
  "pacing": "slow_cinematic|mixed|fast_dynamic",
  "dominant_camera_movement": "static|pan|drone|mixed",
  "space_coverage": ["list of rooms/areas shown"],
  "hook_quality": "strong|medium|weak",
  "signature_shots": ["describe 3-5 standout shots"],
  "editorial_notes": "key observations for editing",
  "estimated_property_type": "luxury|mid-market|budget",
  "estimated_price_tier": "$1M+|$500k-1M|under $500k"
}}"""

def ollama_vision(prompt, image_paths, num_predict, timeout):
    messages = [{"role": "user", "content": []}]
    for ip in image_paths:
        messages[0]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_to_b64(ip)}"}})
    messages[0]["content"].append({"type": "text", "text": prompt})

    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"num_ctx": NUM_CTX, "num_predict": num_predict, "temperature": 0.1},
    }
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()["message"]["content"]

def parse_llm_json(text):
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"```\s*$", "", text.strip())
    return json.loads(text)

# ─── PASS 1 ───────────────────────────────────────────────────────────────────
def run_pass1(video_id, frame_paths):
    results = [None] * len(frame_paths)
    fps = FPS

    def analyze_frame(args):
        idx, fp = args
        try:
            t = idx / fps
            raw = ollama_vision(PASS1_PROMPT, [fp], PASS1_NUM_PREDICT, TIMEOUT_PASS1)
            analysis = parse_llm_json(raw)
            return idx, {"frame_index": idx, "t": t, "frame": fp.name, "analysis": analysis}
        except Exception as e:
            return idx, {"frame_index": idx, "t": idx/fps, "frame": fp.name, "analysis": {"error": str(e)}}

    with concurrent.futures.ThreadPoolExecutor(max_workers=PASS1_WORKERS) as ex:
        futures = {ex.submit(analyze_frame, (i, fp)): i for i, fp in enumerate(frame_paths)}
        for fut in concurrent.futures.as_completed(futures):
            idx, result = fut.result()
            results[idx] = result
            if idx % 20 == 0:
                print(f"    pass1 frame {idx}/{len(frame_paths)}")

    return {
        "video": video_id,
        "fps": fps,
        "frames_total": len(frame_paths),
        "vision_model_used": MODEL,
        "per_frame": results,
    }

# ─── PASS 2 ───────────────────────────────────────────────────────────────────
def run_pass2(video_id, frame_paths):
    n = PASS2_FRAMES
    step = max(1, len(frame_paths) // n)
    sampled = frame_paths[::step][:n]
    prompt = PASS2_PROMPT.format(n_frames=len(sampled))
    try:
        raw = ollama_vision(prompt, sampled, PASS2_NUM_PREDICT, TIMEOUT_PASS2)
        analysis = parse_llm_json(raw)
        return {"video_id": video_id, "model": MODEL, "pass": "pass2_temporal", "synthesis_complete": True, **analysis}
    except Exception as e:
        return {"video_id": video_id, "model": MODEL, "pass": "pass2_temporal", "synthesis_complete": False, "error": str(e)}

# ─── AUDIO ────────────────────────────────────────────────────────────────────
def run_audio_dsp(video_id, video_path, results_dir):
    try:
        import librosa, numpy as np
        audio_path = results_dir / f"{video_id}_audio.wav"
        subprocess.run(["ffmpeg", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le",
                        "-ar", "22050", "-ac", "1", str(audio_path), "-y", "-loglevel", "error"], check=True, timeout=120)
        y, sr = librosa.load(str(audio_path), sr=22050)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time").tolist()
        beat_times = librosa.frames_to_time(beats, sr=sr).tolist()
        rms = librosa.feature.rms(y=y, frame_length=sr, hop_length=sr)[0]
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=sr)[0]
        energy_curve = [{"t": float(i), "rms": float(r)} for i, r in enumerate(rms)]
        brightness = [{"t": float(i), "centroid_hz": float(c)} for i, c in enumerate(centroid)]
        dsp = {
            "video_id": video_id,
            "bpm": float(tempo),
            "beats": beat_times,
            "onsets": onsets,
            "energy_curve": energy_curve,
            "spectral_brightness": brightness,
        }
        audio_path.unlink(missing_ok=True)
        return dsp
    except Exception as e:
        return {"video_id": video_id, "audio_dsp_available": False, "error": str(e)}

# ─── FINAL SYNTHESIS ──────────────────────────────────────────────────────────
def write_synthesis(video_id, pass1, pass2, dsp, results_dir):
    pf = pass1.get("per_frame", [])
    good = [f for f in pf if isinstance(f.get("analysis"), dict) and "error" not in f.get("analysis", {})]
    n = len(good)
    from collections import Counter
    rooms = Counter()
    movements = Counter()
    roles = Counter()
    typo = 0
    for f in good:
        a = f["analysis"]
        rooms[(a.get("room_or_amenity") or "unknown").lower()] += 1
        movements[(a.get("camera_movement") or "unknown").lower()] += 1
        roles[(a.get("sequence_role") or "unknown").lower()] += 1
        if a.get("typography_present"):
            typo += 1

    bpm = dsp.get("bpm", "N/A")
    md = f"""# Final Synthesis — {video_id}

## Core Metrics
- Frames analyzed: **{n}** / {len(pf)} @ {FPS} fps
- Typography: **{typo}/{n} frames** ({typo/n*100:.1f}% if n else 0)
- Model: **{MODEL}** (Ollama, qwen2.5vl:32b)

## Pass 2 Summary
- Narrative arc: {pass2.get("narrative_arc", "N/A")}
- Pacing: {pass2.get("pacing", "N/A")}
- Hook quality: {pass2.get("hook_quality", "N/A")}
- Property type: {pass2.get("estimated_property_type", "N/A")}
- Price tier: {pass2.get("estimated_price_tier", "N/A")}
- Space coverage: {", ".join(pass2.get("space_coverage", []))}

## Room Coverage
{chr(10).join(f"- {k}: {v} frames" for k, v in rooms.most_common(10))}

## Camera Movement
{chr(10).join(f"- {k}: {v} frames" for k, v in movements.most_common(8))}

## Sequence Roles
{chr(10).join(f"- {k}: {v} frames" for k, v in roles.most_common(8))}

## Audio DSP
- BPM: {bpm}
- DSP available: {dsp.get("audio_dsp_available", True)}

## Editorial Notes
{pass2.get("editorial_notes", "N/A")}
"""
    (results_dir / f"{video_id}_final_synthesis.md").write_text(md)

# ─── CLEANUP ──────────────────────────────────────────────────────────────────
def cleanup(video_path, frames_dir):
    if video_path and video_path.exists():
        video_path.unlink()
    if frames_dir and frames_dir.exists():
        import shutil
        shutil.rmtree(frames_dir, ignore_errors=True)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def process_video(video_id, download_fn, results_dir):
    vdir = results_dir / video_id
    vdir.mkdir(parents=True, exist_ok=True)
    fdir = FRAMES_TMP / video_id
    video_path = None

    print(f"\n{'='*60}\n  {video_id}\n{'='*60}")
    try:
        if not check_disk():
            print("  ✗ DISK FULL — skipping")
            return False

        print("  Downloading...")
        video_path = download_fn(vdir)
        print(f"  Downloaded: {video_path.stat().st_size / 1e6:.1f}MB")

        print("  Extracting frames...")
        frame_paths = extract_frames(video_path, fdir)
        print(f"  Extracted: {len(frame_paths)} frames")

        print("  Pass 1 (per-frame)...")
        pass1 = run_pass1(video_id, frame_paths)
        (vdir / f"{video_id}_vision_pass1.json").write_text(json.dumps(pass1, indent=2))
        print(f"  Pass 1 done: {len(pass1["per_frame"])} frames")

        print("  Pass 2 (temporal synthesis)...")
        pass2 = run_pass2(video_id, frame_paths)
        (vdir / f"{video_id}_vision_pass2_temporal.json").write_text(json.dumps(pass2, indent=2))
        print(f"  Pass 2 done: {pass2.get('synthesis_complete', False)}")

        print("  Audio DSP...")
        dsp = run_audio_dsp(video_id, video_path, vdir)
        (vdir / f"{video_id}_audio_dsp.json").write_text(json.dumps(dsp, indent=2))
        print(f"  Audio done: BPM={dsp.get('bpm', 'N/A')}")

        print("  Writing synthesis...")
        write_synthesis(video_id, pass1, pass2, dsp, vdir)
        print("  ✓ COMPLETE")
        return True

    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        (vdir / "error.log").write_text(str(e))
        return False
    finally:
        print("  Cleaning up...")
        cleanup(video_path, fdir)

def main():
    print("\n🚀 GPU Re-Run Batch Processor")
    print(f"   Model: {MODEL}")
    print(f"   Disk cap: {DISK_CAP_GB}GB")
    print(f"   Targets: {len(VIMEO_TARGETS) + len(YOUTUBE_TARGETS)} videos")

    if not check_ollama():
        print("✗ Ollama not ready. Exiting.")
        return

    done = 0
    failed = 0

    for video_id, vimeo_id in VIMEO_TARGETS:
        fn = lambda d, vid=video_id, vmid=vimeo_id: download_vimeo(vid, vmid, d)
        ok = process_video(video_id, fn, RESULTS_DIR)
        if ok: done += 1
        else: failed += 1

    for video_id, yt_id in YOUTUBE_TARGETS:
        fn = lambda d, vid=video_id, ytid=yt_id: download_youtube(vid, ytid, d)
        ok = process_video(video_id, fn, RESULTS_DIR)
        if ok: done += 1
        else: failed += 1

    print(f"\n{'='*60}")
    print(f"DONE: {done} succeeded, {failed} failed")
    print(f"Results: {RESULTS_DIR}")
    print(f"Disk usage: {disk_usage_gb():.1f}GB")

if __name__ == "__main__":
    main()
