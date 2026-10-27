"""One command: collect/replay Yahoo, exact F0 verification, local-volatility LPs."""
import argparse
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import os
from fractions import Fraction as Q

from collect_coherent_yahoo import terminate


def exact_local_check(logical,vector,sigma_min,sigma_max,scheme):
    ts=list(map(Q,logical['times']));xs=list(map(Q,logical['strikes']))
    nt,nx=len(ts),len(xs);v=list(map(Q,vector))
    if len(v)!=nt*nx:return {'passed':False,'reason':'dimension'}
    c=[v[j*nx:(j+1)*nx] for j in range(nt)]
    lo,hi=Q(str(sigma_min))**2,Q(str(sigma_max))**2
    for j in range(nt-1):
        row=c[j if scheme=='forward' else j+1]
        for i in range(1,nx-1):
            left=(row[i]-row[i-1])/(xs[i]-xs[i-1])
            right=(row[i+1]-row[i])/(xs[i+1]-xs[i])
            gamma=2*(right-left)/(xs[i+1]-xs[i-1])
            factor=(ts[j+1]-ts[j])*xs[i]**2*gamma/2
            delta=c[j+1][i]-c[j][i]
            if not lo*factor<=delta<=hi*factor:
                return {'passed':False,'reason':'exact local variance inequality','cell':[j,i],'scheme':scheme}
    return {'passed':True,'scheme':scheme,'cells':(nt-1)*(nx-2),
            'sigma_bounds':[str(Q(str(sigma_min))),str(Q(str(sigma_max)))],
            'arithmetic':'exact rationals on original normalized coordinates and declared variance bounds'}


