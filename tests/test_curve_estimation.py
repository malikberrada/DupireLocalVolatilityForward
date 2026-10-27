import csv
import json
from fractions import Fraction as Q
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.optimize import linprog
from dupire_joint.curve_estimation import (
    parity_polygon, polygon_summary, estimate_archive, estimate_command,
    matched_pairs, normalize_estimated, verify_curves, outward, observation_times,
)
from dupire_joint.settlements import scheduled_fixing, load_overrides, aware_utc
from dupire_joint.market import normalize_snapshot
from dupire_joint.progress import Progress


def option(root, expiry, side, strike, price, spread):
    return {"contractSymbol": root + expiry.replace("-", "")[2:] + side + f"{int(strike*1000):08d}",
            "strike": float(strike), "bid": float(price-spread), "ask": float(price+spread)}


def fixture_archive(spread=Q(1), roots=("SPXW",), expiries=("2026-12-18", "2027-01-15")):
    chains = []
    for expiry in expiries:
        for root in roots:
            calls, puts = [], []
            for k in (4500, 4750, 5000, 5250, 5500):
                y = Q(4950) - Q(99,100) * k
                c = max(y, Q(0)) + 40
                calls.append(option(root, expiry, "C", k, c, spread))
                puts.append(option(root, expiry, "P", k, c-y, spread))
            chains.append({"symbol": "^SPX", "expiry": expiry, "calls": calls, "puts": puts})
    return {"started_utc": "2026-10-26T14:00:00+00:00", "ended_utc": "2026-10-26T14:00:10+00:00", "chains": chains}


def settings(**kw):
    return {"symbol": "^SPX", "root": "SPXW", "min_days": "7", "max_days": "365",
            "min_pairs": 3, "max_pairs": 2000, "time_limit": 30, "asof": None, **kw}


def run_estimate(tmp_path, archive=None, **kw):
    snapshot = tmp_path/"snapshot.json"
    snapshot.write_text(json.dumps(archive or fixture_archive()))
    output = tmp_path/"estimated"
    output.mkdir(exist_ok=True)
    args = SimpleNamespace(snapshot=str(snapshot), out=str(output), symbol="^SPX", root="SPXW",
                           min_days=7., max_days=365., min_pairs=3, max_pairs=2000, time_limit=30,
                           asof=None, settlements=None, allow_partial=False, normalize=True)
    for k,v in kw.items():
        setattr(args,k,v)
    estimate_command(args, Progress(output,quiet=True))
    return snapshot, output/"curves_estimees.csv", output


def test_exact_point_recovers_A_D_without_rate_prior():
    pairs,_,_=matched_pairs(fixture_archive(Q(0))["chains"][:1],"SPXW")
    summary=polygon_summary(parity_polygon(pairs))
    assert summary["nominal"] == {"prepaid_forward":"4950", "discount":"99/100", "forward":"5000"}
    assert len(summary["vertices_A_D"])==1


def test_empty_intersection_is_not_repaired():
    assert parity_polygon([(Q(100),Q(10),Q(10)),(Q(200),Q(9),Q(9)),(Q(300),Q(10),Q(10))])==[]


def test_positive_discount_and_prepaid_identifiability():
    poly=parity_polygon([(Q(1),Q(-10),Q(10)),(Q(2),Q(-10),Q(10))])
    with pytest.raises(ValueError,match="unidentified"):
        polygon_summary(poly)


@pytest.mark.parametrize("seed",range(6))
def test_exact_polygon_extrema_match_independent_LP(seed):
    rng=np.random.default_rng(seed)
    pairs=[]
    for k in range(100,901,100):
        y=Q(900)-Q(97,100)*k
        width=Q(int(rng.integers(1,20)))
        pairs.append((Q(k),y-width,y+width))
    summary=polygon_summary(parity_polygon(pairs))
    matrix=[]; rhs=[]
    for k,l,u in pairs:
        matrix.extend([[1,-float(k)],[-1,float(k)]]);rhs.extend([float(u),float(-l)])
    for key,index in (("prepaid_forward",0),("discount",1)):
        for sign,which in ((1,0),(-1,1)):
            cost=[0.,0.];cost[index]=sign
            sol=linprog(cost,A_ub=matrix,b_ub=rhs,bounds=[(0,None),(0,None)],method="highs")
            assert sol.success
            assert float(Q(summary["bounds"][key][which]))==pytest.approx(sol.x[index],rel=1e-9)
    for a,d in summary["vertices_A_D"]:
        assert all(l<=Q(a)-Q(d)*k<=u for k,l,u in pairs)
    # Independent Charnes-Cooper LP for the fractional objective A/D.
    cc_matrix=[];cc_rhs=[]
    for k,l,u in pairs:
        cc_matrix.extend([[1,-float(u)],[-1,float(l)]]);cc_rhs.extend([float(k),float(-k)])
    for sign,which in ((1,0),(-1,1)):
        sol=linprog([sign,0],A_ub=cc_matrix,b_ub=cc_rhs,bounds=[(0,None),(0,None)],method="highs")
        assert sol.success
        assert float(Q(summary["bounds"]["forward"][which]))==pytest.approx(sol.x[0],rel=1e-9)


