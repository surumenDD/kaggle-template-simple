from pathlib import Path
root=Path(__file__).resolve().parent
p=root/'toolkit.py'
s=p.read_text(encoding='utf-8')
old="        if r.returncode: fail(f'Command failed ({r.returncode}); see {logfile}')"
new="        if r.returncode:\n            tail=Path(logfile).read_text(encoding='utf-8',errors='replace')[-8000:]\n            fail(f'Command failed ({r.returncode}); see {logfile}\\n'+tail)"
assert old in s, 'Expected diagnostic code not found'
s=s.replace(old,new,1)
old="'-r','30','-fps_mode','passthrough'"
new="'-r','30','-fps_mode','cfr'"
assert old in s, 'Expected frame-rate code not found'
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
p=root/'build_docs.py'
s=p.read_text(encoding='utf-8')
old="numpy==2.2.6\\npyopenjtalk-plus==0.4.1.post8\\n"
new="numpy==2.2.6\\npyopenjtalk-plus==0.4.1.post8\\nsudachipy==0.7.0\\nsudachidict_core==20261015\\n"
assert old in s, 'Expected dependency list not found'
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('Applied verified release changes: diagnostics, CFR with frame-count guard, pinned pronunciation dependencies.')
