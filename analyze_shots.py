#!/usr/bin/env python3
import argparse, base64, glob, json, os, sys, requests

def extract_json_from_content(content):
    if isinstance(content, list):
        text_parts=[]
        for part in content:
            if isinstance(part, dict) and part.get('type') in ('output_text','text'):
                text_parts.append(part.get('text',''))
            elif isinstance(part,str):
                text_parts.append(part)
        content='\n'.join([t for t in text_parts if t])
    if not isinstance(content,str):
        return None,'non-string'
    s,e=content.find('{'),content.rfind('}')
    if s!=-1 and e!=-1 and e>s:
        try:return json.loads(content[s:e+1]),None
        except Exception as ex:return None,f'json-parse-failed: {ex}'
    return None,'no-json'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--frames-glob',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--base-url',default='http://192.168.1.242:6759')
    ap.add_argument('--model',default='qwen/qwen3-vl-8b')
    ap.add_argument('--api-key',default=os.getenv('LM_STUDIO_MCP_TOKEN',''))
    ap.add_argument('--max-tokens',type=int,default=500)
    args=ap.parse_args()

    headers={'Content-Type':'application/json'}
    if args.api_key: headers['Authorization']=f'Bearer {args.api_key}'
    chat_url=args.base_url.rstrip('/')+'/v1/chat/completions'
    load_url=args.base_url.rstrip('/')+'/api/v1/models/load'

    frame_paths=sorted(glob.glob(args.frames_glob))
    if not frame_paths:
        print('No frames found',file=sys.stderr); sys.exit(2)
    frames=[]
    for fp in frame_paths:
        with open(fp,'rb') as f:
            frames.append({'path':fp,'b64':base64.b64encode(f.read()).decode('ascii')})

    try:
        lr=requests.post(load_url,headers=headers,json={'model':args.model,'gpu_offload':'max'},timeout=90)
        load_resp={'status':lr.status_code,'body':lr.text[:400]}
    except Exception as ex:
        load_resp={'status':-1,'body':str(ex)}

    warm=requests.post(chat_url,headers=headers,json={
        'model':args.model,
        'messages':[{'role':'user','content':'say ok'}],
        'max_tokens':3,'temperature':0
    },timeout=90)

    prompt=(
      'You are analyzing a frame from a professional real estate video edit. Return STRICT JSON only, no markdown. '
      'JSON schema: {"room_type":"string","shot_type":"string","camera_motion":"string","composition":"string","lighting":"string","premium_features":[],"energy_level":0,"hook_candidate":false,"color_grade_style":"string","text_or_overlay_present":false}. '
      'room_type one of [exterior_front, exterior_back, living_room, kitchen, dining_room, bedroom, bathroom, hallway, staircase, pool, patio, balcony, garage, office, laundry, aerial, driveway, entrance, foyer].'
    )

    items=[]; ok=0
    for i,fr in enumerate(frames,1):
        payload={'model':args.model,'messages':[{'role':'user','content':[
            {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+fr['b64']}},
            {'type':'text','text':prompt}
        ]}],'max_tokens':args.max_tokens,'temperature':0.1}
        try:
            r=requests.post(chat_url,headers=headers,json=payload,timeout=90)
            rec={'index':i,'frame':fr['path'],'status':r.status_code}
            if r.status_code==200:
                body=r.json(); content=body.get('choices',[{}])[0].get('message',{}).get('content','')
                parsed,err=extract_json_from_content(content)
                if parsed is not None:
                    rec['parsed']=parsed; ok+=1
                else:
                    rec['parse_error']=err; rec['raw']=str(content)[:500]
            else:
                rec['error']=r.text[:500]
            items.append(rec)
            print(f'[{i}/{len(frames)}] status={rec["status"]}')
        except Exception as ex:
            items.append({'index':i,'frame':fr['path'],'status':-1,'error':str(ex)})
            print(f'[{i}/{len(frames)}] exception={ex}')

    out_obj={'model':args.model,'frames_total':len(frames),'items_count':ok,'warmup':{'status':warm.status_code,'body':warm.text[:400]},'load':load_resp,'items':items}
    os.makedirs(os.path.dirname(args.out),exist_ok=True)
    with open(args.out,'w') as f: json.dump(out_obj,f,indent=2)
    print(json.dumps({'out':args.out,'ok':ok,'total':len(frames),'warmup_status':warm.status_code},indent=2))

if __name__=='__main__': main()
