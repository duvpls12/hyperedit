#!/usr/bin/env python3
import base64, json, re, os, io
from pathlib import Path
import requests
from bisect import bisect_left
from datetime import datetime, timezone
from PIL import Image

ROOT = Path('/Users/davideby/hyperedit')
BASE = ROOT/'state'/'baseline'/'1044-waterbury'
OUT = ROOT/'state'/'agents'/'1044_waterbury_20260228'/'rebuild_v2'
OUT.mkdir(parents=True, exist_ok=True)

LM_BASE = os.getenv('LM_STUDIO_SERVER_URL','http://192.168.1.242:6759').rstrip('/')
if '192.168.1.242:6759' not in LM_BASE:
    LM_BASE = 'http://192.168.1.242:6759'
API = LM_BASE + '/v1'
MODEL_LADDER = ['llama-3.2-11b-vision-instruct','qwen/qwen3-vl-8b','qwen/qwen3-vl-4b']

clean_slate = {
  'step':'0_clean_slate',
  'deleted':[],
  'preserved_keep_list':'all existing artifacts preserved; no explicit invalid artifact list was provided in task context',
  'blocker_if_any': None
}
(OUT/'clean_slate_report.json').write_text(json.dumps(clean_slate, indent=2))

fps5 = BASE/'fps_5'
frames = sorted([p for p in fps5.glob('f_*.jpg')])
ffprobe = json.loads((BASE/'ffprobe.json').read_text())
audio = json.loads((BASE/'audio_dsp_real.json').read_text())
scene_log = (BASE/'scene_detect.log').read_text()
inputs_manifest = {
  'step':'1A_inputs_frames',
  'frames_dir': str(fps5),
  'frame_count': len(frames),
  'ffprobe_path': str(BASE/'ffprobe.json'),
  'audio_dsp_path': str(BASE/'audio_dsp_real.json'),
  'scene_log_path': str(BASE/'scene_detect.log'),
  'timestamp_utc': datetime.now(timezone.utc).isoformat()
}
(OUT/'inputs_manifest_v2.json').write_text(json.dumps(inputs_manifest, indent=2))

avail = requests.get(API+'/models', timeout=20).json().get('data',[])
avail_ids = [m['id'] for m in avail]
model_load = {'step':'1B_model_load', 'api': API, 'available': avail_ids, 'warmups': []}
for m in MODEL_LADDER:
    if m not in avail_ids:
        model_load['warmups'].append({'model':m,'status':'missing'})
        continue
    try:
        r = requests.post(API+'/chat/completions', json={
            'model': m,
            'messages': [{'role':'user','content':'Reply with JSON: {"ok":true}'}],
            'temperature':0,
            'max_tokens':20
        }, timeout=60)
        model_load['warmups'].append({'model':m,'status':'ok' if r.ok else 'error','http':r.status_code})
    except Exception as e:
        model_load['warmups'].append({'model':m,'status':'error','error':str(e)})
(OUT/'model_load_report_v2.json').write_text(json.dumps(model_load, indent=2))

def nearest_frame_for_time(t):
    idx = max(1, min(len(frames), round(t*5)))
    return frames[idx-1], idx/5.0

