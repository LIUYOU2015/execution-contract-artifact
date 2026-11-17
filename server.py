"""Pinned native lifecycle API, with an ownership-only Docker perimeter.

The perimeter is installed BEFORE importing lifecycle/main, because constructor
restore scans otherwise see foreign resources. No cancellation repair is added.
"""
from __future__ import annotations
import argparse,os,sys,json,subprocess,uuid,functools
from pathlib import Path
from common import *
sys.path.insert(0,str(REPO/'server'))
class API:
 def __init__(self,raw,owner):self.raw,self.owner=raw,owner;self.exec_ids=set()
 def __getattr__(self,k):
  if k in ['kill','stop','start','pause','unpause','restart','put_archive','exec_create','rename','update_container']:
   def call(*args,**kwargs):
    ident=args[0] if args else kwargs.get('container')
    obj=self.owner.check(ident,mutation=True,operation=k);self.owner.events('docker_'+k+'_begin',container_id=obj['Id'])
    value=getattr(self.raw,k)(*args,**kwargs)
    if k=='exec_create':self.exec_ids.add(value['Id'])
    self.owner.events('docker_'+k+'_end',container_id=obj['Id']);return value
   return call
  if k in ['exec_start','exec_resize']:
   def call(*a,**kw):
    ident=a[0] if a else kw.get('exec_id')
    if ident not in self.exec_ids:raise PermissionError('unowned exec refused')
    return getattr(self.raw,k)(*a,**kw)
   return call
  if k in ['prune_containers','prune_volumes','create_volume','remove_volume','prune_networks','create_network','remove_network','commit','build','import_image','prune_images','pull','push','load_image','remove_image','tag','import_image_from_data','import_image_from_file']:
   raise PermissionError('operation outside C-01 scope:'+k)
  return getattr(self.raw,k)
 def create_host_config(self,**kw):
  if kw.get('mem_limit') is not None:kw['memswap_limit']=kw['mem_limit']
  return self.raw.create_host_config(**kw)
 def containers(self,*a,**kw):kw['filters']=self.owner.filters(kw.get('filters'));return self.raw.containers(*a,**kw)
 def create_container(self,**kw):
  labels=kw.get('labels') or {}
  if labels.get(STUDY_KEY)!=self.owner.study or not labels.get(TRIAL_KEY):raise PermissionError('missing exact study/trial labels')
  if kw.get('image') not in [TASK_IMAGE,EXECD_IMAGE]:raise PermissionError('unapproved image')
  role=labels.get(ROLE_KEY)
  expected={'target':(1_000_000_000,256*1024**2),'sentinel':(100_000_000,128*1024**2),'helper':(250_000_000,128*1024**2)}
  if role not in expected:raise PermissionError('unknown container role')
  host=kw.get('host_config') or {};mem=host.get('Memory',0);cpu=host.get('NanoCpus',0)
  if (cpu,mem)!=expected[role]:raise PermissionError('role-specific quota mismatch')
  if not 0<mem<=256*1024**2 or not 0<cpu<=1_000_000_000 or host.get('PidsLimit')!=64:raise PermissionError('container quota mismatch')
  if host.get('MemorySwap')!=mem:raise PermissionError('swap quota mismatch')
  count=len(self.raw.containers(all=True,filters={'label':f'{STUDY_KEY}={self.owner.study}'}))
  if count>=3:raise PermissionError('C-01 capacity exceeded')
  same_role=self.raw.containers(all=True,filters={'label':[f'{STUDY_KEY}={self.owner.study}',f'{ROLE_KEY}={role}']})
  if same_role:raise PermissionError('one-container-per-role capacity exceeded')
  if role!='helper':TRIAL_CONTEXT.set(labels[TRIAL_KEY])
  self.owner.events('docker_create_begin',trial=labels[TRIAL_KEY],role=labels.get(ROLE_KEY),name=kw.get('name'),limits=host)
  v=self.raw.create_container(**kw);self.owner.identities[v['Id']]=(labels[TRIAL_KEY],labels.get(ROLE_KEY));self.owner.events('docker_create_end',trial=labels[TRIAL_KEY],container_id=v['Id']);return v
 def remove_container(self,container,*a,**kw):
  obj=self.owner.check(container,mutation=True,operation='remove');labels=obj.get('Config',{}).get('Labels') or {}
  self.owner.events('docker_remove_begin',container_id=obj['Id'],trial=labels.get(TRIAL_KEY),role=labels.get(ROLE_KEY))
  v=self.raw.remove_container(container,*a,**kw)
  self.owner.events('docker_remove_end',container_id=obj['Id'],trial=labels.get(TRIAL_KEY),role=labels.get(ROLE_KEY));return v
