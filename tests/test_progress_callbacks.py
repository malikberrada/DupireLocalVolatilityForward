from types import SimpleNamespace
import numpy as np
from scipy import sparse
from dupire_joint.solver import _callback_event,_update_iteration_bar,_highs,SolverOptions
from dupire_joint.model import LP


TYPES=SimpleNamespace(kCallbackLogging=0,kCallbackSimplexInterrupt=1,kCallbackIpmInterrupt=2)


class UndefinedFields:
    def __getattr__(self,name):
        raise AssertionError(f"Undefined native callback field read: {name}")


class FakeBar:
    def __init__(self):
        self.n=0
    def update(self,value):
        self.n+=value
    def refresh(self):
        pass


def test_log_event_never_reads_iteration_or_timing_fields():
    event=_callback_event(0,"Running HiGHS",UndefinedFields(),TYPES)
    assert event["callback"]=="logging"
    assert not any(k in event for k in ("simplex_iterations","ipm_iterations","solver_seconds"))
    bar=FakeBar();counters={}
    _update_iteration_bar(bar,counters,event)
    assert bar.n==0 and not counters


def test_iteration_events_read_only_their_defined_algorithm():
    class Simplex(UndefinedFields):
        simplex_iteration_count=7
        running_time=.1
    class IPM(UndefinedFields):
        ipm_iteration_count=3
        running_time=.2
    a=_callback_event(1,"",Simplex(),TYPES)
    b=_callback_event(2,"",IPM(),TYPES)
    assert a["simplex_iterations"]==7 and "ipm_iterations" not in a
    assert b["ipm_iterations"]==3 and "simplex_iterations" not in b
    bar=FakeBar();counters={}
    _update_iteration_bar(bar,counters,a)
    _update_iteration_bar(bar,counters,b)
    assert bar.n==10
    _update_iteration_bar(bar,counters,{"simplex_iterations":0,"ipm_iterations":0})
    assert bar.n==0


def test_native_presolved_smoke_test_has_truthful_final_counts():
    lp=LP(sparse.csr_matrix([[1.]]),np.array([.5]),np.array([0.]),np.array([1.]),np.array([-1.]))
    events=[]
    result=_highs(lp,SolverOptions(threads=1,time_limit=10),events.append)
    assert result["status"]=="optimal"
    assert result["simplex_iterations"]==0 and result["ipm_iterations"]==0
    assert result["x"][0]==.5
    for event in events:
        if event.get("callback")=="logging":
            assert "simplex_iterations" not in event and "ipm_iterations" not in event