def local_stage(argv,verify=False):
    p=argparse.ArgumentParser()
    p.add_argument('--accepted',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--threads',type=int,default=4)
    p.add_argument('--sigma-min',type=float,default=.05)
    p.add_argument('--sigma-max',type=float,default=1.)
    a=p.parse_args(argv)
    from collect_coherent_yahoo import (interior_lp,exact_primal_check,exact_shape_check,
        logical_grid,verify_bundle,require)
    from dupire_joint.data import Quotes,Grid
    from dupire_joint.model import LP,build_lp,audit_lp
    from dupire_joint.engine import independent_audit
    from dupire_joint.progress import Progress
    from dupire_joint.solver import SolverSession,SolverOptions
    from dupire_joint.certificates import find_certificate
    a.out.mkdir(parents=True,exist_ok=True)
    cfg=read(a.accepted/'collector_config.json');progress=Progress(a.out)
    verify_bundle(a.accepted,cfg,progress)
    if verify:
        report=read(a.out/'joint_validation.json')
        a.sigma_min,a.sigma_max=report['sigma_bounds']
    else:
        report={'sigma_bounds':[a.sigma_min,a.sigma_max],'variants':{},'bid_ask_synchronization_verified':False,
                'scope':'selected strike mesh; nominal F,D; exact discrete constraints only'}
    q=Quotes.read(a.accepted/'F0.quotes.csv');grid=Grid.from_quotes(q)
    logical=logical_grid(a.accepted,cfg)
    lo,hi=a.sigma_min**2,a.sigma_max**2
    options=SolverOptions(threads=a.threads,time_limit=60,tolerance=1e-10,method='ipm')
    session=None if verify else SolverSession(options,progress)
    if session:session.__enter__()
    try:
        for scheme in ('forward','backward'):
            lp=build_lp(grid,q,lo,hi,scheme,local=True,max_variables=cfg['max_nodes'])
            if verify:
                saved=LP.load(a.out/(scheme+'.lp.npz'))
                require(lp.digest()==saved.digest(),'Rebuilt local LP differs')
                witness=read(a.out/(scheme+'.witness.json'))
                require(witness['lp_sha256']==lp.digest() and witness['quotes_sha256']==q.digest(),'Witness binding differs')
                values=list(map(Q,witness['prices_rational']))
                checks=[exact_primal_check(lp,values),exact_shape_check(logical,values),
                        exact_local_check(logical,values,a.sigma_min,a.sigma_max,scheme)]
                require(all(c['passed'] for c in checks),str(checks))
                continue
            lp.save(a.out/(scheme+'.lp.npz'))
            original=session.solve(lp,scheme+' / local-volatility constraints')
            rec={'solver_status':original['status'],'status':'not_verified'}
            if original['status']=='infeasible':
                certificate=find_certificate(lp,original,session,scheme)
                if certificate:save(a.out/(scheme+'.infeasibility.json'),certificate)
                rec['status']='infeasible_certified' if certificate else 'infeasible_solver_only'
                report['variants'][scheme]=rec;continue
            candidates=[]
            if original.get('x') is not None:
                interior=session.solve(interior_lp(lp),scheme+' / seek strict interior, fixed quotes and bounds')
                if interior.get('x') is not None:candidates.append(interior['x'][:-1])
                candidates.append(original['x'])
            for vector in candidates:
                numeric=audit_lp(lp,vector,1e-8)
                direct=independent_audit(vector,grid,q,lo,hi,scheme,True,tol=1e-8)
                if not (numeric['passed'] and direct['passed']):continue
                for denominator in (10**10,10**12,None):
                    values=[Q.from_float(float(v)) for v in vector]
                    if denominator:values=[v.limit_denominator(denominator) for v in values]
                    checks=[exact_primal_check(lp,values),exact_shape_check(logical,values),
                            exact_local_check(logical,values,a.sigma_min,a.sigma_max,scheme)]
                    if all(c['passed'] for c in checks):
                        rec.update(status='feasible_exact',checks=checks,numeric_audit=numeric,independent_audit=direct)
                        save(a.out/(scheme+'.witness.json'),{'lp_sha256':lp.digest(),'quotes_sha256':q.digest(),
                             'prices_rational':[str(v) for v in values],'checks':checks})
                        break
                if rec['status']=='feasible_exact':break
            report['variants'][scheme]=rec
            save(a.out/'joint_validation.json',report)
    finally:
        if session:session.__exit__(None,None,None)
    if verify:
        save(a.out/'joint_verification.json',{'verified':True,'schemes':['forward','backward'],'arithmetic':'exact rational'})
        print('[pipeline] Both local-volatility witnesses independently reverified exactly',flush=True)
        return 0
    report['verified']=all(v['status']=='feasible_exact' for v in report['variants'].values()) and len(report['variants'])==2
    save(a.out/'joint_validation.json',report)
    print(json.dumps(report,indent=2),flush=True)
    return 0 if report['verified'] else 3


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))


