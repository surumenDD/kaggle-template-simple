#!/usr/bin/env python3
"""Local-only deterministic replay of EXISTING lecture annotations. No OCR/ASR/LLM.
Private media and annotation text are never sent to a network service.
Python >=3.10. ffmpeg + ffprobe required for media commands.
"""
from __future__ import annotations
import argparse, contextlib, hashlib, importlib.metadata, json, math, os, re
import shutil, subprocess, sys, tempfile, urllib.request, wave, zipfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path, PurePosixPath
from fractions import Fraction

VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parent
FONT_URL = 'https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/Sans/OTF/Japanese/NotoSansCJKjp-Regular.otf'
FONT_NAME = 'NotoSansCJKjp-Regular.otf'
DEFAULTS = {'sample_rate':48000, 'max_speed':1.65, 'gap_ms':30,
            'crf':16, 'preset':'medium', 'threads':2, 'expected_lesson_count':40,
            'engine':'pyopenjtalk-plus', 'engine_version':'0.4.1.post8',
            'voice':'mei_normal', 'predict_nani':False, 'run_marine':False}
TEXT_EXT = {'.json','.ass','.srt','.txt','.md','.csv'}
FONT_EXT = {'.ttf','.otf','.ttc','.woff','.woff2'}

class Stop(RuntimeError): pass

