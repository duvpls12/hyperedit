#!/usr/bin/env python3
import os, json, base64, shutil, subprocess, urllib.request, atexit
from pathlib import Path
import numpy as np

ROOT = Path('/Volumes/Charlie/hyperedit-video-intel')
ALL = ROOT / 'all_files'
DONE = ROOT / 'done'
DONE.mkdir(parents=True, exist_ok=True)

OUT_V = Path('/Users/davideby/hyperedit/state/video-analysis-single')
OUT_A = Path('/Users/davideby/hyperedit/state/audio-analysis')
OUT_F = Path('/Users/davideby/hyperedit/state/final-analysis')
for p in (OUT_V, OUT_A, OUT_F): p.mkdir(parents=True, exist_ok=True)

HOST='http://192.168.1.242:6759'
QWEN='qwen/qwen3-vl-8b'
AUDIO_MODELS=['qwen2-audio-7b','gemma-music-recommender']
FPS=5
MAX_VIDEOS=10
LOCK_FILE=Path('/Users/davideby/hyperedit/state/video-analysis-single/.batch10.lock')

key=''
for l in Path('/Users/davideby/hyperedit/.env').read_text().splitlines():
    if l.startswith('LM_STUDIO_API_KEY='):
        key=l.split('=',1)[1].strip(); break
H={'Authorization':f'Bearer {key}','Content-Type':'application/json'}

def req(path,payload=None,method='POST',timeout=180):
    data=None if payload is None else json.dumps(payload).encode()
    r=urllib.request.Request(HOST+path,data=data,headers=H,method=method)
    with urllib.request.urlopen(r,timeout=timeout) as resp:
        txt=resp.read().decode() or '{}'
    try: return json.loads(txt)
    except: return {'raw':txt}

def chat(model,messages,max_tokens=250,timeout=120):
    return req('/v1/chat/completions',{'model':model,'messages':messages,'temperature':0,'max_tokens':max_tokens},timeout=timeout)['choices'][0]['message'].get('content','')

def list_loaded():
    ids=[]
    try:
        raw=req('/api/v1/models',None,'GET',30)
    except:
        raw={}
    # LM Studio may return either {data:[...]} or {models:[...]}.
    models=raw.get('data') or raw.get('models') or []
    for m in models:
        # Newer shape: loaded_instances under each model
        li=m.get('loaded_instances') or []
        if li:
            for inst in li:
                iid=inst.get('identifier') or inst.get('id')
                if iid: ids.append(iid)
            continue
        # Older shape: flat entries
        i=m.get('id') or m.get('instance_id')
        if i: ids.append(i)
    return ids

def ensure_two_qwen():
    ids=list_loaded()
    q=sorted([i for i in ids if i.startswith('qwen/qwen3-vl-8b')])
    if len(q)>2:
        raise RuntimeError(f'More than 2 qwen instances loaded: {q}')
    while len(q)<2:
        req('/api/v1/models/load',{'model':QWEN},'POST',240)
        # Re-read after each load; fail closed if cap is exceeded.
        q=sorted([i for i in list_loaded() if i.startswith('qwen/qwen3-vl-8b')])
        if len(q)>2:
            raise RuntimeError(f'Cap exceeded after load: {q}')
    return q[:2]

def unload_instances(ids):
    for i in ids:
        try: req('/api/v1/models/unload',{'instance_id':i},'POST',60)
        except: pass

def load_audio_models():
    loaded=[]
    for m in AUDIO_MODELS:
        try:
            r=req('/api/v1/models/load',{'model':m},'POST',240)
            loaded.append(r.get('instance_id') or r.get('id') or m)
        except:
            loaded.append(m)
    return loaded

def ffprobe_duration(path):
    try:
        out=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],text=True).strip()
        return float(out)
    except:
        return 60.0

def extract_frames(video, frame_dir):
    frame_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg','-y','-i',str(video),'-vf',f'fps={FPS},scale=640:-1',str(frame_dir/'f_%06d.jpg')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return sorted(frame_dir.glob('f_*.jpg'))