def test_contract_roots_are_separate():
    a=fixture_archive(roots=("SPXW","SPX"))
    out=estimate_archive(a,settings())
    assert out["accepted_count"]==2
    assert all(g["root"]=="SPXW" and g["pair_count"]==5 for g in out["groups"])


@pytest.mark.parametrize("field,value,reason",[("bid",99999,"crossed_book"),("strike",4501,"mismatch")])
def test_contradictory_books_reject_expiry(field,value,reason):
    a=fixture_archive();a["chains"][0]["calls"][0][field]=value
    out=estimate_archive(a,settings())
    assert out["rejected_count"]==1
    assert reason in out["groups"][0]["reason"]


def test_ambiguous_duplicates_fail():
    a=fixture_archive()
    r=dict(a["chains"][0]["calls"][0]);r["ask"]+=1
    a["chains"][0]["calls"].append(r)
    out=estimate_archive(a,settings())
    assert "ambiguous_duplicate" in out["groups"][0]["reason"]


def test_missing_books_logged_and_insufficient_pairs_rejected():
    a=fixture_archive();a["chains"][0]["puts"]=a["chains"][0]["puts"][:2]
    a["chains"][0]["calls"][0]["bid"]=None
    out=estimate_archive(a,settings())
    assert out["groups"][0]["pair_count"]==1
    assert out["groups"][0]["excluded_books"]
    assert out["groups"][0]["reason"]=="insufficient_matched_strikes"


def test_complete_cli_backend_export_verify_and_envelopes(tmp_path):
    snapshot,curves,out=run_estimate(tmp_path)
    cert=verify_curves(snapshot,curves)
    assert cert["accepted_count"]==2
    assert cert["quote_synchronization_verified"] is False
    q=normalize_snapshot(snapshot,curves,"^SPX","SPXW",out/"again.csv")
    with (out/"again.csv.uncertainty.csv").open() as f:
        rows=list(csv.DictReader(f))
    for i,r in enumerate(rows):
        for key in ("time","x","bid","ask"):
            assert float(r[key+"_lower"])<=getattr(q,key)[i]<=float(r[key+"_upper"])
            assert Q.from_float(float(r[key+"_lower"]))<=Q(r[key+"_lower_exact"])
            assert Q.from_float(float(r[key+"_upper"]))>=Q(r[key+"_upper_exact"])
    meta=json.loads((out/"again.csv.metadata.json").read_text())
    assert meta["forward_discount_uncertainty_propagated"]
    assert meta["robust_calibration_certified"] is False


@pytest.mark.parametrize("target",["snapshot","csv","certificate"])
def test_tampering_is_detected(tmp_path,target):
    snapshot,curves,_=run_estimate(tmp_path)
    if target=="snapshot":
        snapshot.write_text(snapshot.read_text()+" ")
    elif target=="csv":
        curves.write_text(curves.read_text().replace("european","american"))
    else:
        side=Path(str(curves)+".uncertainty.json")
        cert=json.loads(side.read_text());cert["groups"][0]["bounds"]["discount"][0]="0"
        side.write_text(json.dumps(cert))
    with pytest.raises(ValueError,match="mismatch|failed"):
        verify_curves(snapshot,curves)


def test_missing_sidecar_cannot_be_silently_downgraded(tmp_path):
    snapshot,curves,out=run_estimate(tmp_path)
    Path(str(curves)+".uncertainty.json").unlink()
    with pytest.raises(ValueError,match="require"):
        normalize_snapshot(snapshot,curves,"^SPX","SPXW",out/"q.csv")