class Containers:
 def __init__(self,raw,owner):self.raw,self.owner=raw,owner
 def get(self,ident):obj=self.raw.get(ident);self.owner.check(obj.id);return obj
 def list(self,*a,**kw):kw['filters']=self.owner.filters(kw.get('filters'));return self.raw.list(*a,**kw)
 def create(self,**kw):
  if kw.get('image')!=EXECD_IMAGE:raise PermissionError('only official extraction helper uses high-level create')
  kw.update(name='c01-helper-'+uuid.uuid4().hex[:16],labels={STUDY_KEY:self.owner.study,TRIAL_KEY:TRIAL_CONTEXT.get() or 'setup-helper-'+uuid.uuid4().hex,ROLE_KEY:'helper'},nano_cpus=250_000_000,mem_limit=128*1024**2,memswap_limit=128*1024**2,pids_limit=64)
  return self.raw.create(**kw)
class NoVolumes:
 def __getattr__(self,k):raise PermissionError('no volume operation authorized')
class Scoped:
 def __init__(self,raw,study,events):
  self.raw,self.study,self.events=raw,study,events;self.identities={}
  self.original_api=raw.api
  raw.api=API(raw.api,self)
  self.api=raw.api;self.containers=Containers(raw.containers,self);self.volumes=NoVolumes()
 def __getattr__(self,k):return getattr(self.raw,k)
 def check(self,ident,*,mutation=False,operation=None):
  obj=self.original_api.inspect_container(ident);lab=obj.get('Config',{}).get('Labels') or {}
  expected=(lab.get(TRIAL_KEY),lab.get(ROLE_KEY))
  if lab.get(STUDY_KEY)!=self.study or not expected[0] or expected[1] not in ['target','sentinel','helper']:raise PermissionError('foreign or incomplete container ownership refused')
  if self.identities.get(obj['Id'])!=expected:raise PermissionError('unregistered/replaced container identity refused')
  if mutation and TRIAL_CONTEXT.get() is not None and TRIAL_CONTEXT.get()!=expected[0]:raise PermissionError('cross-trial mutation refused')
  if mutation and expected[1]=='sentinel' and operation in ['kill','stop','pause','unpause','restart','rename','update_container','remove'] and ACTOR.get()!='admin-sentinel-final':raise PermissionError('sentinel lifecycle mutation refused')
  return obj
 def filters(self,f=None):
  out=dict(f or {});labels=out.get('label',[]);labels=[labels] if isinstance(labels,str) else list(labels)
  out['label']=labels+[f'{STUDY_KEY}={self.study}'];return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run-dir',type=Path,required=True);ap.add_argument('--study',required=True);ap.add_argument('--port',type=int,required=True);a=ap.parse_args();a.run_dir.mkdir(parents=True,exist_ok=True)
 events=Events(a.run_dir/'server-events.jsonl')
 config=a.run_dir/'server.toml'
 config.write_text(f'''[server]\nhost="127.0.0.1"\nport={a.port}\napi_key="c01-local-test-only"\nthread_pool_size=16\n[runtime]\ntype="docker"\nexecd_image="{EXECD_IMAGE}"\n[docker]\nnetwork_mode="bridge"\napi_timeout=10\npublish_host="127.0.0.1"\nhost_ip="127.0.0.1"\npids_limit=64\n[store]\npath="{a.run_dir/'server.sqlite'}"\n''')
 os.environ['SANDBOX_CONFIG_PATH']=str(config)
 import docker
 host=json.loads(subprocess.check_output(['docker','context','inspect'],text=True))[0]['Endpoints']['docker']['Host']
 raw=docker.DockerClient(base_url=host,timeout=10);raw.ping();scoped=Scoped(raw,a.study,events)
 def factory(**kwargs):return scoped
 docker.from_env=factory
 # These path/observation hooks are installed before native service construction.
 import opensandbox_server.services.docker.metadata as meta
 meta.DEFAULT_STORE_DIR=a.run_dir/'metadata'
 from opensandbox_server.services.docker.docker_service import DockerSandboxService
 expire=DockerSandboxService._expire_sandbox
 @functools.wraps(expire)
 def observed_expire(self,sandbox_id,*args,**kwargs):
  token=ACTOR.set('expiry_timer');events('expiry_timer_enter',sandbox_id=sandbox_id)
  try:return expire(self,sandbox_id,*args,**kwargs)
  finally:events('expiry_timer_exit',sandbox_id=sandbox_id);ACTOR.reset(token)
 DockerSandboxService._expire_sandbox=observed_expire
 from opensandbox_server.main import app
 @app.middleware('http')
 async def request_log(request,call_next):
  actor=request.headers.get('x-c01-actor','unspecified');token=ACTOR.set(actor);trialtoken=TRIAL_CONTEXT.set(request.headers.get('x-c01-trial'))
  events('http_begin',method=request.method,path=request.url.path,trial=request.headers.get('x-c01-trial'))
  try:
   res=await call_next(request);events('http_end',method=request.method,path=request.url.path,status=res.status_code,trial=request.headers.get('x-c01-trial'));return res
  finally:ACTOR.reset(token);TRIAL_CONTEXT.reset(trialtoken)
 events('server_start',source_sha=SOURCE_SHA,ownership_only_perimeter=True,ttl_observation_wrapper=True)
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=a.port,log_level='info',access_log=False,timeout_graceful_shutdown=10)
if __name__=='__main__':main()
