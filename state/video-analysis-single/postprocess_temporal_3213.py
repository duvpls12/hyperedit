#!/usr/bin/env python3
import json
import math
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np

ROOT = Path('/Users/davideby/hyperedit/state/video-analysis-single')
INPUT_JSON = ROOT / '3213_CliffDrive_2inst.json'
INPUT_MD = ROOT / '3213_CliffDrive_2inst.md'
FRAMES_DIR = ROOT / 'frames_3213_CliffDrive_2inst'
FPS = 5.0


def read_image_dims(frame_path: Path) -> Tuple[int, int]:
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', str(frame_path)
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    w, h = out.split('x')
    return int(w), int(h)


def load_gray_frames_from_jpg_sequence(pattern: str, width: int, height: int) -> np.ndarray:
    cmd = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error',
        '-framerate', str(int(FPS)), '-i', pattern,
        '-f', 'rawvideo', '-pix_fmt', 'gray', '-'
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
    raw = proc.stdout
    frame_bytes = width * height
    n = len(raw) // frame_bytes
    arr = np.frombuffer(raw[: n * frame_bytes], dtype=np.uint8).reshape((n, height, width))
    return arr


def phase_correlation_shift(a: np.ndarray, b: np.ndarray) -> Tuple[float, float, float]:
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    a -= a.mean()
    b -= b.mean()
    fa = np.fft.fft2(a)
    fb = np.fft.fft2(b)
    cps = fa * np.conj(fb)
    den = np.maximum(np.abs(cps), 1e-9)
    cps /= den
    corr = np.fft.ifft2(cps)
    corr_abs = np.abs(corr)
    y, x = np.unravel_index(np.argmax(corr_abs), corr_abs.shape)
    h, w = a.shape
    if x > w // 2:
        x = x - w
    if y > h // 2:
        y = y - h
    peak = float(corr_abs.max())
    return float(x), float(y), peak


def detect_shot_boundaries(frame_diffs: np.ndarray) -> List[int]:
    if frame_diffs.size == 0:
        return [0]
    med = float(np.median(frame_diffs))
    mad = float(np.median(np.abs(frame_diffs - med))) + 1e-9
    z = (frame_diffs - med) / (1.4826 * mad)
    hard = np.where((z > 4.0) | (frame_diffs > med * 2.4))[0] + 1
    boundaries = [0]
    last = -999
    for b in hard.tolist():
        if b - last >= int(FPS * 1.0):
            boundaries.append(int(b))
            last = b
    return sorted(set(boundaries))


def classify_shot(dx: np.ndarray, dy: np.ndarray, conf: np.ndarray) -> Tuple[str, float]:
    if dx.size == 0:
        return 'static', 0.4
    mag = np.sqrt(dx * dx + dy * dy)
    med_mag = float(np.median(mag))
    consistency = float(np.abs(np.mean(np.exp(1j * np.arctan2(dy + 1e-9, dx + 1e-9)))))
    jitter = float(np.std(np.diff(mag)) if mag.size > 2 else 0.0)
    mx = float(np.median(dx))
    my = float(np.median(dy))
    conf_q = float(np.clip(np.median(conf), 0.0, 1.0))

    if med_mag < 0.55:
        return 'static', round(0.72 * conf_q + 0.18, 3)

    if jitter > 0.9 and consistency < 0.45:
        return 'handheld', round(0.56 * conf_q + 0.25, 3)

    if consistency > 0.72:
        if abs(mx) > abs(my) * 1.45:
            if med_mag > 2.8:
                return 'truck', round(0.48 * conf_q + 0.33, 3)
            return 'pan', round(0.56 * conf_q + 0.3, 3)
        if abs(my) > abs(mx) * 1.45:
            return 'tilt', round(0.58 * conf_q + 0.28, 3)
        if med_mag > 2.4:
            return 'orbit', round(0.42 * conf_q + 0.31, 3)

    # Weak scale proxy from net motion trend (limited inferability)
    trend = float(np.mean(np.diff(mag)) if mag.size > 2 else 0.0)
    if trend > 0.08 and consistency > 0.55:
        return 'push', round(0.35 * conf_q + 0.24, 3)
    if trend < -0.08 and consistency > 0.55:
        return 'pull', round(0.35 * conf_q + 0.24, 3)

    return 'handheld', round(0.42 * conf_q + 0.22, 3)


def interpolate_track(frame_start: int, frame_end: int, dx: np.ndarray, dy: np.ndarray, anchor_step: int = 8) -> List[Dict]:
    n = frame_end - frame_start
    if n <= 0:
        return []
    cdx = np.concatenate([[0.0], np.cumsum(dx)])
    cdy = np.concatenate([[0.0], np.cumsum(dy)])
    anchors = list(range(0, n + 1, anchor_step))
    if anchors[-1] != n:
        anchors.append(n)

    track = []
    for i in range(n + 1):
        li = max(a for a in anchors if a <= i)
        ri = min(a for a in anchors if a >= i)
        if ri == li:
            tx = float(cdx[li])
            ty = float(cdy[li])
        else:
            alpha = (i - li) / float(ri - li)
            tx = float((1 - alpha) * cdx[li] + alpha * cdx[ri])
            ty = float((1 - alpha) * cdy[li] + alpha * cdy[ri])
        track.append({
            'frame_index': int(frame_start + i),
            't': round((frame_start + i) / FPS, 3),
            'interp_dx': round(tx, 4),
            'interp_dy': round(ty, 4),
        })
    return track


