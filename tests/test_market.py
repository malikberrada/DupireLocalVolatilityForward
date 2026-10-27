import json
import pytest
from dupire_joint.market import normalize_snapshot


def test_normalization_preserves_crossed_quotes_and_separates_roots(tmp_path):
    archive={"chains":[{"symbol":"^SPX","expiry":"2027-01-15","calls":[
        {"contractSymbol":"SPXW270115C05000000","strike":5000,"bid":110,"ask":100},
        {"contractSymbol":"SPX270115C05000000","strike":5000,"bid":130,"ask":140},
        {"contractSymbol":"SPXW270115C05100000","strike":5100,"bid":0,"ask":0}]}]}
    snap=tmp_path/"snap.json";snap.write_text(json.dumps(archive))
    curves=tmp_path/"curves.csv"
    curves.write_text("symbol,root,expiry,time,forward,discount,style,settlement\n^SPX,SPXW,2027-01-15,0.2,5000,0.99,european,PM\n")
    q=normalize_snapshot(snap,curves,"^SPX","SPXW",tmp_path/"q.csv")
    assert len(q.time)==1 and q.bid[0]>q.ask[0]
    assert q.x[0]==1.
    assert q.bid[0]==pytest.approx(110/4950)
    with pytest.raises(ValueError,match="Missing verified"):
        normalize_snapshot(snap,curves,"^SPX","SPX",tmp_path/"bad.csv")
    with pytest.raises(ValueError):
        normalize_snapshot(snap,curves,"SPY","SPY",tmp_path/"bad.csv")

