import copy
from datetime import date, timedelta
import json
import sys
from types import SimpleNamespace
import pytest
from dupire_joint.market_quality import audit_archive, select_expiries
from dupire_joint.market import snapshot
from dupire_joint.progress import Progress


def archive(calls,puts):
    def row(side,k,b,a):
        return {"contractSymbol":"SPXW261120"+side+f"{k*1000:08d}","strike":k,"bid":b,"ask":a,"lastPrice":999}
    return {"source":"test","chains":[{"symbol":"^SPX","expiry":"2026-11-20",
        "calls":[row("C",*r) for r in calls],"puts":[row("P",*r) for r in puts]}]}


def test_spread_selection_filters_before_capping():
    expiries=[(date(2026,10,25)+timedelta(days=i)).isoformat() for i in range(1,101)]
    chosen=select_expiries(expiries[::-1],4,"spread",7,90,"2026-10-25T16:00:00Z")
    assert len(chosen)==4 and len(set(chosen))==4
    assert chosen[0]=="2026-11-01" and chosen[-1]=="2027-01-23"
    assert select_expiries(expiries,4,"front",7,90,"2026-10-25")==expiries[6:10]


@pytest.mark.parametrize("cap",[1,2,5,50])
def test_spread_unique_sorted_and_bounded(cap):
    raw=[(date(2026,10,25)+timedelta(days=i)).isoformat() for i in range(30)]
    chosen=select_expiries(raw+raw,cap,"spread",asof="2026-10-25")
    assert chosen==sorted(set(chosen)) and len(chosen)==min(cap,30)


@pytest.mark.parametrize("kw",[{"cap":0},{"cap":2,"mode":"x"},{"cap":2,"min_days":-1},{"cap":2,"min_days":10,"max_days":9}])
def test_invalid_expiry_selection_refused(kw):
    with pytest.raises(ValueError): select_expiries([],**kw)


def test_zero_books_are_diagnosed_without_last_price_substitution():
    a=archive([(5000,0,0)],[(5000,0,0)]);before=copy.deepcopy(a)
    q=audit_archive(a,check_parity=True);g=q["groups"][0]
    assert g["calls_zero_book"]==g["puts_zero_book"]==1
    assert g["matched_valid_strikes"]==0 and g["parity_status"]=="insufficient_pairs"
    assert q["has_enough_paired_books"] is False
    assert a==before


def test_valid_books_at_different_strikes_do_not_make_pairs():
    q=audit_archive(archive([(4900,10,11)],[(5100,10,11)]))
    g=q["groups"][0]
    assert g["calls_valid_book"]==g["puts_valid_book"]==1
    assert g["matched_valid_strikes"]==0


def test_count_is_distinct_from_compatible_parity():
    a=archive([(4900,200,201),(5000,100,101),(5100,150,151)],
              [(4900,10,11),(5000,10,11),(5100,10,11)])
    q=audit_archive(a,check_parity=True)
    assert q["has_enough_paired_books"]
    assert not q["has_compatible_parity"]
    assert q["groups"][0]["parity_reason"]=="empty_parity_set"


def test_crossed_book_preserves_strict_policy_and_explains_raw_counts():
    a=archive([(4900,200,190),(5000,100,101),(5100,40,41)],
              [(4900,10,11),(5000,10,11),(5100,50,51)])
    g=audit_archive(a,min_pairs=2,check_parity=True)["groups"][0]
    assert g["matched_valid_strikes"]==2
    assert g["parity_status"]=="rejected" and "crossed_book" in g["parity_reason"]


def test_snapshot_quality_gate_retains_original_data(tmp_path,monkeypatch):
    a=archive([(5000,0,0)],[(5000,0,0)])["chains"][0]
    class Frame:
        def __init__(self,rows):self.rows=rows
        def to_json(self,**kw):return json.dumps(self.rows)
    class Ticker:
        def __init__(self,symbol):self.options=["2026-11-20"]
        def option_chain(self,expiry):return SimpleNamespace(calls=Frame(a["calls"]),puts=Frame(a["puts"]))
    monkeypatch.setitem(sys.modules,"yfinance",SimpleNamespace(Ticker=Ticker))
    monkeypatch.setattr("dupire_joint.market.time.sleep",lambda seconds:None)
    with pytest.raises(SystemExit) as exc:
        snapshot(["^SPX"],tmp_path,Progress(tmp_path,quiet=True),require_matched_pairs=3)
    assert exc.value.code==3
    data=json.loads((tmp_path/"snapshot.json").read_text())
    assert data["chains"][0]["calls"][0]["ask"]==0
    quality=json.loads((tmp_path/"snapshot.quality.json").read_text())
    assert not quality["has_enough_paired_books"] and quality["snapshot_sha256"]


def test_quality_distinguishes_policy_rejection_from_parity_incompatibility():
    a=archive([(4900,200,201),(5000,101,102),(5100,11,12),(6000,11,9)],
              [(4900,10,11),(5000,10,11),(5100,20,21)])
    # Remaining differences decrease by about 99 per 100 points, a compatible D.
    strict=audit_archive(a,check_parity=True)
    selected=audit_archive(a,check_parity=True,crossed_policy="exclude")
    assert not strict["has_compatible_parity"]
    assert selected["has_compatible_parity"]
    assert selected["groups"][0]["parity_status"]=="compatible_intervals"
    assert len(selected["groups"][0]["excluded_crossed_books"])==1
    assert selected["original_snapshot_all_quotes_certified"] is False