def vision_pass1(video, qinst):
    vid=video.stem.replace(' ','_')[:120]
    frame_dir=OUT_V/f'frames_{vid}'
    frames=extract_frames(video, frame_dir)
    per=[]
    for i,f in enumerate(frames):
        model=qinst[i%2]
        b64=base64.b64encode(f.read_bytes()).decode()
        msg=[{'role':'system','content':'Return strict JSON only.'},{'role':'user','content':[{'type':'text','text':'Analyze frame and return JSON keys: shot_type, room_or_amenity, typography_present, composition, color_grade, camera_movement, sequence_role.'},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+b64}}]}]
        try: raw=chat(model,msg,140,80)
        except Exception as e: raw=json.dumps({'error':str(e)})
        per.append({'frame_index':i,'t':round(i/FPS,3),'frame':f.name,'analysis':raw,'instance':model})
    out={'video':str(video),'fps':FPS,'frames_total':len(frames),'per_frame':per}
    p=OUT_V/f'{vid}_vision_pass1.json'; p.write_text(json.dumps(out,indent=2))
    return p, frame_dir, frames

def temporal_post(video, pass1_json, frames):
    arr=[]
    for i in range(len(frames)-1):
        a=np.frombuffer(subprocess.check_output(['ffmpeg','-hide_banner','-loglevel','error','-i',str(frames[i]),'-f','rawvideo','-pix_fmt','gray','-'],),dtype=np.uint8)
        b=np.frombuffer(subprocess.check_output(['ffmpeg','-hide_banner','-loglevel','error','-i',str(frames[i+1]),'-f','rawvideo','-pix_fmt','gray','-'],),dtype=np.uint8)
        n=min(len(a),len(b));
        arr.append(float(np.mean(np.abs(a[:n].astype(np.int16)-b[:n].astype(np.int16)))))
    diffs=np.array(arr if arr else [0.0])
    med=float(np.median(diffs)); thr=max(med*2.4, med+5)
    boundaries=[0]+[i+1 for i,v in enumerate(diffs) if v>thr]
    if boundaries[-1] != len(frames)-1: boundaries.append(len(frames)-1)
    boundaries=sorted(set(boundaries))
    shots=[]
    for i in range(len(boundaries)-1):
        s,e=boundaries[i],boundaries[i+1]
        d=(e-s)/FPS
        shots.append({'shot_id':i+1,'start_frame':s,'end_frame':e,'duration_sec':round(d,3),'movement_type':'static' if d>2 else 'pan','confidence':0.35})
    j=json.loads(pass1_json.read_text())
    j['temporal_post']={'fps':FPS,'frames_total':len(frames),'shot_boundaries':boundaries,'shots':shots,'summary':{'shot_count':len(shots),'movement_counts':{k:sum(1 for s in shots if s['movement_type']==k) for k in ['static','pan']}}}
    vid=video.stem.replace(' ','_')[:120]
    p=OUT_V/f'{vid}_vision_pass2_temporal.json'; p.write_text(json.dumps(j,indent=2))
    return p

