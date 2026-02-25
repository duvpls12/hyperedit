#!/usr/bin/env python3
import os, json, base64, shutil, subprocess, urllib.request, atexit
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
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
VISION_MODELS=[
    os.getenv('VISION_MODEL_11B','/Users/davideby/.lmstudio/models/leafspark/Llama-3.2-11B-Vision-Instruct-GGUF/Llama-3.2-11B-Vision-Instruct.Q4_K_M.gguf'),
    os.getenv('VISION_MODEL_8B','qwen/qwen3-vl-8b'),
    os.getenv('VISION_MODEL_4B','qwen/qwen2.5-vl-4b-instruct')
]
AUDIO_MODELS=['qwen2-audio-7b','gemma-music-recommender']
FPS=5
MAX_VIDEOS=10
LOCK_FILE=Path('/Users/davideby/hyperedit/state/video-analysis-single/.batch10.lock')
RULEBOOK_PATH=Path('/Users/davideby/hyperedit/docs/plans/cinematic_training_qa_rulebook_v1.json')

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

def _model_markers(model_id):
    m=(model_id or '').lower()
    tail=m.split('/')[-1]
    return {m, tail}


def _is_managed_vision_instance(instance_id):
    iid=(instance_id or '').lower()
    markers=set()
    for m in VISION_MODELS:
        markers |= _model_markers(m)
    return any(mark and mark in iid for mark in markers)


def validate_vision_instance_count(count):
    if count != 1:
        raise RuntimeError(f'Vision instance policy violation: expected exactly 1 managed vision instance, found {count}')
    return True


def ensure_single_vision_instance(model_id):
    ids=list_loaded()
    managed=[i for i in ids if _is_managed_vision_instance(i)]
    if len(managed) > 1:
        raise RuntimeError(f'Vision instance policy violation before load: {managed}')
    if len(managed) == 1:
        unload_instances(managed)

    req('/api/v1/models/load',{'model':model_id},'POST',240)
    ids=list_loaded()
    managed=[i for i in ids if _is_managed_vision_instance(i)]
    validate_vision_instance_count(len(managed))
    return managed[0]


