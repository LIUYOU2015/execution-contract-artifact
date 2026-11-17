"""C-01 native HTTP lost-reply experiment. --help/import have no native effects."""
from __future__ import annotations
import argparse,asyncio,hashlib,json,os,random,re,socket,subprocess,sys,time,traceback
from pathlib import Path
from datetime import datetime,timezone,timedelta
from dataclasses import dataclass,field
from aiohttp import web,ClientSession,ClientTimeout
import httpx,docker
from common import *
sys.path.insert(0,str(REPO/'sdks/sandbox/python/src'))
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig
from opensandbox.models.sandboxes import PlatformSpec

def port():
 s=socket.socket();s.bind(('127.0.0.1',0));v=s.getsockname()[1];s.close();return v

def utc_seconds(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()

@dataclass
class TrialGate:
 trial:str;arm:str;gate:asyncio.Event=field(default_factory=asyncio.Event);release:asyncio.Event=field(default_factory=asyncio.Event)
 creates:list=field(default_factory=list);requests:list=field(default_factory=list);endpoints:list=field(default_factory=list);downstream_transport:object=None

class Proxy:
 def __init__(self,upstream,out,events):self.upstream,self.out,self.events=upstream,out,events;self.active={};self.counter=0;self.inflight_creates={}
 async def start(self):
  self.client=ClientSession(timeout=ClientTimeout(total=120));app=web.Application();app.router.add_route('*','/{path:.*}',self.handle)
  self.runner=web.AppRunner(app,access_log=None);await self.runner.setup();self.port=port();await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
 async def close(self):
  for g in self.active.values():g.release.set()
  await self.runner.cleanup();await self.client.close()
 async def handle(self,request):
  self.counter+=1;n=self.counter;actor=request.headers.get('x-c01-actor','sdk');trial=request.headers.get('x-c01-trial','unknown');g=self.active.get(trial)
  data=await request.read();d=self.out/'http';d.mkdir(exist_ok=True);(d/f'{n:05d}-request.bin').write_bytes(data)
  row=self.events('proxy_request',request_no=n,method=request.method,path=request.path_qs,trial=trial,request_actor=actor)
  if g:g.requests.append(row)
  if g and g.arm=='known_id_cancel' and request.method=='GET' and '/endpoints/' in request.path and actor=='sdk':
   g.endpoints.append(row);self.events('known_id_gate_reached',trial=trial,path=request.path);g.gate.set();await g.release.wait()
   # SDK endpoint request is gone. Do not contact backend after it settles.
   return web.Response(status=499,text='C01 gate released after SDK settled')
  headers={k:v for k,v in request.headers.items() if k.lower() not in ['host','connection','content-length','transfer-encoding']}
  is_create=request.method=='POST' and request.path.rstrip('/').endswith('/sandboxes')
  if is_create:self.inflight_creates[n]={'trial':trial,'started_monotonic_ns':row['monotonic_ns']}
  async with self.client.request(request.method,self.upstream+request.path_qs,data=data,headers=headers) as upstream:
   body=await upstream.read()
   if is_create:self.inflight_creates.pop(n,None)
   (d/f'{n:05d}-response.bin').write_bytes(body)
   rec=self.events('proxy_upstream_response',request_no=n,method=request.method,path=request.path,trial=trial,status=upstream.status,bytes=len(body))
   dump(d/f'{n:05d}-metadata.json',rec)
   if g and request.method=='POST' and request.path.rstrip('/').endswith('/sandboxes'):
    try:payload=json.loads(body)
    except Exception:payload=None
    g.creates.append({'response':rec,'body':payload})
    if g.arm=='lost_id_cancel' and upstream.status==202:
     g.downstream_transport=request.transport;self.events('lost_id_gate_reached',trial=trial,response_headers_sent=False,response_body_sent=False);g.gate.set();await g.release.wait()
     self.events('lost_id_downstream_state_at_release',trial=trial,transport_closing_or_gone=request.transport is None or request.transport.is_closing())
   self.events('proxy_response_released',request_no=n,trial=trial,method=request.method,path=request.path)
   rh={k:v for k,v in upstream.headers.items() if k.lower() not in ['content-length','transfer-encoding','connection','content-encoding']}
   return web.Response(status=upstream.status,body=body,headers=rh)

class Experiment:
 def __init__(self,args):
  self.args=args;self.out=args.out.resolve();self.out.mkdir(parents=True,exist_ok=False);self.study=args.run_id;self.events=Events(self.out/'events.jsonl');self.sentinel=None;self.results=[];self.raw=None;self.server=None;self.proxy=None;self.observation_lock=asyncio.Lock()
 def config(self,trial):return ConnectionConfig(api_key='c01-local-test-only',domain=f'127.0.0.1:{self.proxy.port}',request_timeout=timedelta(seconds=120),headers={'x-c01-actor':'sdk','x-c01-trial':trial})
 def snapshot(self,trial):
  before=time.monotonic_ns();rows=[];races=[]
  labels=[f'{STUDY_KEY}={self.study}',f'{TRIAL_KEY}={trial}',f'{ROLE_KEY}='+('sentinel' if trial=='sentinel' else 'target')]
  summaries=self.raw.api.containers(all=True,filters={'label':labels})
  for summary in summaries:
   cid=summary['Id']
   try:a=self.raw.api.inspect_container(cid)
   except docker.errors.NotFound:
    readback=self.raw.api.containers(all=True,filters={'label':labels})
    record={'listed_id':cid,'inspect_status':404,'readback_ids':[x['Id'] for x in readback],'readback_monotonic_ns':time.monotonic_ns()}
    races.append(record);self.events('observer_inspect404_readback',trial=trial,**record)
    if readback:raise RuntimeError('inspect404 has uncertain/replaced exact-label readback')
    continue
   l=a.get('Config',{}).get('Labels') or {};hc=a.get('HostConfig',{})
   if l.get(STUDY_KEY)!=self.study or l.get(TRIAL_KEY)!=trial:raise PermissionError('observer owner mismatch')
   rows.append({'container_id':a['Id'],'sandbox_id':l.get('opensandbox.io/id'),'state':a.get('State'),'labels':l,'limits':{k:hc.get(k) for k in ['NanoCpus','Memory','MemorySwap','PidsLimit']}})
  return self.events('container_observation',trial=trial,objects=rows,inspection_started_monotonic_ns=before,listed_ids=[x['Id'] for x in summaries],confirmed_disappearance_readbacks=races)
 async def observe(self,trial):
  async with self.observation_lock:return await asyncio.to_thread(self.snapshot,trial)
 async def sentinel_check(self,phase):
  obs=await self.observe('sentinel');assert len(obs['objects'])==1,'sentinel absent/multiple';obj=obs['objects'][0];assert obj['container_id']==self.sentinel_cid and obj['state']['Running'],'sentinel identity/running changed'
  c=self.raw.containers.get(self.sentinel_cid);l=c.attrs['Config']['Labels'];assert l.get(STUDY_KEY)==self.study and l.get(TRIAL_KEY)=='sentinel'
  response=await asyncio.to_thread(c.exec_run,['sh','-c',f'test "$(cat /tmp/c01-sentinel)" = "{self.study}"'])
  self.events('sentinel_check',phase=phase,container_id=c.id,exit_code=response.exit_code)
  assert response.exit_code==0,'sentinel marker changed';return True
 async def readiness(self,sid,trial):
  try:
   r=await self.http.get(f'{self.upstream}/v1/sandboxes/{sid}/endpoints/44772',headers={'OPEN-SANDBOX-API-KEY':'c01-local-test-only','x-c01-actor':'observer','x-c01-trial':trial});r.raise_for_status();data=r.json();ep=data['endpoint'];ep=ep if ep.startswith('http') else 'http://'+ep
   r=await self.http.get(ep.rstrip('/')+'/ping',headers=data.get('headers') or {},timeout=2)
   self.events('backend_readiness_observation',trial=trial,status=r.status_code,endpoint=ep);return {'ready':r.status_code==200,'status':r.status_code,'error':None}
  except Exception as e:self.events('backend_readiness_observation',trial=trial,error=repr(e));return {'ready':None,'status':None,'error':repr(e)}
 async def administrative_delete(self,trial,reason):
  self.events('admin_cleanup_begin',trial=trial,reason=reason)
  objs=self.raw.containers.list(all=True,filters={'label':[f'{STUDY_KEY}={self.study}',f'{TRIAL_KEY}={trial}']})
  for o in objs:
   l=o.attrs['Config']['Labels'];assert l.get(STUDY_KEY)==self.study and l.get(TRIAL_KEY)==trial
   sid=l.get('opensandbox.io/id')
   if sid:
    r=await self.http.delete(f'{self.upstream}/v1/sandboxes/{sid}',headers={'OPEN-SANDBOX-API-KEY':'c01-local-test-only','x-c01-actor':'admin-sentinel-final' if trial=='sentinel' else 'admin','x-c01-trial':trial},timeout=15)
    self.events('admin_delete_response',trial=trial,sandbox_id=sid,status=r.status_code)
   remaining=await self.observe(trial)
   if remaining['objects']:
    self.events('admin_docker_fallback',trial=trial,container_id=o.id)
    await asyncio.to_thread(o.remove,force=True)
  obs=await self.observe(trial);assert not obs['objects'],'administrative cleanup unresolved';self.events('admin_cleanup_end',trial=trial)
 async def settle(self,task,timeout):
  done,pending=await asyncio.wait({task},timeout=timeout)
  if pending:raise TimeoutError('SDK task unsettled; watchdog did not recancel it')
  try:return {'kind':'returned','value':task.result()}
  except BaseException as e:return {'kind':type(e).__name__,'exception':repr(e)}
 async def trial(self,index,arm,lifetime):
  tid=f't{index:02d}-{arm}-'+('ttl60' if lifetime else 'manual');d=self.out/tid;d.mkdir();g=TrialGate(tid,arm);self.proxy.active[tid]=g
  row={'trial_id':tid,'index':index,'arm':arm,'lifetime_s':lifetime,'status':'started','request_timeout_s':120,'cancel_requested_ns':None,'cancel_returned_ns':None,'destroy_requested_ns':None,'destroy_returned_ns':None}
  dump(d/'result.json',row);self.events('trial_started',trial=tid,arm=arm,lifetime_s=lifetime);await self.sentinel_check(tid+'-before')
  task=asyncio.create_task(Sandbox.create(TASK_IMAGE,timeout=timedelta(seconds=lifetime) if lifetime else None,ready_timeout=timedelta(seconds=30),resource={'cpu':'1','memory':'256Mi'},platform=PlatformSpec(os='linux',arch='amd64'),metadata={STUDY_KEY:self.study,TRIAL_KEY:tid,ROLE_KEY:'target'},entrypoint=['sh','-c','sleep infinity'],connection_config=self.config(tid)))
  self.events('sdk_create_requested',trial=tid)
  samples=[];sample_errors=[];sample_stop=asyncio.Event()
  async def sample_loop():
   while not sample_stop.is_set():
    try:samples.append(await self.observe(tid))
    except Exception as exc:sample_errors.append(repr(exc));self.events('observation_error',trial=tid,error=repr(exc));return
    await asyncio.sleep(.25)
  sampler=asyncio.create_task(sample_loop())
  try:
   if arm=='normal':
    settled=await self.settle(task,50);assert settled['kind']=='returned',settled
    sandbox=settled.pop('value');row['sdk_ready']=True;row['sdk_identified']=True
    self.events('sdk_ready',trial=tid,sandbox_id=sandbox.id)
    assert len(g.creates)==1 and g.creates[0]['response']['status']==202,g.creates
    row['server_create']=g.creates[0];row['backend_ready']={'ready':True,'status':200,'error':None,'source':'SDK native readiness success'}
    snap=await self.observe(tid);assert len(snap['objects'])==1
    row['injection_observation']=snap
    row['destroy_requested_ns']=time.monotonic_ns();self.events('sdk_destroy_requested',trial=tid)
    await sandbox.destroy();row['destroy_returned_ns']=time.monotonic_ns();self.events('sdk_destroy_returned',trial=tid)
    row['sdk_terminal']='destroy_returned';anchor=row['destroy_requested_ns'];returned=row['destroy_returned_ns']
   else:
    gatewait=asyncio.create_task(g.gate.wait());done,_=await asyncio.wait({gatewait,task},timeout=45,return_when=asyncio.FIRST_COMPLETED)
    assert gatewait in done and g.gate.is_set(),'fault gate not reached before SDK settled/deadline'
    assert not task.done(),'SDK already completed before gate'
    assert len(g.creates)==1 and g.creates[0]['response']['status']==202,g.creates
    response=g.creates[0];row['server_create']=response;sid=response['body']['id'];assert sid
    snap=await self.observe(tid);assert len(snap['objects'])==1 and snap['objects'][0]['state']['Running'],'target not live at gate'
    row['injection_observation']=snap;row['backend_ready']=await self.readiness(sid,tid)
    assert row['backend_ready']['error'] is None,'backend readiness observer unavailable'
    row['sdk_identified']=bool(g.endpoints);row['sdk_ready']=False
    assert row['sdk_identified']==(arm=='known_id_cancel')
    row['cancel_requested_ns']=time.monotonic_ns();self.events('sdk_cancel_requested',trial=tid,task_pending=not task.done())
    row['cancel_call_accepted']=task.cancel();assert row['cancel_call_accepted']
    settled=await self.settle(task,35);row['cancel_returned_ns']=time.monotonic_ns();self.events('sdk_cancel_settled',trial=tid,terminal=settled['kind'])
    assert settled['kind']=='CancelledError',settled
    row['sdk_terminal']=settled['kind'];anchor=row['cancel_requested_ns'];returned=row['cancel_returned_ns']
    if arm=='lost_id_cancel':
     for _ in range(100):
      if g.downstream_transport is None or g.downstream_transport.is_closing():break
      await asyncio.sleep(.01)
     row['lost_reply_downstream_closed']=g.downstream_transport is None or g.downstream_transport.is_closing()
     assert row['lost_reply_downstream_closed'],'SDK transport did not close after cancellation'
     self.events('lost_id_client_disconnect_observed',trial=tid)
    g.release.set();self.events('gate_release_after_sdk_terminal',trial=tid)
   # Scientific observation starts before administrative cleanup.
   first=await self.observe(tid);samples.append(first);row['first_post_terminal_observation']=first
   response=row['server_create'];body=response['body'];expiry=body.get('expiresAt');remaining=None
   if expiry:
    # Map server expiry into the local monotonic clock at the proxy's captured202.
    rec=response['response'];expiry_ns=rec['monotonic_ns']+int((utc_seconds(expiry)-rec['wall_time_ns']/1e9)*1e9)
    remaining=(expiry_ns-returned)/1e9
   else:expiry_ns=None
   row['expiry_monotonic_ns']=expiry_ns;row['remaining_ttl_at_terminal_s']=remaining
   horizon=max(returned+30_000_000_000,(expiry_ns+15_000_000_000) if expiry_ns and arm=='lost_id_cancel' else 0)
   row['observation_deadline_ns']=horizon;row['observation_anchor']='SDK terminal return';row['operation_request_anchor_ns']=anchor
   while samples[-1]['objects'] and time.monotonic_ns()<horizon:
    assert not sample_errors,sample_errors
    await asyncio.sleep(.25)
   samples.append(await self.observe(tid))
   sample_stop.set();await sampler
   assert not sample_errors,sample_errors
   obs=sorted({x['monotonic_ns']:x for x in samples+[row['injection_observation']]}.values(),key=lambda x:x['monotonic_ns'])
   clock_bad=[]
   for previous,current in zip(obs,obs[1:]):
    discrepancy=((current['wall_time_ns']-previous['wall_time_ns'])-(current['monotonic_ns']-previous['monotonic_ns']))/1e9
    if abs(discrepancy)>2:clock_bad.append({'at':current['monotonic_ns'],'wall_mono_increment_disagreement_s':discrepancy})
   # Pre-create absence is not cleanup; retain it in raw samples but exclude from removal endpoint.
   outcome_obs=[x for x in obs if x['monotonic_ns']>=row['injection_observation']['monotonic_ns']]
   dump(d/'observations.json',obs);row['observation_count']=len(obs);row['first_absent_ns']=next((x['monotonic_ns'] for x in outcome_obs if not x['objects']),None)
   row['last_present_ns']=max((x['monotonic_ns'] for x in outcome_obs if x['objects']),default=None)
   row['retained_at_horizon']=bool(obs[-1]['objects']);row['right_censored']=row['retained_at_horizon'];row['clock_disagreements']=clock_bad
   row['sdk_delete_requests']=[x for x in g.requests if x['method']=='DELETE'];row['sdk_endpoint_requests']=g.endpoints if arm=='known_id_cancel' else [x for x in g.requests if '/endpoints/' in x['path']]
   row['upstream_create_count']=len(g.creates);row['sentinel_preserved']=await self.sentinel_check(tid+'-after')
   # Store scientific outcome before any post-horizon removal.
   row['status']='completed';row['scientific_record_complete_ns']=time.monotonic_ns();dump(d/'result.json',row)
   if row['retained_at_horizon']:await self.administrative_delete(tid,'post-horizon-retained-target')
   assert not (await self.observe(tid))['objects'],'target not clean before next trial'
   assert not clock_bad,'clock consistency invalidates timing; halt subsequent trials'
   self.events('trial_completed',trial=tid,retained_at_horizon=row['retained_at_horizon']);self.results.append(row);return row
  except BaseException as e:
   row.update(status='invalid_or_incomplete',error=repr(e),traceback=traceback.format_exc(),sdk_task_done=task.done());dump(d/'result.json',row);self.events('trial_failed',trial=tid,error=repr(e));raise
  finally:
   sample_stop.set();await sampler
   g.release.set()
   if not task.done():
    # A failure outside the planned cancellation is explicitly administrative.
    self.events('administrative_sdk_cancellation',trial=tid);task.cancel();await asyncio.wait({task},timeout=15)
   self.proxy.active.pop(tid,None)
 async def final_native_cleanup(self):
  if self.server and self.server.poll() is None:
   self.server.terminate()
   try:await asyncio.to_thread(self.server.wait,15)
   except subprocess.TimeoutExpired:self.events('administrative_server_kill');self.server.kill();await asyncio.to_thread(self.server.wait)
  self.events('native_server_stopped',returncode=self.server.returncode if self.server else None)
  empty=0;deadline=time.monotonic()+30;inventory=[]
  while time.monotonic()<deadline and empty<3:
   objs=self.raw.containers.list(all=True,filters={'label':f'{STUDY_KEY}={self.study}'})
   inventory.append({'monotonic_ns':time.monotonic_ns(),'ids':[x.id for x in objs]})
   if objs:
    empty=0
    for obj in objs:
     labels=obj.attrs.get('Config',{}).get('Labels') or {}
     assert labels.get(STUDY_KEY)==self.study and labels.get(TRIAL_KEY) and labels.get(ROLE_KEY) in ['target','sentinel','helper']
     self.events('final_admin_docker_remove',container_id=obj.id,trial=labels.get(TRIAL_KEY),role=labels.get(ROLE_KEY))
     try:await asyncio.to_thread(obj.remove,force=True)
     except docker.errors.NotFound:pass
   else:empty+=1
   await asyncio.sleep(.5)
  final=self.raw.containers.list(all=True,filters={'label':f'{STUDY_KEY}={self.study}'});dump(self.out/'FINAL_CLEANUP.json',{'exact_study':self.study,'remaining_ids':[x.id for x in final],'quiet_inventory':inventory,'native_server_returncode':self.server.returncode if self.server else None,'foreign_all_container_count_after':len(self.raw.containers.list(all=True))})
  return final
 async def run(self):
  self.events('campaign_started',phase=self.args.phase)
  host=json.loads(subprocess.check_output(['docker','context','inspect'],text=True))[0]['Endpoints']['docker']['Host'];self.raw=docker.DockerClient(base_url=host,timeout=10);self.raw.ping()
  info=self.raw.info();dump(self.out/'docker-environment.json',{k:info.get(k) for k in ['ServerVersion','OSType','Architecture','NCPU','MemTotal','OperatingSystem','KernelVersion']})
  foreign_before=len(self.raw.containers.list(all=True));self.events('foreign_inventory_count_before',count=foreign_before)
  self.http=httpx.AsyncClient(timeout=10);serverport=port();self.upstream=f'http://127.0.0.1:{serverport}'
  cells=[(a,t) for t in [60,None] for a in ['normal','known_id_cancel','lost_id_cancel']]
  order=cells if self.args.phase=='pilot' else cells*3
  if self.args.phase=='main':random.Random(20261115).shuffle(order)
  config={'run_id':self.study,'phase':self.args.phase,'planned_trials':len(order),'order':order,'source_sha':SOURCE_SHA,'task_image':TASK_IMAGE,'execd_image':EXECD_IMAGE,'request_timeout_s':120,'sdk_default_retry_policy':True,'target_cpu':1,'target_memory_mib':256,'sentinel_cpu':.1,'sentinel_memory_mib':128,'commands':sys.argv,'created_at_utc':datetime.now(timezone.utc).isoformat(),'hashes':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in list((ROOT/'src').glob('*.py'))+[ROOT/'PROTOCOL.md']}}
  config['upstream_file_hashes']={str(f.relative_to(REPO)):hashlib.sha256(f.read_bytes()).hexdigest() for base in [REPO/'server/opensandbox_server',REPO/'sdks/sandbox/python/src/opensandbox'] for f in base.rglob('*.py')}
  config['amendments']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in ROOT.glob('AMENDMENT_*.md')}
  dump(self.out/'FREEZE.json',config)
  (self.out/'requirements-freeze.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
  serverlog=(self.out/'server.log').open('w');env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+str(REPO/'server')+os.pathsep+str(REPO/'sdks/sandbox/python/src')
  self.server=subprocess.Popen([sys.executable,str(ROOT/'src/server.py'),'--run-dir',str(self.out),'--study',self.study,'--port',str(serverport)],env=env,stdout=serverlog,stderr=subprocess.STDOUT)
  dump(self.out/'PIDS.json',{'driver':os.getpid(),'server':self.server.pid})
  try:
   for _ in range(120):
    if self.server.poll() is not None:raise RuntimeError('native server exited during setup')
    try:
     z=await self.http.get(self.upstream+'/health',timeout=.5)
     if z.status_code==200:break
    except Exception:pass
    await asyncio.sleep(.25)
   else:raise TimeoutError('native server health unavailable')
   self.proxy=Proxy(self.upstream,self.out,self.events);await self.proxy.start();self.events('http_stack_ready',server_port=serverport,proxy_port=self.proxy.port)
   self.sentinel=await Sandbox.create(TASK_IMAGE,timeout=None,resource={'cpu':'.1','memory':'128Mi'},platform=PlatformSpec(os='linux',arch='amd64'),metadata={STUDY_KEY:self.study,TRIAL_KEY:'sentinel',ROLE_KEY:'sentinel'},entrypoint=['sh','-c','sleep infinity'],connection_config=self.config('sentinel'))
   snap=await self.observe('sentinel');assert len(snap['objects'])==1;self.sentinel_cid=snap['objects'][0]['container_id'];s=self.raw.containers.get(self.sentinel_cid)
   marked=await asyncio.to_thread(s.exec_run,['sh','-c',f'printf %s {self.study} > /tmp/c01-sentinel']);assert marked.exit_code==0
   await self.sentinel_check('campaign-initial')
   for i,(arm,lifetime) in enumerate(order,1):
    self.events('progress',completed=len(self.results),planned=len(order));await self.trial(i,arm,lifetime)
    dump(self.out/'PROGRESS.json',{'completed':len(self.results),'planned':len(order),'last':self.results[-1]['trial_id']})
   dump(self.out/'SUMMARY.json',{'status':'completed','planned':len(order),'completed':len(self.results),'results':self.results})
  except BaseException as e:
   dump(self.out/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'completed':len(self.results)});raise
  finally:
   self.events('final_administration_started',unsettled_proxy_creates=self.proxy.inflight_creates if self.proxy else {})
   dump(self.out/'UNSETTLED_AT_TEARDOWN.json',{'proxy_creates':self.proxy.inflight_creates if self.proxy else {},'campaign_had_failure':(self.out/'FAILURE.json').exists()})
   if self.proxy:
    for gate in self.proxy.active.values():gate.release.set()
   # Quiesce the native process before final Docker cleanup. Any incomplete
   # create stays incomplete even if bounded administrative cleanup later succeeds.
   final=await self.final_native_cleanup()
   if self.proxy:await self.proxy.close()
   serverlog.close();await self.http.aclose();self.raw.close();assert not final,'owned containers left after cleanup'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--phase',choices=['pilot','main'],required=True);ap.add_argument('--authorize-native',action='store_true');a=ap.parse_args()
 if not a.authorize_native:raise SystemExit('Explicit --authorize-native run marker required')
 asyncio.run(Experiment(a).run())
if __name__=='__main__':main()