def audio_pass(video, audio_models):
    import librosa
    vid=video.stem.replace(' ','_')[:120]
    wav=OUT_A/f'{vid}.wav'
    subprocess.run(['ffmpeg','-y','-i',str(video),'-vn','-ac','1','-ar','22050',str(wav)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    y,sr=librosa.load(str(wav),sr=22050,mono=True)
    tempo,beats=librosa.beat.beat_track(y=y,sr=sr)
    onset=librosa.onset.onset_strength(y=y,sr=sr)
    cent=librosa.feature.spectral_centroid(y=y,sr=sr)[0]
    dsp={'bpm':float(tempo),'beats':[float(b) for b in beats[:500]],'onsets':[float(x) for x in onset[:500]],'energy_curve':[float(x) for x in librosa.feature.rms(y=y)[0][:500]],'spectral_brightness':[float(x) for x in cent[:500]]}

    summaries=[]
    for m in audio_models:
        try:
            s=chat(m,[{'role':'system','content':'Return concise JSON only.'},{'role':'user','content':f'Given audio features {json.dumps({"bpm":dsp["bpm"],"energy_mean":float(np.mean(dsp["energy_curve"]))})}, provide sound design summary and music recommendations.'}],350,90)
        except Exception as e:
            s=json.dumps({'error':str(e)})
        summaries.append({'model':m,'summary':s})

    out={'video':str(video),'audio_models':audio_models,'audio_models_loaded':True,'bpm':dsp['bpm'],'beats':dsp['beats'],'onsets':dsp['onsets'],'energy_curve':dsp['energy_curve'],'spectral_brightness':dsp['spectral_brightness'],'segments':[],'sound_design_events':[],'audio_semantic_summary':summaries,'music_fit_score':None,'music_recommendations':[]}
    p=OUT_A/f'{vid}_audio_pass.json'; p.write_text(json.dumps(out,indent=2))
    try: wav.unlink()
    except: pass
    return p

def final_synthesis(video, p1, p2, pa):
    from collections import Counter
    import re
    vid=video.stem.replace(' ','_')[:120]
    j1=json.loads(p1.read_text()); j2=json.loads(p2.read_text()); ja=json.loads(pa.read_text())

    shots=j2.get('temporal_post',{}).get('shots',[])
    movement=Counter(s.get('movement_type','unknown') for s in shots)
    rooms=Counter(); roles=Counter(); typo=0; total=0
    for fr in j1.get('per_frame',[]):
        try:
            a=json.loads(fr.get('analysis','{}'))
        except:
            continue
        total += 1
        rooms[str(a.get('room_or_amenity') or 'unknown').strip().lower()] += 1
        roles[str(a.get('sequence_role') or 'unknown').strip().lower()] += 1
        if a.get('typography_present') is True:
            typo += 1

    gemma_summary=''
    gemma_recs=[]
    for item in ja.get('audio_semantic_summary',[]):
        if 'gemma' not in str(item.get('model','')).lower():
            continue
        txt=item.get('summary','')
        m=re.search(r'\{[\s\S]*\}', txt)
        if not m:
            continue
        try:
            gj=json.loads(m.group(0))
            gemma_summary=gj.get('summary','')
            gemma_recs=[r.get('title') for r in gj.get('recommendations',[]) if isinstance(r,dict) and r.get('title')]
        except:
            pass

    top_rooms=', '.join([f"{k} ({v})" for k,v in rooms.most_common(8)]) if rooms else 'n/a'
    top_roles=', '.join([f"{k} ({v})" for k,v in roles.most_common(8)]) if roles else 'n/a'
    move_mix=', '.join([f"{k}={v}" for k,v in movement.items()]) if movement else 'n/a'
    typo_pct=(typo/total*100.0) if total else 0.0

    md=(
        f"# Final Synthesis — {video.name}\n\n"
        f"## Core Metrics\n"
        f"- Frames analyzed: **{j1.get('frames_total')}** @ {j1.get('fps')} fps\n"
        f"- Shot count (temporal pass): **{len(shots)}**\n"
        f"- Movement mix: **{move_mix}**\n"
        f"- Typography presence: **{typo}/{total} frames** ({typo_pct:.1f}%)\n"
        f"- Audio BPM: **{ja.get('bpm')}**\n\n"
        f"## Room/Amenity Coverage\n{top_rooms}\n\n"
        f"## Sequence Role Distribution\n{top_roles}\n\n"
        f"## Audio + Music Fit\n"
        f"- DSP baseline complete (tempo/onset/energy/brightness).\n"
        f"- Gemma summary: **{gemma_summary or 'n/a'}**\n"
        f"- Suggested tracks/styles: {', '.join(gemma_recs) if gemma_recs else 'n/a'}\n"
    )
    p=OUT_F/f'{vid}_final_synthesis.md'; p.write_text(md)
    (OUT_F/f'{vid}_done.marker').write_text('done\n')
    return p


def acquire_lock():
    if LOCK_FILE.exists():
        raise RuntimeError(f'Batch runner lock exists: {LOCK_FILE}. Another run is active or previous run crashed.')
    LOCK_FILE.write_text(str(os.getpid()) + '\n')


def release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except:
        pass


def main():
    acquire_lock()
    atexit.register(release_lock)
    try:
        vids=sorted([p for p in ALL.iterdir() if p.is_file() and p.suffix.lower() in ['.mp4','.mov','.mkv','.webm','.m4v']])[:MAX_VIDEOS]
        print('TARGET_VIDEOS',len(vids))
        for v in vids:
            print('START',v.name)
            q=ensure_two_qwen()
            p1, frame_dir, frames = vision_pass1(v, q)
            p2 = temporal_post(v, p1, frames)
            unload_instances(q)
            am = load_audio_models()
            pa = audio_pass(v, am)
            final_synthesis(v, p1, p2, pa)
            unload_instances(am)
            dest=DONE/v.name
            shutil.move(str(v), str(dest))
            print('DONE',v.name,'->',dest)
        print('BATCH_DONE')
    finally:
        release_lock()

if __name__=='__main__':
    main()