def main() -> None:
    data = json.loads(INPUT_JSON.read_text())

    first = FRAMES_DIR / 'f_000001.jpg'
    w, h = read_image_dims(first)
    frames = load_gray_frames_from_jpg_sequence(str(FRAMES_DIR / 'f_%06d.jpg'), w, h)
    n_frames = int(frames.shape[0])

    # Per-step motion and frame diff
    dx = []
    dy = []
    conf = []
    diffs = []
    for i in range(n_frames - 1):
        a = frames[i]
        b = frames[i + 1]
        diffs.append(float(np.mean(np.abs(b.astype(np.int16) - a.astype(np.int16)))))
        sx, sy, pk = phase_correlation_shift(a, b)
        dx.append(sx)
        dy.append(sy)
        conf.append(pk)

    dx = np.array(dx, dtype=np.float32)
    dy = np.array(dy, dtype=np.float32)
    conf = np.array(conf, dtype=np.float32)
    diffs = np.array(diffs, dtype=np.float32)

    boundaries = detect_shot_boundaries(diffs)
    if boundaries[-1] != n_frames - 1:
        boundaries.append(n_frames - 1)

    shots = []
    interp = []
    for sidx in range(len(boundaries) - 1):
        s = boundaries[sidx]
        e = boundaries[sidx + 1]
        if e - s < 2:
            continue
        sdx = dx[s:e]
        sdy = dy[s:e]
        scf = conf[s:e]
        label, lconf = classify_shot(sdx, sdy, scf)
        mag = np.sqrt(sdx * sdx + sdy * sdy)
        shots.append({
            'shot_id': int(len(shots) + 1),
            'start_frame': int(s),
            'end_frame': int(e),
            'start_t': round(s / FPS, 3),
            'end_t': round(e / FPS, 3),
            'duration_s': round((e - s) / FPS, 3),
            'movement_type': label,
            'movement_confidence': round(float(lconf), 3),
            'mean_dx': round(float(np.mean(sdx)), 4),
            'mean_dy': round(float(np.mean(sdy)), 4),
            'mean_motion_mag': round(float(np.mean(mag)), 4),
            'median_frame_diff': round(float(np.median(diffs[s:e])), 4),
            'anchor_frames': [int(s), int((s + e) // 2), int(e)],
        })
        interp.extend(interpolate_track(s, e, sdx, sdy, anchor_step=8))

    movement_counts: Dict[str, int] = {}
    for sh in shots:
        movement_counts[sh['movement_type']] = movement_counts.get(sh['movement_type'], 0) + 1

    # Deduplicate interpolation rows at shot boundaries deterministically by frame_index.
    interp_by_frame = {}
    for row in interp:
        interp_by_frame[row['frame_index']] = row
    interp = [interp_by_frame[k] for k in sorted(interp_by_frame.keys())]

    temporal = {
        'version': 'posthoc-temporal-v1',
        'fps': FPS,
        'frames_total': n_frames,
        'method': {
            'shot_boundary': 'frame-diff-robust-threshold',
            'motion_estimation': 'phase-correlation-global-shift',
            'classification': 'rule-based-deterministic',
            'interpolation': 'linear-between-anchor-cumulative-motion',
        },
        'shot_boundaries': boundaries,
        'shots': shots,
        'interpolated_motion': interp,
        'summary': {
            'shot_count': len(shots),
            'movement_counts': dict(sorted(movement_counts.items())),
            'avg_shot_duration_s': round(float(np.mean([s['duration_s'] for s in shots])) if shots else 0.0, 3),
        },
    }

    # deterministic json output
    data['temporal_post'] = temporal

    # enhanced markdown with shot-level table
    lines = []
    lines.append('# Enhanced Temporal Summary (Posthoc)')
    lines.append('')
    lines.append(f"- Frames analyzed: {n_frames} @ {FPS:g} fps")
    lines.append(f"- Shot count: {len(shots)}")
    lines.append(f"- Movement mix: {', '.join([f'{k}={v}' for k,v in sorted(movement_counts.items())]) or 'n/a'}")
    lines.append('')
    lines.append('## Shot-Level Motion Table')
    lines.append('')
    lines.append('| Shot | Start (s) | End (s) | Dur (s) | Movement | Conf | mean dx | mean dy |')
    lines.append('|---:|---:|---:|---:|---|---:|---:|---:|')
    for sh in shots:
        lines.append(
            f"| {sh['shot_id']} | {sh['start_t']:.3f} | {sh['end_t']:.3f} | {sh['duration_s']:.3f} | {sh['movement_type']} | {sh['movement_confidence']:.3f} | {sh['mean_dx']:.3f} | {sh['mean_dy']:.3f} |"
        )
    lines.append('')
    lines.append('## Notes')
    lines.append('')
    lines.append('- Movement labels are deterministic and inferential from global inter-frame motion only.')
    lines.append('- `push/pull/truck/orbit` are emitted only when heuristics are strong enough; otherwise motion defaults to `pan/tilt/static/handheld`.')
    lines.append('- No semantic frame inference was rerun in this pass.')
    lines.append('')

    enhanced_md = '\n'.join(lines).strip() + '\n'
    data['final'] = enhanced_md.strip()

    INPUT_JSON.write_text(json.dumps(data, indent=2, sort_keys=True))
    INPUT_MD.write_text(enhanced_md)


if __name__ == '__main__':
    main()