def test_rejected_expiry_needs_explicit_allow_partial(tmp_path):
    a=fixture_archive();a["chains"][0]["puts"]=[]
    with pytest.raises(SystemExit) as e:
        run_estimate(tmp_path,a)
    assert e.value.code==3
    assert not (tmp_path/"estimated"/"quotes.csv").exists()
    snap,curves,out=run_estimate(tmp_path,a,allow_partial=True)
    c=verify_curves(snap,curves)
    assert c["accepted_count"]==1 and c["rejected_count"]==1
    assert (out/"quotes.csv").is_file()


def test_failed_repeat_preserves_and_relocates_earlier_exports(tmp_path):
    snap,curves,out=run_estimate(tmp_path)
    original=(out/"quotes.csv").read_bytes()
    a=fixture_archive();a["chains"][0]["puts"]=[]
    with pytest.raises(SystemExit):
        run_estimate(tmp_path,a)
    assert not (out/"quotes.csv").exists()
    archived=list((out/"previous_exports").glob("*/quotes.csv"))
    assert len(archived)==1 and archived[0].read_bytes()==original


def test_degenerate_segment_is_retained_exactly():
    s=polygon_summary(parity_polygon([(Q(100),Q(900),Q(900)),(Q(200),Q(799),Q(801))]))
    assert len(s["vertices_A_D"])==2
    assert s["bounds"]["discount"]==["99/100","101/100"]


def test_pair_budget_does_not_subsample_or_claim_infeasibility():
    r=estimate_archive(fixture_archive(),settings(max_pairs=4))
    assert r["accepted_count"]==0
    assert "pair_budget_exceeded" in r["groups"][0]["reason"]


def test_known_true_normalization_is_covered_by_exported_envelopes(tmp_path):
    snap,curves,out=run_estimate(tmp_path)
    with (out/"quotes.csv.uncertainty.csv").open() as f:
        rows=list(csv.DictReader(f))
    archive=json.loads(snap.read_text())
    raw={r["contractSymbol"]:r for c in archive["chains"] for r in c["calls"]}
    for row in rows:
        call=raw[row["contract"]]
        values={"x":Q(str(call["strike"]))/5000,"bid":Q(str(call["bid"]))/4950,
                "ask":Q(str(call["ask"]))/4950}
        for key,value in values.items():
            assert Q(row[key+"_lower_exact"])<=value<=Q(row[key+"_upper_exact"])


def test_explicit_window_exclusion_recorded():
    a=fixture_archive(expiries=("2026-10-27","2026-12-18"))
    r=estimate_archive(a,settings())
    assert r["outside_window_count"]==1 and r["accepted_count"]==1


def test_timezone_DST_and_early_close():
    assert scheduled_fixing("^SPX","SPXW","2026-10-30")["fixing_utc"].startswith("2026-10-30T20:00")
    assert scheduled_fixing("^SPX","SPXW","2026-11-06")["fixing_utc"].startswith("2026-11-06T21:00")
    assert scheduled_fixing("^XSP","XSP","2026-11-27")["fixing_utc"].startswith("2026-11-27T18:00")
    assert scheduled_fixing("^SPX","SPX","2026-12-18")["fixing_utc"].startswith("2026-12-18T14:30")


@pytest.mark.parametrize("expiry",["2026-12-25","2026-12-26","2029-01-19"])
def test_unknown_or_closed_sessions_not_guessed(expiry):
    with pytest.raises(ValueError):
        scheduled_fixing("^SPX","SPXW",expiry)


def test_override_and_mandatory_timestamp_offset(tmp_path):
    p=tmp_path/"fix.csv"
    p.write_text("symbol,root,expiry,fixing_utc,settlement,source\n^SPX,SPXW,2029-01-19,2029-01-19T21:00:00Z,PM,verified_test_schedule\n")
    r=scheduled_fixing("^SPX","SPXW","2029-01-19",load_overrides(p))
    assert r["calendar"]=="explicit_override"
    with pytest.raises(ValueError,match="offset"):
        aware_utc("2026-10-26T14:00:00")


def test_asof_is_not_last_trade_date():
    with pytest.raises(ValueError,match="started_utc"):
        observation_times({"lastTradeDate":"2026-10-26"})
    at,start,end,source=observation_times(fixture_archive())
    assert start<at<end and source=="retrieval_window_not_bid_ask_time"


def test_outward_rounding_for_exact_endpoints():
    for f in [Q(1,10),Q(2,3),Q(0),Q(5000,997)]:
        assert Q.from_float(outward(f,True))<=f<=Q.from_float(outward(f,False))