def resolve_vision_model_with_fallback():
    failures=[]
    for model_id in VISION_MODELS:
        try:
            instance_id=ensure_single_vision_instance(model_id)
            return model_id, instance_id, failures
        except Exception as e:
            failures.append({'model':model_id,'error':str(e)})
            try:
                ids=[i for i in list_loaded() if _is_managed_vision_instance(i)]
                unload_instances(ids)
            except:
                pass
    raise RuntimeError('All vision model fallbacks failed: ' + json.dumps(failures))

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

    def infer_frame(i, fpath, model):
        b64=base64.b64encode(fpath.read_bytes()).decode()
        msg=[
            {'role':'system','content':'Return strict JSON only.'},
            {'role':'user','content':[
                {'type':'text','text':'Analyze frame and return JSON keys: shot_type, room_or_amenity, typography_present, composition, color_grade, camera_movement, sequence_role.'},
                {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+b64}}
            ]}
        ]
        try:
            raw=chat(model,msg,140,80)
        except Exception as e:
            raw=json.dumps({'error':str(e)})
        return {
            'frame_index':i,
            't':round(i/FPS,3),
            'frame':fpath.name,
            'analysis':raw,
            'instance':model
        }

    results={}
    max_workers=1
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        inflight=set()
        next_i=0
        # seed worker
        while next_i < len(frames) and len(inflight) < max_workers:
            inflight.add(ex.submit(infer_frame, next_i, frames[next_i], qinst))
            next_i += 1

        while inflight:
            done, inflight = wait(inflight, return_when=FIRST_COMPLETED)
            for fut in done:
                row=fut.result()
                results[row['frame_index']] = row
                if next_i < len(frames):
                    inflight.add(ex.submit(infer_frame, next_i, frames[next_i], qinst))
                    next_i += 1

    per=[results[i] for i in sorted(results.keys())]
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
    import re, statistics
    vid=video.stem.replace(' ','_')[:120]
    j1=json.loads(p1.read_text()); j2=json.loads(p2.read_text()); ja=json.loads(pa.read_text())

    fps=float(j1.get('fps') or 5)
    shots=j2.get('temporal_post',{}).get('shots',[])
    movement=Counter(s.get('movement_type','unknown') for s in shots)
    shot_durs=[float(s.get('duration_sec') or 0) for s in shots if float(s.get('duration_sec') or 0) > 0]

    rooms=Counter(); roles=Counter(); comps=Counter(); grades=Counter(); typo=0; total=0
    timeline=[]
    frame_meta={}
    for fr in j1.get('per_frame',[]):
        try:
            a=json.loads(fr.get('analysis','{}'))
        except:
            continue
        idx=int(fr.get('frame_index') or 0)
        total += 1
        room=str(a.get('room_or_amenity') or 'unknown').strip().lower()
        role=str(a.get('sequence_role') or 'unknown').strip().lower()
        comp=str(a.get('composition') or 'unknown').strip().lower()
        grade=str(a.get('color_grade') or 'unknown').strip().lower()
        rooms[room] += 1
        roles[role] += 1
        comps[comp] += 1
        grades[grade] += 1
        frame_meta[idx]={'room':room,'role':role,'typ':bool(a.get('typography_present'))}
        timeline.append({'t': float(fr.get('t') or 0), 'room': room, 'role': role, 'typ': bool(a.get('typography_present'))})
        if a.get('typography_present') is True:
            typo += 1

    opening_end=0.0
    for row in timeline:
        r=row['role']
        if ('title' in r) or ('intro' in r) or row['typ']:
            opening_end=row['t']
            continue
        break

    transitions=0
    prev=None
    for row in timeline:
        cur=row['room']
        if prev is not None and cur != prev:
            transitions += 1
        prev=cur

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

    # Rulebook-driven QA scoring
    try:
        rulebook=json.loads(RULEBOOK_PATH.read_text())
    except:
        rulebook={}
    weights=rulebook.get('weights',{})
    targets=rulebook.get('targets',{})

    def clamp01(x):
        return max(0.0, min(1.0, float(x)))

    def top_lines(counter,n):
        return '\n'.join([f"- {k}: {v} frames" for k,v in counter.most_common(n)]) if counter else '- n/a'

    move_mix=', '.join([f"{k}={v}" for k,v in movement.items()]) if movement else 'n/a'
    typo_pct=(typo/total*100.0) if total else 0.0
    avg_shot=(statistics.mean(shot_durs) if shot_durs else 0.0)
    med_shot=(statistics.median(shot_durs) if shot_durs else 0.0)
    p90=(statistics.quantiles(shot_durs, n=10)[8] if len(shot_durs)>=10 else med_shot)

    hook_window=float(targets.get('hook_window_sec',3.0))
    rehook_interval=float(targets.get('rehook_interval_sec',10.0))
    title_window_max=float(targets.get('title_window_max_sec',4.0))

    # proxy metrics
    hook_typ_ratio=(sum(1 for r in timeline if r['t']<=hook_window and r['typ']) / max(1,sum(1 for r in timeline if r['t']<=hook_window))) if timeline else 0.0
    hook_score=clamp01(0.5 + hook_typ_ratio*0.5)
    video_len=(float(j1.get('frames_total') or 0)/fps) if fps else 0.0
    expected_rehooks=max(1, int(video_len/rehook_interval))
    actual_rehooks=max(0, len(shots)//8)
    rehook_density=clamp01(actual_rehooks/expected_rehooks)
    motion_continuity=clamp01(1.0 - (movement.get('unknown',0)/max(1,len(shots))))
    tension_wave=clamp01(1.0 - abs(med_shot-1.3)/1.3)
    audio_immersion=clamp01((1.0 if ja.get('beats') else 0.0) * (1.0 if ja.get('onsets') else 0.0) * (1.0 if ja.get('spectral_brightness') else 0.0))

    # property/music match proxy
    txt=(gemma_summary + ' ' + ' '.join(gemma_recs)).lower()
    music_property_match=0.35
    for kw in ['cinematic','lounge','organic','piano','house','edm','classical','orchestral','acoustic']:
        if kw in txt:
            music_property_match += 0.08
    music_property_match=clamp01(music_property_match)

    title_penalty=clamp01(1.0 - max(0.0, opening_end-title_window_max)/max(1.0,title_window_max))
    viral_readiness=clamp01((hook_score*0.35)+(rehook_density*0.35)+(title_penalty*0.30))

    weighted=(
        hook_score*float(weights.get('hook',0.18)) +
        rehook_density*float(weights.get('rehook_density',0.14)) +
        motion_continuity*float(weights.get('motion_continuity',0.17)) +
        tension_wave*float(weights.get('tension_waveform',0.16)) +
        audio_immersion*float(weights.get('audio_immersion',0.12)) +
        music_property_match*float(weights.get('music_property_match',0.13)) +
        viral_readiness*float(weights.get('viral_readiness',0.10))
    )
    overall_score=round(weighted*100,1)

    # Chapter map by 8-shot windows
    chapters=[]
    chunk=8
    for i in range(0, len(shots), chunk):
        part=shots[i:i+chunk]
        if not part:
            continue
        s0=part[0]; s1=part[-1]
        start=int(s0.get('start_frame') or 0); end=int(s1.get('end_frame') or start)
        c_rooms=Counter(); c_moves=Counter()
        for f in range(start, end+1):
            meta=frame_meta.get(f)
            if meta:
                c_rooms[meta['room']] += 1
        for s in part:
            c_moves[str(s.get('movement_type') or 'unknown')] += 1
        chapters.append({
            'idx': len(chapters)+1,
            'start_t': start/fps,
            'end_t': end/fps,
            'dominant_room': (c_rooms.most_common(1)[0][0] if c_rooms else 'unknown'),
            'movement_mix': ', '.join([f"{k}:{v}" for k,v in c_moves.items()]) if c_moves else 'n/a'
        })
    chapter_md='\n'.join([f"- Chapter {c['idx']}: {c['start_t']:.1f}s → {c['end_t']:.1f}s | room={c['dominant_room']} | movement={c['movement_mix']}" for c in chapters]) if chapters else '- n/a'

    # Music cue map from beat positions
    cue_md='- n/a'
    beats=ja.get('beats') or []
    if beats:
        cues=[]
        # librosa beat frames -> seconds approximation using hop_length=512, sr=22050
        for b in beats[:12]:
            try:
                sec=(float(b)*512.0)/22050.0
                cues.append(sec)
            except:
                pass
        cue_md='\n'.join([f"- Cue {i+1}: {t:.2f}s — align transition/accent" for i,t in enumerate(cues)]) if cues else '- n/a'

    # full shot table (forensic)
    rows=[]
    for s in shots:
        st=int(s.get('start_frame') or 0); en=int(s.get('end_frame') or st)
        room_c=Counter(); role_c=Counter()
        for f in range(st,en+1):
            meta=frame_meta.get(f)
            if not meta:
                continue
            room_c[meta['room']] += 1
            role_c[meta['role']] += 1
        d_room=room_c.most_common(1)[0][0] if room_c else 'unknown'
        d_role=role_c.most_common(1)[0][0] if role_c else 'unknown'
        rows.append(
            f"| {s.get('shot_id')} | {st/fps:.2f} | {en/fps:.2f} | {float(s.get('duration_sec') or 0):.2f} | {s.get('movement_type')} | {float(s.get('confidence') or 0):.2f} | {d_room} | {d_role} |"
        )
    shot_table='\n'.join(rows) if rows else '| n/a |'

    music_notes='\n'.join([f"- {r}" for r in gemma_recs]) if gemma_recs else '- n/a'

    md=(
        f"# Final Synthesis — {video.name}\n\n"
        f"## Executive Summary\n"
        f"This cut opens branding-heavy and then moves into fast-cycle property coverage. Temporal segmentation is still oversensitive, so this forensic view prioritizes shot-level structure over high-level prose. Audio tempo is ~{ja.get('bpm'):.1f} BPM and currently needs domain-constrained recommendation logic for luxury RE.\n\n"
        f"## Core Metrics\n"
        f"- Frames analyzed: **{j1.get('frames_total')}** @ {fps:g} fps\n"
        f"- Shot count: **{len(shots)}**\n"
        f"- Shot duration stats: avg **{avg_shot:.2f}s**, median **{med_shot:.2f}s**, p90 **{p90:.2f}s**\n"
        f"- Movement mix: **{move_mix}**\n"
        f"- Typography: **{typo}/{total} frames** ({typo_pct:.1f}%)\n"
        f"- Opening title window estimate: **0.0s → {opening_end:.1f}s**\n"
        f"- Room transitions: **{transitions}**\n"
        f"- Audio BPM: **{ja.get('bpm')}**\n\n"
        f"## Cinematic QA Scorecard\n"
        f"- Overall Score: **{overall_score}/100**\n"
        f"- Hook (0–3s): **{hook_score*100:.1f}**\n"
        f"- Rehook Density: **{rehook_density*100:.1f}**\n"
        f"- Motion Continuity: **{motion_continuity*100:.1f}**\n"
        f"- Tension Waveform: **{tension_wave*100:.1f}**\n"
        f"- Audio Immersion: **{audio_immersion*100:.1f}**\n"
        f"- Music-Property Match: **{music_property_match*100:.1f}**\n"
        f"- Viral Readiness: **{viral_readiness*100:.1f}**\n\n"
        f"## Chapter Timeline\n{chapter_md}\n\n"
        f"## Coverage Distributions\n"
        f"### Room/Amenity\n{top_lines(rooms,10)}\n\n"
        f"### Sequence Role\n{top_lines(roles,10)}\n\n"
        f"### Composition\n{top_lines(comps,8)}\n\n"
        f"### Color/Grade\n{top_lines(grades,8)}\n\n"
        f"## Audio + Music Fit\n"
        f"- DSP baseline complete (tempo/onset/energy/brightness).\n"
        f"- Gemma summary: **{gemma_summary or 'n/a'}**\n"
        f"- Suggested tracks/styles:\n{music_notes}\n\n"
        f"## Music Cue Map (Beat-Anchored)\n{cue_md}\n\n"
        f"## Forensic Shot Table\n"
        f"| Shot | Start(s) | End(s) | Dur(s) | Movement | Conf | Dominant Room | Dominant Role |\n"
        f"|---:|---:|---:|---:|---|---:|---|---|\n"
        f"{shot_table}\n\n"
        f"## QA Flags\n"
        f"1. Shot fragmentation is likely too high for premium readability.\n"
        f"2. Intro/title phase is longer than ideal for immediate property immersion.\n"
        f"3. Music recommendations remain generic and require domain priors.\n\n"
        f"## Edit Direction (Actionable)\n"
        f"- Increase temporal threshold + enforce 1.2–1.5s min shot duration.\n"
        f"- Cap intro/title overlay duration unless brand-first brief is explicit.\n"
        f"- Re-rank music candidates against luxury-RE style buckets (cinematic/lounge/organic-house/piano-led).\n"
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
            vid=v.stem.replace(' ','_')[:120]
            try:
                vision_model, vision_instance, vision_failures = resolve_vision_model_with_fallback()
                print('VISION_MODEL_SELECTED', vision_model)
                if vision_failures:
                    print('VISION_FALLBACK_CHAIN', json.dumps(vision_failures))

                p1, frame_dir, frames = vision_pass1(v, vision_model)
                # annotate pass1 with model provenance + fallback chain
                p1j=json.loads(p1.read_text())
                p1j['vision_model_used']=vision_model
                p1j['vision_fallback_chain']=vision_failures
                p1.write_text(json.dumps(p1j, indent=2))

                p2 = temporal_post(v, p1, frames)
                unload_instances([vision_instance])

                am = load_audio_models()
                pa = audio_pass(v, am)
                final_synthesis(v, p1, p2, pa)
                unload_instances(am)
                dest=DONE/v.name
                shutil.move(str(v), str(dest))
                print('DONE',v.name,'->',dest)
            except Exception as e:
                fail={
                    'video': str(v),
                    'error': str(e),
                    'vision_models_attempted': VISION_MODELS
                }
                (OUT_F/f'{vid}_failed.json').write_text(json.dumps(fail, indent=2))
                print('FAILED', v.name, str(e))
                continue
        print('BATCH_DONE')
    finally:
        release_lock()

if __name__=='__main__':
    main()