def classify_image(img_path):
    im = Image.open(img_path).convert('RGB')
    max_w = 768
    if im.width > max_w:
        nh = int(im.height * (max_w / im.width))
        im = im.resize((max_w, nh))
    bio = io.BytesIO(); im.save(bio, format='JPEG', quality=72)
    img_b64 = base64.b64encode(bio.getvalue()).decode('utf-8')
    prompt = (
      'Classify this real-estate frame. Return strict JSON keys only: '
      'room_tag, scene_type, camera_motion, shot_type, mood, confidence (0..1). '
      'room_tag must be one of: exterior, entrance, living_room, kitchen, dining_room, bedroom, bathroom, staircase, hallway, balcony, garage, pool, patio, yard, detail, unknown.'
    )
    errs=[]
    for m in MODEL_LADDER:
        if m not in avail_ids:
            errs.append({'model':m,'error':'missing'})
            continue
        try:
            r = requests.post(API+'/chat/completions', json={
                'model': m,
                'temperature': 0,
                'max_tokens': 180,
                'response_format': {'type':'json_object'},
                'messages': [{
                    'role':'user',
                    'content':[
                        {'type':'text','text':prompt},
                        {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{img_b64}'}}
                    ]
                }]
            }, timeout=120)
            if not r.ok:
                errs.append({'model':m,'error':f'http_{r.status_code}'})
                continue
            text = r.json()['choices'][0]['message']['content']
            data = json.loads(text)
            return {'ok':True,'model_used':m,'result':data,'fallback_errors':errs}
        except Exception as e:
            errs.append({'model':m,'error':str(e)})
    return {'ok':False,'model_used':None,'result':{'room_tag':'unknown','scene_type':'unknown','camera_motion':'unknown','shot_type':'unknown','mood':'unknown','confidence':0.0},'fallback_errors':errs}

pts = [float(x) for x in re.findall(r'pts_time:([0-9]+\.?[0-9]*)', scene_log)]
pts = sorted(set(pts))
duration = float(ffprobe['format']['duration'])
if not pts or pts[0] > 0.2:
    pts = [0.0] + pts
if pts[-1] < duration:
    pts.append(duration)
shots=[]
for i in range(len(pts)-1):
    s,e = pts[i], pts[i+1]
    mid = (s+e)/2
    shots.append({'shot_index':i+1,'start_s':round(s,3),'end_s':round(e,3),'duration_s':round(e-s,3),'mid_s':round(mid,3)})
cut_map = {
  'video':'1044_waterbury_lane',
  'source_scene_log':str(BASE/'scene_detect.log'),
  'total_cuts': len(pts)-2 if len(pts)>=2 else 0,
  'total_shots': len(shots),
  'cuts_per_minute': round(((len(pts)-2)/duration)*60,2) if duration else None,
  'shots': shots
}
(OUT/'cut_map.json').write_text(json.dumps(cut_map, indent=2))

semantic_tags=[]
edit_sequence=[]
room_flow=[]
blockers=[]
for sh in shots:
    img, img_t = nearest_frame_for_time(sh['mid_s'])
    cls = classify_image(img)
    if not cls['ok']:
        blockers.append({'shot_index':sh['shot_index'],'mid_s':sh['mid_s'],'issue':'all_models_failed','fallback_errors':cls['fallback_errors']})
    r = cls['result']
    sem = {
      'shot_index': sh['shot_index'],
      'frame': str(img.relative_to(ROOT)),
      'frame_time_s': round(img_t,3),
      'shot_start_s': sh['start_s'],
      'shot_end_s': sh['end_s'],
      'room_tag': r.get('room_tag','unknown'),
      'scene_type': r.get('scene_type','unknown'),
      'camera_motion': r.get('camera_motion','unknown'),
      'shot_type': r.get('shot_type','unknown'),
      'mood': r.get('mood','unknown'),
      'confidence': float(r.get('confidence',0) or 0),
      'vision_model_used': cls['model_used'],
      'vision_fallback_chain': cls['fallback_errors']
    }
    semantic_tags.append(sem)
    edit_sequence.append({
      'order': sh['shot_index'],
      'shot_window_s': [sh['start_s'], sh['end_s']],
      'middle_frame': sem['frame'],
      'semantic': {
        'room_tag': sem['room_tag'],
        'scene_type': sem['scene_type'],
        'camera_motion': sem['camera_motion'],
        'shot_type': sem['shot_type'],
        'confidence': sem['confidence']
      }
    })

cur=None
for s in semantic_tags:
    room = s['room_tag']
    if cur is None or cur['room_tag']!=room:
        cur = {'room_tag':room,'start_shot':s['shot_index'],'end_shot':s['shot_index'],'duration_s':0.0,'shots':1}
        room_flow.append(cur)
    else:
        cur['end_shot']=s['shot_index']
        cur['shots'] += 1
    cur['duration_s'] = round(cur['duration_s'] + (s['shot_end_s']-s['shot_start_s']),3)

semantic_doc = {
  'video':'1044_waterbury_lane',
  'version':'v2',
  'source':'per-shot middle frame classification via LM Studio',
  'model_ladder': MODEL_LADDER,
  'lm_studio_api': API,
  'tags': semantic_tags,
  'blocking_issues': blockers
}
(OUT/'semantic_tags_v2.json').write_text(json.dumps(semantic_doc, indent=2))
(OUT/'davids_edit_sequence.json').write_text(json.dumps({'video':'1044_waterbury_lane','sequence':edit_sequence,'blocking_issues':blockers}, indent=2))
(OUT/'room_flow.json').write_text(json.dumps({'video':'1044_waterbury_lane','room_flow':room_flow,'room_sequence':[x['room_tag'] for x in room_flow]}, indent=2))

beats = audio.get('beats',[])
beat_offsets=[]
for sh in shots:
    c = sh['start_s']
    if not beats:
        off=None
    else:
        pos = bisect_left(beats, c)
        cand=[]
        if pos < len(beats): cand.append(abs(beats[pos]-c))
        if pos > 0: cand.append(abs(beats[pos-1]-c))
        off=min(cand) if cand else None
    beat_offsets.append(off)
valid_offsets=[x for x in beat_offsets if x is not None]
aligned = sum(1 for x in valid_offsets if x<=0.12)
analysis = {
  'video':'1044_waterbury_lane',
  'audio_source': str(BASE/'audio_dsp_real.json'),
  'bpm': audio.get('bpm'),
  'beat_count': len(beats),
  'cut_count': cut_map['total_cuts'],
  'alignment_tolerance_s': 0.12,
  'aligned_cuts': aligned,
  'alignment_ratio': round(aligned/len(valid_offsets),4) if valid_offsets else 0.0,
  'mean_cut_to_beat_offset_s': round(sum(valid_offsets)/len(valid_offsets),4) if valid_offsets else None,
  'median_cut_to_beat_offset_s': round(sorted(valid_offsets)[len(valid_offsets)//2],4) if valid_offsets else None
}
(OUT/'beat_sync_analysis.json').write_text(json.dumps(analysis, indent=2))

room_seq=[x['room_tag'] for x in room_flow]
canon=['living_room','kitchen','dining_room','bedroom','bathroom']
canon_idx={r:i for i,r in enumerate(canon)}
seq_filtered=[r for r in room_seq if r in canon_idx]
inversions=0
for a,b in zip(seq_filtered,seq_filtered[1:]):
    if canon_idx[b] < canon_idx[a]: inversions += 1
room_order_score = max(0, round(100 - inversions*12.5,2))
beat_score = round(analysis['alignment_ratio']*100,2)
cut_rate_target=103.09
cut_delta=abs(cut_map['cuts_per_minute']-cut_rate_target)
pace_score=max(0, round(100 - cut_delta*2.0,2))
overall=round(0.4*pace_score + 0.3*room_order_score + 0.3*beat_score,2)
rubric = {
  'video':'1044_waterbury_lane',
  'version':'v2',
  'inputs': {
    'semantic_tags_v2': str(OUT/'semantic_tags_v2.json'),
    'cut_map': str(OUT/'cut_map.json'),
    'davids_edit_sequence': str(OUT/'davids_edit_sequence.json'),
    'beat_sync_analysis': str(OUT/'beat_sync_analysis.json'),
    'room_flow': str(OUT/'room_flow.json')
  },
  'metrics': {
    'cuts_per_minute': cut_map['cuts_per_minute'],
    'target_cuts_per_minute': cut_rate_target,
    'pace_score': pace_score,
    'room_order_score': room_order_score,
    'beat_alignment_score': beat_score
  },
  'score': {
    'overall': overall,
    'formula': '0.4*pace + 0.3*room_order + 0.3*beat_alignment'
  },
  'blockers': blockers
}
(OUT/'rubric_v2.json').write_text(json.dumps(rubric, indent=2))

training_entry = {
  'ts_utc': datetime.now(timezone.utc).isoformat(),
  'cycle': 1,
  'rubric_path': str(OUT/'rubric_v2.json'),
  'score': overall,
  'notes': 'initial scaffold entry; no rendered recreate output produced in this run'
}
with (OUT/'training_log.jsonl').open('a') as f:
    f.write(json.dumps(training_entry, sort_keys=True) + '\n')
initial_grade = {
  'project_id': '1044_waterbury_20260228',
  'cycle': 1,
  'overall_score': overall,
  'status': 'scaffolded_no_render',
  'rendered_video_path': None,
  'top_deltas': [
    {'metric':'pace_score','delta_to_90': round(90-pace_score,2)},
    {'metric':'room_order_score','delta_to_90': round(90-room_order_score,2)},
    {'metric':'beat_alignment_score','delta_to_90': round(90-beat_score,2)}
  ]
}
(OUT/'initial_grade_card.json').write_text(json.dumps(initial_grade, indent=2))

print(json.dumps({'out':str(OUT),'overall_score':overall,'cuts':cut_map['total_cuts'],'room_sequence':room_seq,'beat_alignment':analysis['alignment_ratio']}, indent=2))