def test_forward_fractional_extrema_cover_interior():
    pairs,_,_=matched_pairs(fixture_archive()["chains"][:1],"SPXW")
    s=polygon_summary(parity_polygon(pairs))
    lo,hi=map(Q,s["bounds"]["forward"])
    poly=[tuple(map(Q,p)) for p in s["vertices_A_D"]]
    for p in poly:
        for q in poly:
            aa,dd=((p[j]+2*q[j])/3 for j in (0,1))
            assert lo<=aa/dd<=hi


def with_unpaired_crossed_book():
    a=fixture_archive()
    a["chains"][0]["calls"].append(option("SPXW","2026-12-18","C",6000,Q(10),Q(-1)))
    return a


def test_explicit_exclusion_recovers_otherwise_compatible_expiry():
    a=with_unpaired_crossed_book()
    before=json.dumps(a,sort_keys=True)
    strict=estimate_archive(a,settings())
    cleaned=estimate_archive(a,settings(crossed_policy="exclude"))
    assert strict["accepted_count"]==1 and "crossed_book" in strict["groups"][0]["reason"]
    assert cleaned["accepted_count"]==2 and cleaned["groups"][0]["pair_count"]==5
    e=[e for e in cleaned["groups"][0]["excluded_books"] if e.get("policy")=="explicit_crossed_book_exclusion"]
    assert len(e)==1 and e[0]["bid"]==11 and e[0]["ask"]==9
    assert before==json.dumps(a,sort_keys=True)


@pytest.mark.parametrize("field,side",[("calls","C"),("puts","P")])
def test_crossed_member_removes_only_its_pair(field,side):
    a=fixture_archive()
    a["chains"][0][field][2]["bid"]=1000
    r=estimate_archive(a,settings(crossed_policy="exclude"))
    assert r["accepted_count"]==2 and r["groups"][0]["pair_count"]==4
    assert r["groups"][0]["unmatched_strikes"]==["5000"]


def test_exclusion_does_not_repair_incompatible_valid_intervals():
    a=with_unpaired_crossed_book()
    c=a["chains"][0]["calls"][2]
    c["bid"]+=1000;c["ask"]+=1000
    r=estimate_archive(a,settings(crossed_policy="exclude"))
    assert r["groups"][0]["reason"]=="empty_parity_set"
    assert r["groups"][0]["pair_count"]==5


@pytest.mark.parametrize("problem",["mismatch","duplicate"])
def test_exclude_mode_keeps_other_integrity_checks(problem):
    a=with_unpaired_crossed_book()
    if problem=="mismatch":a["chains"][0]["calls"][0]["strike"]+=1
    else:
        row=dict(a["chains"][0]["calls"][0]);row["ask"]+=1
        a["chains"][0]["calls"].append(row)
    r=estimate_archive(a,settings(crossed_policy="exclude"))
    assert r["groups"][0]["status"]=="rejected"
    assert problem in r["groups"][0]["reason"]


def test_unknown_crossed_policy_refused():
    with pytest.raises(ValueError,match="Unknown crossed"):
        matched_pairs(fixture_archive()["chains"],"SPXW","silently_repair")


def test_excluded_books_not_exported_and_nominal_certificate_rechecks(tmp_path):
    snap,curves,out=run_estimate(tmp_path,with_unpaired_crossed_book(),crossed_policy="exclude")
    cert=verify_curves(snap,curves)
    assert cert["accepted_count"]==2 and cert["settings"]["crossed_policy"]=="exclude"
    q=normalize_estimated(snap,curves,"^SPX","SPXW",out/"filtered.csv")
    assert len(q.time)==10  # five original calls per expiry; crossed extra call omitted
    meta=json.loads((out/"filtered.csv.metadata.json").read_text())
    assert meta["crossed_policy"]=="exclude" and meta["original_snapshot_all_quotes_certified"] is False
    assert any("crossed_book" in e["reason"] for e in meta["excluded_books"])


def test_tampered_exclusion_policy_invalidates_curve_verification(tmp_path):
    snap,curves,out=run_estimate(tmp_path,with_unpaired_crossed_book(),crossed_policy="exclude")
    side=Path(str(curves)+".uncertainty.json")
    cert=json.loads(side.read_text());cert["settings"]["crossed_policy"]="reject"
    side.write_text(json.dumps(cert))
    with pytest.raises(ValueError,match="failed"):
        verify_curves(snap,curves)