def fail(message): raise Stop(message)
def readj(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def writej(p, obj):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    os.replace(tmp,p)
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def jhash(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sample(t, sr): return int((Decimal(str(t))*sr).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def command(argv, *, cwd=None, logfile=None):
    argv=[str(x) for x in argv]
    if logfile:
        Path(logfile).parent.mkdir(parents=True,exist_ok=True)
        with Path(logfile).open('wb') as f: r=subprocess.run(argv,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
        if r.returncode: fail(f'Command failed ({r.returncode}); see {logfile}')
        return ''
    r=subprocess.run(argv,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if r.returncode: fail(f'Command failed ({r.returncode}): {argv[0]}\n'+r.stderr.decode('utf-8','replace')[-5000:])
    return r.stdout.decode('utf-8','replace')
def need_tools():
    for n in ('ffmpeg','ffprobe'):
        if not shutil.which(n): fail(f'{n} not found in PATH. See RUNBOOK_WINDOWS.md')
def probe(p, count=False):
    cmd=['ffprobe','-v','error']
    if count: cmd+=['-count_frames']
    return json.loads(command(cmd+['-show_streams','-show_format','-of','json',p]))
def video_info(p, count=False):
    d=probe(p,count); videos=[s for s in d['streams'] if s['codec_type']=='video']
    if len(videos)!=1: fail(f'Expected exactly one video stream: {p}')
    s=videos[0]
    n=s.get('nb_read_frames') if count else s.get('nb_frames')
    return {'width':s['width'],'height':s['height'],
        'fps':float(Fraction(s['avg_frame_rate'])), 'r_fps':float(Fraction(s['r_frame_rate'])),
        'frames':int(n) if n and n!='N/A' else None,
        'duration':float(d['format']['duration']), 'start_time':float(s.get('start_time','0')),
        'pix_fmt':s.get('pix_fmt'), 'stream':s}
def safe_extract(zpath, dest):
    dest=Path(dest); dest.mkdir(parents=True,exist_ok=True)
    extracted=[]
    with zipfile.ZipFile(zpath) as z:
        if len(z.infolist())>100000: fail('Too many archive members')
        if sum(i.file_size for i in z.infolist())>8*1024**3: fail('Archive expansion exceeds 8 GiB')
        for i in z.infolist():
            p=PurePosixPath(i.filename.replace('\\','/'))
            if p.is_absolute() or '..' in p.parts or any(':' in part for part in p.parts): fail('Unsafe archive path')
            if ((i.external_attr>>16)&0o170000)==0o120000: fail('Symlink in archive')
            if i.is_dir() or p.suffix.lower() not in TEXT_EXT: continue
            out=dest.joinpath(*p.parts); out.parent.mkdir(parents=True,exist_ok=True)
            b=z.read(i)
            if out.exists() and out.read_bytes()!=b: fail(f'Conflicting archive member: {p}')
            out.write_bytes(b); extracted.append(out)
    return extracted

def lesson_id(source_name):
    m=re.match(r'(.+?_S\d{2}_\d{2}(?:-\d+)?)(?![\d-])',source_name)
    if not m: fail(f'No unambiguous lesson ID: {source_name}')
    return m.group(1)

def validate_script(d):
    if not isinstance(d,dict): fail('voice_script.json must be an object')
    for k in ('source_name','source_duration','timeline_scale','segments'):
        if k not in d: fail(f'Missing script field: {k}')
    dur=float(d['source_duration']); scale=float(d['timeline_scale'])
    if not math.isfinite(dur) or dur<=0 or scale!=2.0: fail('Only the documented 2x source timeline is supported')
    if not isinstance(d['segments'],list) or not d['segments']: fail('Empty narration')
    ids=set(); previous_end=-1.0
    for i,s in enumerate(d['segments']):
        for k in ('id','start','end','ja'):
            if k not in s: fail(f'Segment {i}: missing {k}')
        a,b=float(s['start']),float(s['end'])
        if not all(math.isfinite(v) for v in (a,b)) or a<0 or b<=a or b>dur+.1: fail(f'Invalid source interval: {s["id"]}')
        if a<previous_end-1e-6: fail(f'Overlapping / unsorted narration intervals: {s["id"]}')
        previous_end=b
        if str(s['id']) in ids: fail('Duplicate segment ID')
        ids.add(str(s['id']))
        text=s.get('ja_for_tts') or s['ja']
        if not isinstance(text,str) or not text.strip(): fail('Empty TTS text')
    return d

def narration_hash(d):
    return jhash({'source_name':d['source_name'],'source_duration':d['source_duration'],
        'timeline_scale':d['timeline_scale'],'segments':d['segments']})

def ass_info(p):
    text=Path(p).read_text(encoding='utf-8-sig')
    def res(k):
        m=re.search(r'^'+k+r'\s*:\s*(\d+)',text,re.M)
        if not m: fail(f'{p}: missing {k}')
        return int(m.group(1))
    lines=[s for s in text.splitlines() if s.startswith('Dialogue:')]
    if not lines: fail(f'{p}: no Dialogue events')
    def sec(t):
        h,m,s=t.strip().split(':'); return int(h)*3600+int(m)*60+float(s)
    events=[]
    for l in lines:
        a=l.split(',',9)
        if len(a)!=10: fail(f'Malformed ASS event: {p}')
        start,end=sec(a[1]),sec(a[2])
        if start<0 or end<=start: fail('Invalid ASS interval')
        events.append((start,end))
    fonts=[]
    for l in text.splitlines():
        if l.startswith('Style:'):
            fields=l.split(','); fonts.append(fields[1].strip())
    return {'width':res('PlayResX'),'height':res('PlayResY'),'events':len(events),
            'max_end':max(b for a,b in events),'fonts':sorted(set(fonts)),
            'times':sorted(set(a for a,b in events))}

def init_project(args):
    need_tools(); root=Path(args.project).resolve()
    if (root/'project.json').exists(): fail('Project already initialized; use a new project directory')
    src=Path(args.sources).resolve()
    if not src.is_dir(): fail('Source directory is missing')
    files=safe_extract(args.assets,root/'assets')
    candidates=[p for p in files if p.name=='voice_script.json']
    by_id={}
    for p in sorted(candidates):
        d=validate_script(readj(p)); lid=lesson_id(d['source_name'])
        if lid in by_id:
            if narration_hash(d)!=narration_hash(readj(by_id[lid])): fail(f'Conflicting scripts for {lid}; select one archive version')
            continue
        by_id[lid]=p
    if not by_id: fail('No voice_script.json found; this ZIP is not the annotation archive')
    cfg=dict(DEFAULTS); cfg['expected_lesson_count']=args.expected_count
    lessons=[]
    for lid,p in sorted(by_id.items()):
        d=readj(p); exact=list(src.rglob(d['source_name']))
        if len(exact)!=1: fail(f'{lid}: expected one exact source filename, got {len(exact)}: {d["source_name"]}')
        v=video_info(exact[0],count=True)
        if (v['width'],v['height'])!=(1920,1080): fail(f'{lid}: expected 1920x1080 source, no automatic resizing')
        if abs(v['fps']-60)>.01 or abs(v['r_fps']-60)>.01: fail(f'{lid}: source is not 60 fps CFR')
        if abs(v['duration']-float(d['source_duration']))>.35: fail(f'{lid}: source duration mismatch')
        if v['frames'] is None or abs(v['frames']/60-v['duration'])>.35: fail(f'{lid}: frame-count / duration mismatch')
        ap=p.parent/'japanese.ass'; sp=p.parent/'screen.json'
        if ap.exists():
            ai=ass_info(ap)
            if (ai['width'],ai['height'])!=(1920,1080) or ai['max_end']>d['source_duration']*2+1: fail(f'{lid}: ASS timeline/resolution mismatch')
        lessons.append({'id':lid,'source_name':d['source_name'],'source_sha256':digest(exact[0]),
            'source_info':{k:v[k] for k in ('width','height','fps','frames','duration','pix_fmt')},
            'voice_script':str(p.relative_to(root)), 'voice_sha256':digest(p),
            'narration_sha256':narration_hash(d),
            'ass':str(ap.relative_to(root)) if ap.exists() else None,
            'ass_sha256':digest(ap) if ap.exists() else None,
            'screen_plan':str(sp.relative_to(root)) if sp.exists() else None,
            'screen_sha256':digest(sp) if sp.exists() else None,
            'source_timeline_scale':2.0,'ass_timebase':'output_seconds',
            'semantic_coverage':'legacy_not_reaudited', 'segments':len(d['segments'])})
    writej(root/'project.json',{'schema':1,'toolkit_version':VERSION,'config':cfg,
        'assets_archive_sha256':digest(args.assets),'lessons':lessons})
    writej(root/'paths.local.json',{'sources':str(src)})
    writej(root/'environment.lock.json',environment())
    print(f'Imported {len(lessons)} lessons. No archive Python code was executed. Fonts were excluded.')
    audit_project(root)

def environment():
    need_tools()
    return {'python':sys.version, 'platform':sys.platform,
        'ffmpeg':command(['ffmpeg','-version']).splitlines()[0],
        'ffprobe':command(['ffprobe','-version']).splitlines()[0],
        'ffmpeg_binary_sha256':digest(shutil.which('ffmpeg')),
        'ffprobe_binary_sha256':digest(shutil.which('ffprobe'))}

def load_project(root):
    root=Path(root).resolve(); p=readj(root/'project.json')
    if p.get('schema')!=1: fail('Unsupported project schema')
    return root,p

def selected(p,ids):
    rows=p['lessons']
    if ids:
        wanted=set(ids.split(',')); rows=[r for r in rows if r['id'] in wanted]
        if wanted-set(r['id'] for r in rows): fail('Unknown lesson ID')
    return rows

def assert_frozen(root,l):
    for pathkey,hashkey in [('voice_script','voice_sha256'),('ass','ass_sha256'),('screen_plan','screen_sha256')]:
        if l.get(pathkey) and digest(root/l[pathkey])!=l[hashkey]: fail(f'{l["id"]}: frozen {pathkey} changed; import a reviewed new project')

def audit_project(root):
    root,p=load_project(root); rows=[]
    for l in p['lessons']:
        reasons=[]
        for k in ('ass','screen_plan'):
            if not l.get(k): reasons.append('MISSING_'+k.upper())
        try: assert_frozen(root,l)
        except Stop as e: reasons.append(str(e))
        rows.append({'id':l['id'],'segments':l['segments'],'renderable_saved_plan':not reasons,
            'semantic_coverage':l['semantic_coverage'],'issues':reasons})
    report={'lessons_found':len(rows),'expected':p['config']['expected_lesson_count'],
        'count_matches':len(rows)==p['config']['expected_lesson_count'],
        'saved_plan_ready':sum(r['renderable_saved_plan'] for r in rows),
        'no_new_translation_or_ocr_performed':True, 'all_screen_text_coverage_verified':False,'lessons':rows}
    writej(root/'reports'/'audit.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='lessons'},ensure_ascii=False))
    return report

def setup_font(root):
    root=Path(root).resolve(); dst=root/'fonts'/FONT_NAME; dst.parent.mkdir(parents=True,exist_ok=True)
    lockpath=ROOT/'font_reference.json'
    if not lockpath.exists(): fail('font_reference.json missing from toolkit')
    lock=readj(lockpath)
    if dst.exists() and digest(dst)==lock['sha256']: return dst
    with urllib.request.urlopen(FONT_URL,timeout=120) as r: b=r.read()
    if hashlib.sha256(b).hexdigest()!=lock['sha256']: fail('Font download hash mismatch')
    dst.write_bytes(b)
    writej(root/'fonts'/'font.lock.json',lock)
    print('Downloaded and hash-verified font on this machine. No font was included in the handoff ZIP.')
    return dst

def write_wave(path,data,sr):
    import numpy as np
    data=np.asarray(data)
    if data.ndim!=1 or not np.isfinite(data).all(): fail('Nonfinite / nonmono audio')
    peak=float(np.max(np.abs(data))) if len(data) else 0
    if peak<1: fail('Silent TTS result')
    if peak>30000: data=data*(30000/peak)
    pcm=np.rint(data).astype('<i2')
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(pcm.tobytes())

def wave_info(path):
    with wave.open(str(path),'rb') as w:
        return {'rate':w.getframerate(),'channels':w.getnchannels(),'width':w.getsampwidth(),'samples':w.getnframes()}

def build_audio(root,p,l):
    import numpy as np, pyopenjtalk
    cfg=p['config']; ver=importlib.metadata.version('pyopenjtalk-plus')
    if ver!=cfg['engine_version']: fail(f'pyopenjtalk-plus version mismatch: {ver}')
    assert_frozen(root,l); d=validate_script(readj(root/l['voice_script'])); sr=cfg['sample_rate']
    directory=root/'audio'/l['id']; directory.mkdir(parents=True,exist_ok=True)
    output=directory/'japanese.wav'; reportpath=directory/'audio_report.json'
    voicepath=Path(os.fsdecode(pyopenjtalk.DEFAULT_HTS_VOICE)); voicehash=digest(voicepath)
    signature=jhash({'voice_script':l['narration_sha256'],'config':cfg,'version':ver,'voice_hash':voicehash,
        'ffmpeg':environment()['ffmpeg_binary_sha256']})
    if output.exists() and reportpath.exists():
        old=readj(reportpath)
        if old.get('signature')==signature and old.get('audio_sha256')==digest(output):
            print(l['id']+': verified audio cache');return
    total=sample(d['source_duration']*2,sr); rows=[]; fitted=[]
    for i,s in enumerate(d['segments']):
        start=sample(s['start']*2,sr); deadline=sample(s['end']*2,sr)
        if i+1<len(d['segments']): deadline=min(deadline,sample(d['segments'][i+1]['start']*2,sr)-sample(cfg['gap_ms']/1000,sr))
        window=deadline-start
        if window<=0: fail('Nonpositive audio window')
        text=s.get('ja_for_tts') or s['ja']
        key=jhash({'text':text,'engine':ver,'voice_hash':voicehash,'speed':1.0,'run_marine':False,'predict_nani':False})
        cache=root/'cache'/'tts'; cache.mkdir(parents=True,exist_ok=True); raw=cache/(key+'.wav')
        if not raw.exists():
            x,rate=pyopenjtalk.tts(text,speed=1.0,run_marine=False,predict_nani=False)
            if rate!=sr: fail('Unexpected TTS sample rate')
            temp=raw.with_suffix('.tmp.wav');write_wave(temp,x,rate);os.replace(temp,raw)
        info=wave_info(raw)
        if (info['rate'],info['channels'],info['width'])!=(sr,1,2): fail('Unexpected raw audio format')
        speed=max(1.0,info['samples']/max(1,window-960))
        if speed>cfg['max_speed']: fail(f'{l["id"]} segment {s["id"]}: required speed {speed:.3f} exceeds {cfg["max_speed"]}; no words were deleted')
        fit=directory/f'{i+1:05d}.wav'
        if speed<=1: shutil.copyfile(raw,fit)
        else:
            command(['ffmpeg','-v','error','-y','-i',raw,'-af',f'atempo={speed:.10f}', '-ar',sr,'-ac',1,'-c:a','pcm_s16le',fit])
        n=wave_info(fit)['samples']
        if n>window: fail(f'{l["id"]} segment {s["id"]}: audio still overflows; nothing was truncated')
        rows.append({'id':s['id'],'start_sample':start,'end_sample':start+n,'deadline_sample':deadline,
            'samples':n,'speed':speed,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'raw_sha256':digest(raw),'fit_sha256':digest(fit)})
        fitted.append(fit)
        print(f'{l["id"]}: {i+1}/{len(d["segments"])}',flush=True)
    tmp=directory/'japanese.partial.wav'; cursor=0
    with wave.open(str(tmp),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(sr)
        for r,f in zip(rows,fitted):
            if r['start_sample']<cursor: fail('Audio overlap detected')
            silence=r['start_sample']-cursor
            while silence:
                n=min(silence,sr*10);out.writeframesraw(b'\0\0'*n);silence-=n
            with wave.open(str(f),'rb') as inp:
                while b:=inp.readframes(sr*10): out.writeframesraw(b)
            cursor=r['end_sample']
        if cursor>total: fail('Audio exceeds lesson duration')
        silence=total-cursor
        while silence:
            n=min(silence,sr*10);out.writeframesraw(b'\0\0'*n);silence-=n
    os.replace(tmp,output)
    writej(reportpath,{'signature':signature,'narration_sha256':l['narration_sha256'],'audio_sha256':digest(output),
        'voice_credit':'Open JTalk / HTS Voice Mei (mei_normal), MMDAgent Project Team / Nagoya Institute of Technology, CC BY 3.0',
        'voice_hash':voicehash,'sample_rate':sr,'total_samples':total,'segment_count':len(rows),'truncated_segments':0,
        'overlapping_segments':0,'segments':rows})

def source_file(root,l,args):
    source_root=Path(args.sources).resolve() if getattr(args,'sources',None) else Path(readj(root/'paths.local.json')['sources'])
    hits=list(source_root.rglob(l['source_name']))
    if len(hits)!=1: fail('Source filename missing or ambiguous: '+l['source_name'])
    if digest(hits[0])!=l['source_sha256']: fail('Source SHA-256 changed: '+l['id'])
    return hits[0]

def final_approval(root,l):
    path=root/'approvals'/(l['id']+'.json')
    if not path.exists(): fail(l['id']+': final coverage approval missing; use replay mode for existing-plan reproduction')
    a=readj(path)
    for k in ('source_sha256','ass_sha256','voice_sha256','screen_sha256'):
        if a.get(k)!=l[k]: fail(l['id']+': approval hash mismatch')
    if a.get('screen_coverage_complete') is not True or a.get('translation_review_complete') is not True or a.get('unresolved_items')!=[]:
        fail(l['id']+': content coverage not approved')
    if not a.get('reviewer') or not a.get('evidence'): fail('Approval needs provenance and evidence, not invented completion')

def render_one(root,p,l,args):
    need_tools(); assert_frozen(root,l)
    if not l['ass'] or not l['screen_plan']: fail(l['id']+': missing screen/ASS plan; never replace with plain subtitles')
    if args.mode=='final': final_approval(root,l)
    font=root/'fonts'/FONT_NAME
    if not font.exists(): fail('Run font command before rendering')
    if digest(font)!=readj(ROOT/'font_reference.json')['sha256']: fail('Font hash mismatch')
    src=source_file(root,l,args); cfg=p['config']; audio=root/'audio'/l['id']/'japanese.wav'
    arpath=audio.with_name('audio_report.json')
    if not audio.exists() or not arpath.exists(): fail('Run synthesize first: '+l['id'])
    ar=readj(arpath)
    if ar['narration_sha256']!=l['narration_sha256'] or ar['audio_sha256']!=digest(audio): fail('Stale or unverified audio')
    ai=ass_info(root/l['ass']); vi=video_info(src)
    if (ai['width'],ai['height'])!=(vi['width'],vi['height']): fail('ASS resolution mismatch')
    output=root/'output'/args.mode/(l['id']+'_japanese.mp4');output.parent.mkdir(parents=True,exist_ok=True)
    done=output.with_suffix('.verified.json')
    signature=jhash({'lesson':l,'config':cfg,'audio':ar['audio_sha256'],'font':digest(font),'env':environment(),'mode':args.mode})
    if output.exists() and done.exists():
        r=readj(done)
        if r.get('signature')==signature and r.get('output_sha256')==digest(output):
            print(l['id']+': verified render cache');return
    job=root/'work'/l['id'];job.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(root/l['ass'],job/'overlay.ass')
    (job/'fonts').mkdir(exist_ok=True);shutil.copyfile(font,job/'fonts'/FONT_NAME)
    tmp=output.with_name(output.stem+'.partial.mp4')
    argv=['ffmpeg','-hide_banner','-y','-i',src,'-i',audio,
        '-map','0:v:0','-map','1:a:0','-map_metadata','-1',
        '-vf','setpts=2*(PTS-STARTPTS),ass=filename=overlay.ass:fontsdir=fonts',
        '-r','30','-fps_mode','passthrough','-c:v','libx264','-crf',cfg['crf'],'-preset',cfg['preset'],
        '-threads',cfg['threads'],'-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000',
        '-metadata:s:a:0','language=jpn','-metadata:s:a:0','title=Japanese narration - Open JTalk Mei',
        '-movflags','+faststart',tmp]
    s=vi['stream']
    opts={'color_range':'-color_range','color_space':'-colorspace','color_transfer':'-color_trc','color_primaries':'-color_primaries'}
    for k,flag in opts.items():
        if s.get(k) not in (None,'unknown','unspecified'): argv[-1:-1]=[flag,s[k]]
    command(argv,cwd=job,logfile=root/'logs'/(l['id']+'_encode.log'))
    command(['ffmpeg','-v','error','-xerror','-i',tmp,'-map','0:v:0','-map','0:a:0','-f','null','-'],logfile=root/'logs'/(l['id']+'_decode.log'))
    out=video_info(tmp,count=True)
    source_count=l['source_info']['frames']
    if out['frames']!=source_count: fail(f'Frame loss / duplication: {l["id"]}: {source_count} -> {out["frames"]}')
    if (out['width'],out['height'])!=(1920,1080) or abs(out['fps']-30)>.02: fail('Output resolution/fps mismatch')
    if abs(out['duration']-l['source_info']['duration']*2)>.5: fail('Output duration mismatch')
    os.replace(tmp,output)
    report={'signature':signature,'output_sha256':digest(output),'source_sha256':l['source_sha256'],
        'frame_count':out['frames'],'width':out['width'],'height':out['height'],'fps':out['fps'],
        'full_decode_passed':True,'narration_segments':ar['segment_count'], 'mode':args.mode,
        'all_screen_text_coverage_verified':args.mode=='final', 'voice_credit':ar['voice_credit']}
    writej(done,report)
    writej(output.with_suffix('.credits.json'),{'credit':ar['voice_credit'],'notes':'Existing burned-in credits, if any, are inherited; they are not silently removed.'})
    print(str(output))

def loop(args,fn):
    root,p=load_project(args.project);errors=[]
    for l in selected(p,args.lesson):
        try: fn(root,p,l)
        except Exception as e:
            errors.append({'id':l['id'],'error':str(e)});print('STOP '+l['id']+': '+str(e),file=sys.stderr)
    writej(root/'reports'/(args.action+'_errors.json'),errors)
    if errors: fail(f'{len(errors)} lesson(s) blocked; successful independent outputs retained')

def video_hash(path):
    return command(['ffmpeg','-v','error','-i',path,'-map','0:v:0','-c:v','copy','-f','hash','-hash','sha256','-']).strip()

def revoice(args):
    need_tools(); inp=Path(args.video).resolve(); aud=Path(args.audio).resolve(); out=Path(args.out).resolve()
    if out==inp or out.exists(): fail('Revoice output must be a new path')
    vd=video_info(inp)['duration']; ad=float(probe(aud)['format']['duration'])
    if abs(vd-ad)>.5: fail('Audio/video duration mismatch; no truncation or retiming permitted')
    out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_name(out.stem+'.partial.mp4')
    command(['ffmpeg','-v','error','-y','-i',inp,'-i',aud,'-map','0:v:0','-map','1:a:0','-map_metadata','0',
        '-c:v','copy','-c:a','aac','-b:a','192k','-metadata:s:a:0','language=jpn','-movflags','+faststart',tmp])
    if video_hash(inp)!=video_hash(tmp): fail('Encoded video payload changed during revoice')
    command(['ffmpeg','-v','error','-xerror','-i',tmp,'-f','null','-'])
    os.replace(tmp,out);writej(out.with_suffix('.verified.json'),{'video_payload_unchanged':True,'output_sha256':digest(out)})

def pack(args):
    root,p=load_project(args.project);out=Path(args.out).resolve()
    if out.exists(): fail('Pack output already exists')
    members={}
    for f in ROOT.rglob('*'):
        if f.is_file() and f.suffix.lower() not in FONT_EXT and '__pycache__' not in f.parts and f.suffix.lower() not in {'.zip','.pyc'}:
            if f.stat().st_size<20*1024**2: members['toolkit/'+str(f.relative_to(ROOT)).replace('\\','/')]=f
    for base in ['assets','audio','approvals','reports']:
        for f in (root/base).rglob('*'):
            if not f.is_file() or f.suffix.lower() in FONT_EXT: continue
            if base=='audio' and f.name not in ('japanese.wav','audio_report.json'): continue
            members['project/'+str(f.relative_to(root)).replace('\\','/')]=f
    members['project/project.json']=root/'project.json'
    manifest={name:digest(f) for name,f in sorted(members.items())}
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for name,f in sorted(members.items()):
            i=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED
            with z.open(i,'w',force_zip64=True) as w, f.open('rb') as r: shutil.copyfileobj(r,w,1<<20)
        i=zipfile.ZipInfo('SHA256.json',date_time=(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(i,json.dumps(manifest,ensure_ascii=False,indent=2).encode())
    with zipfile.ZipFile(out) as z:
        if z.testzip(): fail('Packed ZIP CRC verification failed')
    print(str(out));print('sha256 '+digest(out))

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='action',required=True)
    q=sub.add_parser('init');q.add_argument('--assets',required=True);q.add_argument('--sources',required=True);q.add_argument('--project',default='project');q.add_argument('--expected-count',type=int,default=40)
    for name in ('audit','font','synthesize','render'):
        q=sub.add_parser(name);q.add_argument('--project',default='project')
        if name in ('synthesize','render'): q.add_argument('--lesson',help='Comma-separated exact lesson IDs')
        if name=='render': q.add_argument('--sources');q.add_argument('--mode',choices=['replay','final'],default='replay')
    q=sub.add_parser('revoice');q.add_argument('--video',required=True);q.add_argument('--audio',required=True);q.add_argument('--out',required=True)
    q=sub.add_parser('pack');q.add_argument('--project',default='project');q.add_argument('--out',required=True)
    args=ap.parse_args()
    try:
        if args.action=='init': init_project(args)
        elif args.action=='audit': audit_project(args.project)
        elif args.action=='font': setup_font(args.project)
        elif args.action=='synthesize': loop(args,build_audio)
        elif args.action=='render': loop(args,lambda r,p,l:render_one(r,p,l,args))
        elif args.action=='revoice': revoice(args)
        elif args.action=='pack': pack(args)
    except (Stop,OSError,ValueError,zipfile.BadZipFile) as e:
        print('ERROR: '+str(e),file=sys.stderr);return 2
    return 0
if __name__=='__main__': sys.exit(main())
