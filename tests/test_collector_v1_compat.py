import copy
from datetime import datetime,timezone
from fractions import Fraction as Q
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest
import collect_coherent_yahoo as c
from dupire_joint.progress import Progress
from dupire_joint.settlements import scheduled_fixing,aware_utc
from dupire_joint.curve_estimation import years


def settings(**extra):
    result=dict(symbol="^SPX",root="SPXW",min_days=14,max_days=180,max_expiries=6,min_expiries=2,
        min_pairs=3,max_pairs=2000,moneyness_min=.95,moneyness_max=1.05,reference_spot=None,
        rps=.5,threads=2,max_nodes=5000,solver_seconds=20,exact_seconds=20,attempt_seconds=30,
        attempts=1,retry_seconds=1,max_collection_seconds=120,allow_closed_market=False,
        offline_snapshot=None,out=None,verify=None)
    result.update(extra);return result


def raw_fixture():
    at=aware_utc("2026-10-26T14:00:00Z")
    raw=dict(source="synthetic_test_not_live_yahoo",started_utc=at.isoformat(),ended_utc=at.isoformat(),chains=[])
    first=None
    for expiry in ["2026-12-18","2027-01-15"]:
        t=float(years(aware_utc(scheduled_fixing("^SPX","SPXW",expiry)["fixing_utc"])-at))
        if first is None:first=t
        F=5000+50*t;D=.99;A=F*D
        calls=[];puts=[]
        for k in [4900,4950,5000,5050,5100]:
            z=k/F-1;u=t-first
            normalized=.06-.5*z+z*z+.2*z**3+.1*z**4+.04*u+.003*u*u
            cp=A*normalized;pp=cp-D*(F-k)
            for side,price,target in [("C",cp,calls),("P",pp,puts)]:
                target.append(dict(contractSymbol="SPXW"+expiry.replace("-","")[2:]+side+f"{k*1000:08d}",
                    strike=k,bid=price-.1,ask=price+.1,lastPrice=price+999,lastTradeDate="2026-01-01T00:00:00Z"))
        raw["chains"].append(dict(symbol="^SPX",expiry=expiry,calls=calls,puts=puts,
                                  underlying=dict(regularMarketPrice=5000)))
    return raw


def process(tmp_path, raw=None, **extra):
    raw=raw or raw_fixture();cfg=settings(**extra)
    tmp_path.mkdir(parents=True,exist_ok=True)
    c.save(tmp_path/"raw_snapshot.json",raw)
    result=c.process_archive(raw,cfg,tmp_path,Progress(tmp_path,quiet=True))
    return result,cfg


def test_sunday_blocks_live_requests_and_next_open():
    r=c.session_window(datetime(2026,10,25,17,tzinfo=timezone.utc))
    assert not r["open"] and r["next_open_casablanca"]=="2026-10-26T13:30:00+00:00"


def test_early_close_window_and_DST():
    assert c.session_window(datetime(2026,11,27,17,59,tzinfo=timezone.utc))["open"]
    r=c.session_window(datetime(2026,11,27,18,1,tzinfo=timezone.utc))
    assert not r["open"] and r["next_open_utc"]=="2026-11-30T14:30:00+00:00"


def test_raw_prices_and_last_price_are_not_repaired(tmp_path):
    raw=raw_fixture();before=copy.deepcopy(raw)
    first=raw["chains"][0]
    zero=dict(first["calls"][0]);zero.update(contractSymbol="SPXW261218C04925000",strike=4925,bid=0,ask=0)
    crossed=dict(first["calls"][0]);crossed.update(contractSymbol="SPXW261218C04975000",strike=4975,bid=12,ask=11)
    first["calls"].extend([zero,crossed]);before=copy.deepcopy(raw)
    selected,exclusions=c.select_books(raw,settings())
    assert raw==before
    assert len(selected["chains"][0]["calls"])==5
    assert any("crossed_book" in e["reason"] for e in exclusions)
    assert all(r["bid"]==before["chains"][0]["calls"][i]["bid"] for i,r in enumerate(selected["chains"][0]["calls"]))


def test_fixed_window_excludes_far_strike_and_keeps_valid_books():
    raw=raw_fixture();row=dict(raw["chains"][0]["calls"][0])
    row.update(contractSymbol="SPXW261218C08000000",strike=8000,bid=.01,ask=.02)
    raw["chains"][0]["calls"].append(row)
    selected,excluded=c.select_books(raw,settings())
    assert len(selected["chains"][0]["calls"])==5
    assert excluded[-1]["reason"]=="outside_predeclared_strike_window"
    assert selected["spot_used_as_forward"] is False


def test_missing_underlying_does_not_guess_a_forward():
    raw=raw_fixture()
    for chain in raw["chains"]:chain.pop("underlying")
    with pytest.raises(ValueError,match="Missing positive underlying"):
        c.select_books(raw,settings())
    selected,_=c.select_books(raw,settings(reference_spot=5000))
    assert len(selected["chains"])==2


def test_positive_frame_has_two_independent_exact_checks(tmp_path):
    result,cfg=process(tmp_path)
    assert result["status"]=="accepted_exact_F0",result
    assert result["exact_audit"]["passed"] and result["exact_original_book_shape_audit"]["passed"]
    assert c.verify_bundle(tmp_path,cfg,Progress(tmp_path,quiet=True))["status"]=="verified_exact_F0"


