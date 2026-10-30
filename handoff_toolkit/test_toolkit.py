import argparse, hashlib, json, os, shutil, tempfile, unittest, wave, zipfile
from pathlib import Path
import toolkit as t

ASS='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK JP,42,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,40,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.80,Default,,0,0,0,,日本語表示のテスト
'''

def script():
    return {'course':'demo','source_name':'demo_S01_01_test.mp4','source_duration':2.,'timeline_scale':2.,
            'segments':[{'id':1,'start':.1,'end':1.8,'ja':'こんにちは。','ja_for_tts':'こんにちは。','caption_ids':[1]}]}

class Contracts(unittest.TestCase):
    def test_timebase(self):
        self.assertEqual(t.sample(.1,48000),4800)
        self.assertEqual(t.sample(5.25*2,48000),504000)
        self.assertEqual(t.sample(.00003125,48000),2)
    def test_source_ids(self):
        self.assertEqual(t.lesson_id('demo_S02_03-1題名.mp4'),'demo_S02_03-1')
        self.assertNotEqual(t.lesson_id('demo_S02_03-1題名.mp4'),t.lesson_id('demo_S02_03-2題名.mp4'))
    def test_invalid_script(self):
        d=script();d['segments'][0]['end']=.05
        with self.assertRaises(t.Stop):t.validate_script(d)
        d=script();d['timeline_scale']=1
        with self.assertRaises(t.Stop):t.validate_script(d)
    def test_overlap_rejected(self):
        d=script();d['segments'].append({'id':2,'start':1.,'end':1.9,'ja':'重複'})
        with self.assertRaises(t.Stop):t.validate_script(d)
    def test_duplicate_ids(self):
        d=script();d['segments'][0]['end']=.5;d['segments'].append({'id':1,'start':.6,'end':1.8,'ja':'同一ID'})
        with self.assertRaises(t.Stop):t.validate_script(d)
    def test_narration_fingerprint(self):
        a=script();b=script();b['voice_credit']='different engine'
        self.assertEqual(t.narration_hash(a),t.narration_hash(b))
        b['segments'][0]['ja_for_tts']='別の本文'
        self.assertNotEqual(t.narration_hash(a),t.narration_hash(b))
    def test_zip_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../outside.txt','bad')
            with self.assertRaises(t.Stop):t.safe_extract(p,Path(d)/'out')
    def test_font_and_code_not_imported(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('fonts/a.otf',b'not-a-font');z.writestr('danger.py','raise RuntimeError()');z.writestr('data/a.json','{}')
            found=t.safe_extract(p,Path(d)/'out')
            self.assertEqual([f.name for f in found],['a.json'])
    def test_ass_not_rescaled(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.ass';p.write_text(ASS,encoding='utf8');h=t.digest(p);a=t.ass_info(p)
            self.assertEqual(a['max_end'],1.8);self.assertEqual(a['width'],1920);self.assertEqual(t.digest(p),h)
    def test_final_requires_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(t.Stop):t.final_approval(Path(d),{'id':'demo_S01_01'})
    def test_pcm(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.wav';t.write_wave(p,np.array([0.,35000.,-35000.,0.]),48000)
            self.assertEqual(t.wave_info(p)['samples'],4)
            with wave.open(str(p),'rb') as w:
                values=np.frombuffer(w.readframes(4),dtype='<i2')
            self.assertLessEqual(int(abs(values).max()),30000)
    def test_silent_tts_rejected(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(t.Stop):t.write_wave(Path(d)/'a.wav',np.zeros(5),48000)

@unittest.skipUnless(os.environ.get('MEDIA_TESTS')=='1','Set MEDIA_TESTS=1 for real TTS and FFmpeg integration')
class Media(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);sources=base/'sources';sources.mkdir();p=base/'project'
            t.command(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=gray:size=1920x1080:rate=60:duration=2',
                       '-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t','2','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac',sources/'demo_S01_01_test.mp4'])
            zpath=base/'assets.zip'
            with zipfile.ZipFile(zpath,'w') as z:
                z.writestr('lessons/demo_S01_01/voice_script.json',json.dumps(script(),ensure_ascii=False))
                z.writestr('lessons/demo_S01_01/japanese.ass',ASS)
                z.writestr('lessons/demo_S01_01/screen.json','{"test_fixture":true}')
            t.init_project(argparse.Namespace(project=str(p),assets=str(zpath),sources=str(sources),expected_count=1))
            # Dependency downloaded only for this synthetic test. It is never packaged.
            t.setup_font(p);root,project=t.load_project(p);lesson=project['lessons'][0]
            t.build_audio(root,project,lesson)
            t.build_audio(root,project,lesson)  # verifies cache path
            audio=root/'audio'/lesson['id']/'japanese.wav'
            ar=t.readj(audio.with_name('audio_report.json'))
            self.assertEqual(ar['segment_count'],1);self.assertEqual(ar['truncated_segments'],0)
            t.render_one(root,project,lesson,argparse.Namespace(sources=str(sources),mode='replay'))
            output=root/'output'/'replay'/(lesson['id']+'_japanese.mp4')
            report=t.readj(output.with_suffix('.verified.json'))
            self.assertEqual(report['frame_count'],120)
            self.assertFalse(report['all_screen_text_coverage_verified'])
            revoiced=base/'revoiced.mp4'
            t.revoice(argparse.Namespace(video=str(output),audio=str(audio),out=str(revoiced)))
            self.assertEqual(t.video_hash(output),t.video_hash(revoiced))
            combined=base/'combined.zip';t.pack(argparse.Namespace(project=str(root),out=str(combined)))
            with zipfile.ZipFile(combined) as z:
                self.assertIsNone(z.testzip());self.assertFalse(any(Path(n).suffix.lower() in t.FONT_EXT for n in z.namelist()))
                self.assertIn('project/project.json',z.namelist())
                self.assertIn('project/audio/demo_S01_01/japanese.wav',z.namelist())

if __name__=='__main__':unittest.main(verbosity=2)