def save(p,data):
    p.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def run(command,seconds):
    process=subprocess.Popen(command,start_new_session=os.name!='nt',
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
    start=time.monotonic();notice=start+5
    try:
        while process.poll() is None:
            now=time.monotonic()
            if now-start>seconds:
                terminate(process)
                raise TimeoutError('Stage exceeded '+str(seconds)+' seconds')
            if now>=notice:
                print('[pipeline] child pid='+str(process.pid)+' elapsed='+str(round(now-start,1))+'s',flush=True)
                notice=now+5
            time.sleep(.2)
    except BaseException:
        terminate(process);raise
    return process.returncode


def main():
    if len(sys.argv)>1 and sys.argv[1] in ('_local','_verify_local'):
        return local_stage(sys.argv[2:],sys.argv[1]=='_verify_local')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot',help='Existing raw Yahoo snapshot; omit for a new download')
    p.add_argument('--symbol',choices=['^SPX','^XSP'],default='^SPX')
    p.add_argument('--root',choices=['SPXW','SPX','XSP'],default='SPXW')
    p.add_argument('--strike-step',type=float)
    p.add_argument('--out',type=Path)
    p.add_argument('--threads',type=int,default=4)
    p.add_argument('--sigma-min',type=float,default=.05)
    p.add_argument('--sigma-max',type=float,default=1.)
    p.add_argument('--collect-only',action='store_true')
    p.add_argument('--verify',type=Path,help='Reverify an existing pipeline run without network or solving')
    a=p.parse_args()
    if a.verify:
        root=a.verify.resolve();accepted=root/'collecte/accepted';worker=Path(__file__).resolve()
        collector=worker.with_name('collect_coherent_yahoo.py')
        if not (accepted/'READY.json').is_file():p.error('No accepted collector output in this run')
        code=run([sys.executable,'-u',str(collector),'--verify',str(accepted)],300)
        if code:return code
        if (root/'dupire/joint_validation.json').exists():
            return run([sys.executable,'-u',str(worker),'_verify_local','--accepted',str(accepted),
                        '--out',str(root/'dupire')],300)
        return 0
    if not (math.isfinite(a.sigma_min) and math.isfinite(a.sigma_max) and 0<=a.sigma_min<a.sigma_max and a.threads>0):
        p.error('Require finite 0 <= sigma-min < sigma-max and positive threads')
    if a.snapshot and not Path(a.snapshot).is_file():p.error('Snapshot not found: '+a.snapshot)
    out=(a.out or Path('runs')/('yahoo_valide_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))).resolve()
    if out.exists() and any(out.iterdir()):p.error('Use a new empty --out directory')
    out.mkdir(parents=True,exist_ok=True)
    print('[pipeline] Output: '+str(out),flush=True)
    collector=Path(__file__).resolve().with_name('collect_coherent_yahoo.py')
    cmd=[sys.executable,'-u',str(collector),'--symbol',a.symbol,'--root',a.root,
         '--threads',str(a.threads),'--out',str(out/'collecte')]
    if a.snapshot:cmd+=['--offline-snapshot',str(Path(a.snapshot).resolve())]
    if a.strike_step is not None:cmd+=['--strike-step',str(a.strike_step)]
    code=run(cmd,1000)
    if code:
        save(out/'validation.json',{'status':'collection_not_accepted','exit_code':code})
        return code
    accepted=out/'collecte/accepted'
    code=run([sys.executable,'-u',str(collector),'--verify',str(accepted)],300)
    if code:
        save(out/'validation.json',{'status':'verification_failed','exit_code':code})
        return code
    report={'status':'accepted_exact_F0','accepted':str(accepted),'exact_F0_verified':True,
            'mode':'offline_replay' if a.snapshot else 'live_yahoo','bid_ask_synchronization_verified':False,
            'full_raw_chain_certified':False,'local_volatility_numeric_validation':False,
            'continuous_existence_proved':False,'robust_to_curve_uncertainty':False}
    if not a.collect_only:
        print('[pipeline] Local-volatility bounds fixed at ['+str(a.sigma_min)+', '+str(a.sigma_max)+']',flush=True)
        worker=Path(__file__).resolve()
        code=run([sys.executable,'-u',str(worker),'_local','--accepted',str(accepted),
            '--sigma-min',str(a.sigma_min),'--sigma-max',str(a.sigma_max),'--threads',str(a.threads),
            '--out',str(out/'dupire')],300)
        if code:
            report.update(status='local_volatility_stage_failed',exit_code=code)
            save(out/'validation.json',report);return code
        record=read(out/'dupire/joint_validation.json')
        report.update(local_volatility_sigma_bounds=[a.sigma_min,a.sigma_max],
                      local_volatility_variants={k:v['status'] for k,v in record['variants'].items()})
        ok=record['verified']
        report['local_volatility_numeric_validation']=ok
        if not ok:
            report['status']='local_bounds_not_verified'
            save(out/'validation.json',report);print(json.dumps(report,indent=2),flush=True);return 3
        code=run([sys.executable,'-u',str(worker),'_verify_local','--accepted',str(accepted),
                  '--out',str(out/'dupire')],300)
        if code:
            report['status']='local_witness_reverification_failed'
            save(out/'validation.json',report);return code
        report.update(status='validated_yahoo_selected_mesh',local_volatility_exact_validation=True,
                      local_volatility_bounds_certified_on_selected_grid=True)
    save(out/'validation.json',report)
    print(json.dumps(report,indent=2),flush=True)
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:print('[pipeline] Interrupted; child process group stopped',file=sys.stderr);sys.exit(130)
