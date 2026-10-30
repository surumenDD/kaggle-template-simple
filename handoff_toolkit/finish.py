#!/usr/bin/env python3
"""One command to reproduce existing translation plans; does NOT invent missing plans."""
from __future__ import annotations
import argparse,json,shutil,sys,wave
from pathlib import Path
import toolkit as t

def import_audio(root,project,audio_dir,scripts_dir):
    results=[]
    for l in project['lessons']:
        audios=[x for x in Path(audio_dir).rglob(l['id']+'_mei.wav') if x.is_file()]
        scripts=[x for x in Path(scripts_dir).rglob(l['id']+'_voice_script.json') if x.is_file()]
        if not audios and not scripts:continue
        if len(audios)!=1 or len(scripts)!=1:
            results.append({'id':l['id'],'status':'skipped','reason':'Ambiguous or incomplete audio/script pair'});continue
        d=t.validate_script(t.readj(scripts[0]))
        if t.narration_hash(d)!=l['narration_sha256']:
            results.append({'id':l['id'],'status':'skipped','reason':'Narration content/time differs from frozen imported script'});continue
        info=t.wave_info(audios[0]);expected=t.sample(d['source_duration']*2,48000)
        if (info['rate'],info['channels'],info['width'])!=(48000,1,2) or abs(info['samples']-expected)>24000:
            results.append({'id':l['id'],'status':'skipped','reason':'PCM format or duration mismatch'});continue
        # A paired filename and matching script are provenance, not proof of linguistic accuracy.
        # Preserve the exact waveform. Never resynthesize a verified provided pair automatically.
        dest=root/'audio'/l['id'];dest.mkdir(parents=True,exist_ok=True)
        wav=dest/'japanese.wav';shutil.copyfile(audios[0],wav)
        t.writej(dest/'audio_report.json',{'signature':'imported_existing_pair',
            'narration_sha256':l['narration_sha256'],'audio_sha256':t.digest(wav),
            'paired_script_sha256':t.digest(scripts[0]), 'sample_rate':48000,'total_samples':info['samples'],
            'segment_count':len(d['segments']),'voice_credit':d.get('voice_credit','See original voice documentation'),
            'provenance':'Existing paired audio/script supplied by user; waveform timing/content not independently reaudited',
            'imported':True,'new_tts_generation':False})
        results.append({'id':l['id'],'status':'imported','audio_sha256':t.digest(wav)})
    t.writej(root/'reports'/'audio_import.json',results)
    return results

def valid_audio(root,l):
    wav=root/'audio'/l['id']/'japanese.wav';report=wav.with_name('audio_report.json')
    if not wav.exists() or not report.exists():return False
    r=t.readj(report)
    return r.get('audio_sha256')==t.digest(wav) and r.get('narration_sha256')==l['narration_sha256']

def run(args):
    root=Path(args.project).resolve()
    if not (root/'project.json').exists():
        if not args.assets or not args.sources:t.fail('First run requires --assets and --sources')
        t.init_project(argparse.Namespace(project=str(root),assets=args.assets,sources=args.sources,expected_count=args.expected_count))
    root,p=t.load_project(root)
    if args.sources:t.writej(root/'paths.local.json',{'sources':str(Path(args.sources).resolve())})
    if bool(args.audio_dir)!=bool(args.paired_scripts):t.fail('--audio-dir and --paired-scripts must be supplied together')
    if args.audio_dir:import_audio(root,p,args.audio_dir,args.paired_scripts)
    audit=t.audit_project(root)
    if not audit['count_matches']:t.fail('Lesson count differs from expected; do not call a partial dataset complete')
    t.setup_font(root)
    results=[]
    for l in t.selected(p,args.lesson):
        r={'id':l['id'],'audio':'pending','video':'pending'}
        try:
            t.assert_frozen(root,l)
            if not valid_audio(root,l):t.build_audio(root,p,l)
            r['audio']='verified_file_available'
            if args.audio_only:
                r['video']='not_requested'
            elif not l['ass'] or not l['screen_plan']:
                r['video']='blocked_missing_screen_plan'
            else:
                t.render_one(root,p,l,argparse.Namespace(sources=args.sources,mode=args.mode));r['video']='rendered_'+args.mode
        except Exception as e:
            r['error']=str(e);r['video']='blocked';print(l['id']+': '+str(e),file=sys.stderr)
        results.append(r)
        # Atomic, durable progress after EACH lesson, including errors.
        t.writej(root/'reports'/'finish_status.json',{'toolkit_version':t.VERSION,'mode':args.mode,
            'scope':'selected_lessons' if args.lesson else 'all_lessons','lessons':results,
            'all_requested_videos_rendered':all(x['video']=='rendered_'+args.mode for x in results) and len(results)==len(t.selected(p,args.lesson)),
            'all_course_content_fully_reviewed':args.mode=='final' and not args.lesson and len(results)==p['config']['expected_lesson_count'] and all(x['video']=='rendered_final' for x in results)})
    blocked=[r for r in results if 'error' in r or r['video'].startswith('blocked')]
    print(f'Processed {len(results)} lesson(s); blocked {len(blocked)}. See project/reports/finish_status.json')
    return 2 if blocked else 0

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--assets');a.add_argument('--sources');a.add_argument('--project',default='project')
    a.add_argument('--audio-dir');a.add_argument('--paired-scripts');a.add_argument('--expected-count',type=int,default=40)
    a.add_argument('--lesson');a.add_argument('--audio-only',action='store_true')
    a.add_argument('--mode',choices=['replay','final'],default='replay')
    try:return run(a.parse_args())
    except Exception as e:print('ERROR: '+str(e),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