def test_shape_incoherence_refused_even_when_parity_is_preserved(tmp_path):
    raw=raw_fixture()
    for field in ("calls","puts"):
        r=raw["chains"][0][field][2]
        r["bid"]+=100;r["ask"]+=100
    result,_=process(tmp_path,raw)
    assert result["status"]=="not_accepted" and result["reason"]=="F0_infeasible"
    retained=json.loads((tmp_path/"snapshot.json").read_text())
    assert retained["chains"][0]["calls"][2]["bid"]==raw["chains"][0]["calls"][2]["bid"]


def test_incompatible_parity_not_fixed_by_dropping_an_expiry(tmp_path):
    raw=raw_fixture()
    raw["chains"][0]["calls"][2]["bid"]+=100
    raw["chains"][0]["calls"][2]["ask"]+=100
    result,_=process(tmp_path,raw)
    assert result["status"]=="not_accepted" and result["reason"]=="parity_or_data_quality_failed"
    assert not (tmp_path/"F0.witness.json").exists()


def test_put_incoherence_cannot_hide_inside_wide_call_spreads(tmp_path):
    raw=raw_fixture()
    for row in raw["chains"][0]["calls"]:
        row["bid"]-=50;row["ask"]+=50
    row=raw["chains"][0]["puts"][2]
    row["bid"]+=40;row["ask"]+=40
    result,_=process(tmp_path,raw)
    curves=json.loads((tmp_path/"curves_estimees.csv.uncertainty.json").read_text())
    assert curves["accepted_count"]==2
    assert result["status"]=="not_accepted" and result["reason"]=="F0_infeasible"


def test_missing_preselected_expiry_rejects_entire_attempt(tmp_path):
    raw=raw_fixture();raw["errors"]=[{"expiry":"2027-02-19","error":"network error"}]
    result,_=process(tmp_path,raw)
    assert result["reason"]=="incomplete_collection"
    assert not (tmp_path/"F0.witness.json").exists()


def test_single_expiry_is_not_accepted(tmp_path):
    raw=raw_fixture();raw["chains"]=raw["chains"][:1]
    result,_=process(tmp_path,raw)
    assert result["reason"]=="insufficient_accepted_expiries"


def test_grid_budget_prevents_oversized_lp(tmp_path):
    result,_=process(tmp_path,max_nodes=6)
    assert result["reason"]=="grid_budget_exceeded"


def test_modified_quotes_fail_reverification(tmp_path):
    result,cfg=process(tmp_path)
    assert result["status"]=="accepted_exact_F0"
    p=tmp_path/"quotes.csv"
    import csv
    with p.open() as f:rows=list(csv.DictReader(f))
    rows[0]["bid"]=str(float(rows[0]["bid"])+.001)
    with p.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with pytest.raises(ValueError,match="Normalized quotes differ"):
        c.verify_bundle(tmp_path,cfg,Progress(tmp_path,quiet=True))


def test_fresh_fetch_records_underlying_and_never_pools(monkeypatch,tmp_path):
    fixture=raw_fixture()
    class Frame:
        def __init__(self,rows):self.rows=rows
        def to_json(self,**kwargs):return json.dumps(self.rows)
    class Ticker:
        def __init__(self,symbol):self.options=[c['expiry'] for c in fixture['chains']]
        def option_chain(self,expiry):
            chain=next(c for c in fixture['chains'] if c['expiry']==expiry)
            return SimpleNamespace(calls=Frame(chain['calls']),puts=Frame(chain['puts']),underlying=chain['underlying'])
    monkeypatch.setitem(sys.modules,'yfinance',SimpleNamespace(Ticker=Ticker))
    monkeypatch.setattr(c.time,'sleep',lambda seconds:None)
    monkeypatch.setattr(c,'utcnow',lambda:datetime(2026,10,26,14,tzinfo=timezone.utc))
    cfg=settings();progress=Progress(tmp_path,quiet=True)
    first=c.fetch_archive(cfg,tmp_path,progress);second=c.fetch_archive(cfg,tmp_path,progress)
    assert len(first['chains'])==len(second['chains'])==2
    assert second['chains'][0]['underlying']['regularMarketPrice']==5000


def test_closed_market_exits_before_any_worker(monkeypatch,tmp_path):
    monkeypatch.setattr(c,'utcnow',lambda:datetime(2026,10,25,17,tzinfo=timezone.utc))
    monkeypatch.setattr(c,'supervise',lambda *a,**kw:pytest.fail('No worker should start on a closed session'))
    assert c.main(['--out',str(tmp_path/'closed')])==4
    assert not (tmp_path/'closed'/'accepted').exists()


def test_child_termination_is_bounded():
    p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=os.name!='nt',
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
    c.terminate(p)
    assert p.poll() is not None


def test_timeout_cannot_report_acceptance(tmp_path):
    config=tmp_path/'cfg.json';config.write_text('{}')
    result=c.supervise(config,tmp_path,0)
    assert result['status']=='not_accepted' and result['reason']=='attempt_timeout'


