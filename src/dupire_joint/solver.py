"""C++ HiGHS in one persistent spawned process; the parent stays responsive."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import multiprocessing as mp
import math
import os
import queue
import time
import traceback
import numpy as np


def _callback_event(kind,message,data_out,callback_types):
    """Read only the fields defined for this exact HiGHS callback type."""
    event={"kind":"progress","solver":"HiGHS C++","message":str(message).strip()[:300]}
    if int(kind)==int(callback_types.kCallbackLogging):
        # Iteration/time fields are not defined for logging callbacks.
        event["callback"]="logging"
        return event
    if int(kind)==int(callback_types.kCallbackSimplexInterrupt):
        event["callback"]="simplex"
        key="simplex_iterations"
        count=int(data_out.simplex_iteration_count)
    elif int(kind)==int(callback_types.kCallbackIpmInterrupt):
        event["callback"]="ipm"
        key="ipm_iterations"
        count=int(data_out.ipm_iteration_count)
    else:
        return None
    if count>=0:
        event[key]=count
    seconds=float(data_out.running_time)
    if math.isfinite(seconds) and seconds>=0:
        event["solver_seconds"]=seconds
    return event


def _update_iteration_bar(bar,counters,event):
    """Preserve separate algorithm counts; logs never supply a count."""
    changed=False
    for key in ("simplex_iterations","ipm_iterations"):
        if key in event and isinstance(event[key],int) and event[key]>=0:
            counters[key]=event[key]
            changed=True
    if bar is None or not changed:
        return
    count=sum(counters.values())
    if count>=bar.n:
        bar.update(count-bar.n)
    else:
        # A final getInfo() count is authoritative even if a native phase reset.
        bar.n=count
        bar.refresh()


@dataclass
class SolverOptions:
    threads: int = 10
    time_limit: float = 120.0
    tolerance: float = 1e-9
    method: str = "choose"
    backend: str = "highs"

    def __post_init__(self):
        if self.threads<1 or not np.isfinite(self.time_limit) or self.time_limit<=0:
            raise ValueError("threads >= 1 and finite time_limit > 0 required")
        if not 1e-10<=self.tolerance<=1e-4:
            raise ValueError("Solver tolerance must be in [1e-10,1e-4]")
        if self.method not in ("choose","simplex","ipm") or self.backend != "highs":
            raise ValueError("Unsupported solver/method")


def _highs(lp,opt,send):
    import highspy
    A,b,scale=lp.scaled()
    A=A.tocsr()
    if A.nnz>=2**31 or max(A.shape)>=2**31:
        raise ValueError("LP exceeds the int32 wheel interface")
    h=highspy.Highs()
    settings={"output_flag":True,"log_to_console":False,"threads":opt.threads,
              "time_limit":opt.time_limit,"primal_feasibility_tolerance":opt.tolerance,
              "dual_feasibility_tolerance":opt.tolerance,"solver":opt.method,
              "random_seed":0}
    for k,v in settings.items():
        if h.setOptionValue(k,v)==highspy.HighsStatus.kError:
            raise RuntimeError(f"HiGHS rejected option {k}={v}")
    last={"logging":0.0,"iterations":0.0}
    def callback(kind,message,data_out,data_in,user):
        event=_callback_event(kind,message,data_out,highspy.cb.HighsCallbackType)
        if event is None:
            return
        category="logging" if event["callback"]=="logging" else "iterations"
        now=time.monotonic()
        if now-last[category] >= .5:
            last[category]=now
            send(event)
    h.setCallback(callback,None)
    for name in ("kCallbackLogging","kCallbackSimplexInterrupt","kCallbackIpmInterrupt"):
        h.startCallback(getattr(highspy.cb.HighsCallbackType,name))
    model=highspy.HighsLp()
    model.num_col_=A.shape[1];model.num_row_=A.shape[0]
    model.col_cost_=lp.cost
    model.col_lower_=lp.lower;model.col_upper_=lp.upper
    model.row_lower_=np.full(len(b),-highspy.kHighsInf);model.row_upper_=b
    model.a_matrix_.format_=highspy.MatrixFormat.kRowwise
    model.a_matrix_.start_=A.indptr.astype(np.int32)
    model.a_matrix_.index_=A.indices.astype(np.int32)
    model.a_matrix_.value_=A.data
    if h.passModel(model)==highspy.HighsStatus.kError:
        raise RuntimeError("HiGHS rejected the sparse model")
    h.run()
    # Dual-ray recovery can invoke another native solve. Its iterations are
    # not the iterations of the primary LP whose getInfo() is reported below.
    for name in ("kCallbackLogging","kCallbackSimplexInterrupt","kCallbackIpmInterrupt"):
        h.stopCallback(getattr(highspy.cb.HighsCallbackType,name))
    status=h.getModelStatus();info=h.getInfo();sol=h.getSolution()
    kind="unknown"
    if status==highspy.HighsModelStatus.kOptimal:
        kind="optimal"
    elif status==highspy.HighsModelStatus.kInfeasible:
        kind="infeasible"
    elif status==highspy.HighsModelStatus.kTimeLimit:
        kind="time_limit"
    ray=None
    if kind=="infeasible":
        _,has_ray,value=h.getDualRay()
        if has_ray:
            ray=np.asarray(value,dtype=float)/scale
    return {"status":kind,"native_status":h.modelStatusToString(status),
            "x":np.asarray(sol.col_value,dtype=float) if sol.value_valid else None,
            "ray":ray,"objective":float(info.objective_function_value) if kind=="optimal" else None,
            "simplex_iterations":int(info.simplex_iteration_count),
            "ipm_iterations":int(info.ipm_iteration_count),"backend":"highs","version":h.version()}


def _worker(commands,events):
    # Never import/initialize CUDA in the parent and then fork it.
    while True:
        task=commands.get()
        if task is None:
            break
        ident,lp,opt=task
        def send(event):
            events.put((ident,event))
        start=time.monotonic()
        try:
            send({"kind":"progress","message":"native model loading"})
            result=_highs(lp,opt,send)
            result["wall_seconds"]=time.monotonic()-start
            send({"kind":"result","result":result})
        except BaseException as e:
            send({"kind":"error","error":str(e),"traceback":traceback.format_exc()})


class SolverSession:
    def __init__(self,options=None,progress=None):
        self.options=options or SolverOptions()
        self.progress=progress
        self.context=mp.get_context("spawn")
        self.commands=self.context.Queue()
        self.events=self.context.Queue()
        self.process=None
        self.counter=0

    def __enter__(self):
        # Environment applies to spawned native libraries, avoiding oversubscription.
        # Do not change the parent process's numerical thread pools.
        self.process=self.context.Process(target=_worker,args=(self.commands,self.events),daemon=True)
        self.process.start()
        return self

    def solve(self,lp,label="LP"):
        if self.process is None or not self.process.is_alive():
            raise RuntimeError("SolverSession must be used inside a with block; worker is unavailable")
        self.counter+=1;ident=self.counter
        start=time.monotonic()
        self.commands.put((ident,lp,self.options))
        p=self.progress
        last={"message":"starting native solver"}
        iteration_counts={}
        if p:
            p.event(label,force=True,state="running",rows=lp.A.shape[0],variables=lp.A.shape[1],nnz=lp.A.nnz,
                    time_limit=self.options.time_limit)
        bar=p.bar(total=None,desc=label,unit="iter") if p else None
        try:
            while True:
                try:
                    got,event=self.events.get(timeout=.5)
                except queue.Empty:
                    if not self.process.is_alive():
                        raise RuntimeError(f"Native solver worker exited with {self.process.exitcode}")
                    if time.monotonic()-start>self.options.time_limit+30:
                        self.close(terminate=True)
                        raise TimeoutError("Native worker exceeded wall time; worker terminated; no feasibility conclusion")
                    if p:
                        p.event(label,state="running",solver_wall_seconds=round(time.monotonic()-start,2),**last)
                    continue
                if got!=ident:
                    raise RuntimeError("Solver protocol lost task ordering")
                if event["kind"]=="error":
                    raise RuntimeError(event["traceback"])
                if event["kind"]=="result":
                    result=event["result"]
                    _update_iteration_bar(bar,iteration_counts,result)
                    if p:
                        p.event(label,force=True,state="done",status=result["status"],
                                solver_wall_seconds=round(result["wall_seconds"],3),
                                **iteration_counts)
                    return result
                last.update({k:v for k,v in event.items() if k!="kind"})
                _update_iteration_bar(bar,iteration_counts,event)
                if bar is not None:
                    bar.set_postfix_str(last.get("message","")[:85])
                if p:
                    p.event(label,state="running",**last)
        finally:
            if bar is not None:
                bar.close()

    def close(self,terminate=False):
        if self.process:
            if self.process.is_alive() and not terminate:
                self.commands.put(None)
                self.process.join(timeout=3)
            if self.process.is_alive():
                self.process.terminate();self.process.join(timeout=3)
            self.process=None
        for q in (self.commands,self.events):
            q.cancel_join_thread();q.close()

    def __exit__(self,typ,value,tb):
        self.close(terminate=typ is not None)

