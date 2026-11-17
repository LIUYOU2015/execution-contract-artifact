"""Offline C-01 validity and descriptive accounting from immutable raw records."""
from pathlib import Path
import argparse,json,statistics,hashlib

def read_jsonl(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def analyze(run):
 freeze=json.loads((run/'FREEZE.json').read_text());events=read_jsonl(run/'events.jsonl');server=read_jsonl(run/'server-events.jsonl');rows=[];errors=[]
 for i,(arm,ttl) in enumerate(freeze['order'],1):
  name=f't{i:02d}-{arm}-'+('ttl60' if ttl else 'manual');f=run/name/'result.json'
  if not f.exists():rows.append({'trial_id':name,'status':'missing'});continue
  d=json.loads(f.read_text());row={'trial_id':name,'arm':arm,'lifetime_s':ttl,'status':d['status']}
  if d['status']!='completed':row['error']=d.get('error');rows.append(row);continue
  ev=[e for e in events if e.get('trial')==name];sv=[e for e in server if e.get('trial')==name];obs=json.loads((f.parent/'observations.json').read_text());inj=d['injection_observation'];start=inj['monotonic_ns'];after=[o for o in obs if o['monotonic_ns']>=start]
  terminal=d['destroy_returned_ns'] if arm=='normal' else d['cancel_returned_ns'];request=d['destroy_requested_ns'] if arm=='normal' else d['cancel_requested_ns'];sid=d['server_create']['body']['id'];cid=inj['objects'][0]['container_id']
  checks={'one_upstream_create':d['upstream_create_count']==1,'accepted_202':d['server_create']['response']['status']==202,'one_live_exact_object':len(inj['objects'])==1 and inj['objects'][0]['sandbox_id']==sid and inj['objects'][0]['state']['Running'],'sentinel':d['sentinel_preserved'],'clock':not d['clock_disagreements'],'observer_known':d['backend_ready']['error'] is None,'no_identity_switch':all(all(x['container_id']==cid for x in o['objects']) for o in after)}
  if arm!='normal':checks['single_cancel']=len([e for e in ev if e['event']=='sdk_cancel_requested'])==1 and d['cancel_call_accepted'] and d['sdk_terminal']=='CancelledError'
  if arm=='lost_id_cancel':
   releases=[e for e in ev if e['event']=='proxy_response_released' and e.get('method')=='POST' and e.get('path','').rstrip('/').endswith('/sandboxes')];disconnects=[e for e in ev if e['event']=='lost_id_downstream_state_at_release']
   checks.update(no_sdk_endpoint=not d['sdk_endpoint_requests'],no_sdk_delete=not d['sdk_delete_requests'],downstream_closed=d.get('lost_reply_downstream_closed') is True and all(e['transport_closing_or_gone'] for e in disconnects) and len(disconnects)==1,release_after_terminal=len(releases)==1 and releases[0]['monotonic_ns']>terminal,not_sdk_identified=not d['sdk_identified'])
  elif arm=='known_id_cancel':checks.update(sdk_identified=d['sdk_identified'] and bool(d['sdk_endpoint_requests']),sdk_delete_attempted=bool(d['sdk_delete_requests']))
  else:checks.update(sdk_ready=d['sdk_ready'],sdk_delete_attempted=bool(d['sdk_delete_requests']))
  first_abs=d['first_absent_ns'];last=d['last_present_ns'];expiry_enter=[e for e in server if e['event']=='expiry_timer_enter' and e.get('sandbox_id')==sid];expiry_removes=[e for e in sv if e['event']=='docker_remove_end' and e.get('actor')=='expiry_timer'];sdk_removes=[e for e in sv if e['event']=='docker_remove_end' and e.get('actor')=='sdk'];admin=[e for e in ev if e['event']=='admin_cleanup_begin']
  row.update(valid=all(checks.values()),checks=checks,sdk_id_observed=d['sdk_identified'],sdk_ready=d['sdk_ready'],backend_ready=d['backend_ready']['ready'],sdk_delete_requests=len(d['sdk_delete_requests']),retained_first_post_terminal=bool(d['first_post_terminal_observation']['objects']),present_beyond_10s=any(o['objects'] and o['monotonic_ns']>=terminal+10_000_000_000 for o in after),present_beyond_30s=any(o['objects'] and o['monotonic_ns']>=terminal+30_000_000_000 for o in after),absent_by_30s=first_abs is not None and first_abs<=terminal+30_000_000_000,retained_at_horizon=d['retained_at_horizon'],right_censored=d['right_censored'],terminal_latency_s=(terminal-request)/1e9,remaining_ttl_at_terminal_s=d['remaining_ttl_at_terminal_s'],removal_bracket_after_terminal_s=[(last-terminal)/1e9 if last is not None else None,(first_abs-terminal)/1e9 if first_abs is not None else None],expiry_callback_entries=len(expiry_enter),expiry_remove_count=len(expiry_removes),sdk_remove_count=len(sdk_removes),post_horizon_admin=len(admin)>0,scientific_horizon_after_terminal_s=(d['observation_deadline_ns']-terminal)/1e9,observations=len(obs))
  if admin and admin[0]['monotonic_ns']<d['observation_deadline_ns']:checks['admin_not_before_horizon']=False;row['valid']=False
  if not row['valid']:errors.append({'trial':name,'checks':{k:v for k,v in checks.items() if not v}})
  rows.append(row)
 planned=len(freeze['order']);completed=sum(r['status']=='completed' for r in rows);valid=sum(r.get('valid',False) for r in rows)
 cleanup=json.loads((run/'FINAL_CLEANUP.json').read_text()) if (run/'FINAL_CLEANUP.json').exists() else None
 if cleanup is None or cleanup['remaining_ids']:errors.append('final cleanup not verified')
 if (run/'FAILURE.json').exists():errors.append('campaign failure file present')
 cells=[]
 for ttl in [60,None]:
  for arm in ['normal','known_id_cancel','lost_id_cancel']:
   a=[r for r in rows if r.get('arm')==arm and r.get('lifetime_s')==ttl and r.get('valid')]
   cells.append({'arm':arm,'lifetime_s':ttl,'valid_n':len(a),'retained_first_post_terminal_n':sum(x['retained_first_post_terminal'] for x in a),'present_beyond_10s_n':sum(x['present_beyond_10s'] for x in a),'present_beyond_30s_n':sum(x['present_beyond_30s'] for x in a),'absent_by_30s_n':sum(x['absent_by_30s'] for x in a),'sdk_delete_trials_n':sum(x['sdk_delete_requests']>0 for x in a),'expiry_removed_trials_n':sum(x['expiry_remove_count']>0 for x in a),'right_censored_n':sum(x['right_censored'] for x in a),'post_horizon_admin_n':sum(x['post_horizon_admin'] for x in a),'terminal_latency_s_median':statistics.median([x['terminal_latency_s'] for x in a]) if a else None,'removal_upper_after_terminal_s':[x['removal_bracket_after_terminal_s'][1] for x in a if x['removal_bracket_after_terminal_s'][1] is not None]})
 result={'run_id':freeze['run_id'],'phase':freeze['phase'],'planned':planned,'started':sum(r['status']!='missing' for r in rows),'completed':completed,'valid':valid,'missing':sum(r['status']=='missing' for r in rows),'invalid':sum(r['status']!='missing' and not r.get('valid',False) for r in rows),'failed_or_incomplete_started':sum(r['status'] not in ['completed','missing'] for r in rows),'errors':errors,'status':'verified' if planned==completed==valid and not errors else 'incomplete_or_invalid','cells':cells,'trials':rows,'cleanup':cleanup,'analysis_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--out',type=Path);a=ap.parse_args();out=a.out or a.run/'ANALYSIS.json';assert not out.exists(),'Use a new output path instead of overwriting analysis';result=analyze(a.run);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['run_id','status','planned','started','completed','valid','missing','invalid','errors','cells']},indent=2))
if __name__=='__main__':main()
