from __future__ import annotations
import json,time,threading,contextvars
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent/'cancellation-pilot/upstream/opensandbox/repo'
SOURCE_SHA='e654726234172564860a76b82d2b26909bbf4aa8'
TASK_IMAGE='python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159'
EXECD_IMAGE='opensandbox/execd@sha256:6cf7dba2f21f0b536e100563d841ac58a9f31c2b0a081b7ac76796a24d6f47e2'
STUDY_KEY='research.codex.c01_study';TRIAL_KEY='research.codex.c01_trial';ROLE_KEY='research.codex.c01_role'
ACTOR=contextvars.ContextVar('c01_actor',default='background')
TRIAL_CONTEXT=contextvars.ContextVar('c01_trial_context',default=None)
class Events:
 def __init__(self,path):self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock()
 def __call__(self,event,**data):
  row={'event':event,'monotonic_ns':time.monotonic_ns(),'wall_time_ns':time.time_ns(),'actor':ACTOR.get(),**data}
  with self.lock:
   with self.path.open('a') as f:f.write(json.dumps(row,sort_keys=True,default=str)+'\n')
  return row

def dump(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True,default=str)+'\n')
