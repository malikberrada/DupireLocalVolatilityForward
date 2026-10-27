import copy
from datetime import datetime,timezone
from fractions import Fraction as Q
import json
from pathlib import Path
import pytest
import collect_coherent_yahoo as c
from test_collector_v1_compat import raw_fixture,settings
from dupire_joint.progress import Progress


def test_predeclared_mesh_does_not_adapt_to_prices():
    raw=raw_fixture()
    for chain in raw['chains']:
        for field,side in [('calls','C'),('puts','P')]:
            r=copy.deepcopy(chain[field][0]);r.update(strike=5025,
                contractSymbol='SPXW'+chain['expiry'].replace('-','')[2:]+side+'05025000',bid=9000,ask=9001)
            chain[field].append(r)
    selected,excluded=c.select_books(raw,settings(strike_step=50))
    require_ids={r['contractSymbol'] for chain in selected['chains'] for field in ('calls','puts') for r in chain[field]}
    assert len(require_ids)==20
    assert sum(r['reason']=='outside_predeclared_strike_mesh' for r in excluded)==4
    modified=copy.deepcopy(raw)
    for chain in modified['chains']:
        for field in ('calls','puts'):
            for row in chain[field]:row.update(bid=123,ask=124)
    second,_=c.select_books(modified,settings(strike_step=50))
    assert require_ids=={r['contractSymbol'] for chain in second['chains'] for field in ('calls','puts') for r in chain[field]}
    original={r['contractSymbol']:r for chain in raw['chains'] for field in ('calls','puts') for r in chain[field]}
    assert all(row==original[row['contractSymbol']] for chain in selected['chains'] for f in ('calls','puts') for row in chain[f])


def test_fractional_mesh_preserves_decimal_strikes():
    raw=raw_fixture()
    for chain in raw['chains']:
        for field,side in [('calls','C'),('puts','P')]:
            r=copy.deepcopy(chain[field][0]);r.update(strike=5002.5,
                contractSymbol='SPXW'+chain['expiry'].replace('-','')[2:]+side+'05002500')
            chain[field].append(r)
    selected,_=c.select_books(raw,settings(strike_step=2.5))
    assert any(Q(str(row['strike']))==Q('5002.5') for chain in selected['chains'] for row in chain['calls'])


def test_index_option_regular_hours_include_1610_et():
    assert c.session_window(datetime(2026,10,26,20,10,tzinfo=timezone.utc))['open']
    assert not c.session_window(datetime(2026,10,26,20,16,tzinfo=timezone.utc))['open']


def test_local_variance_upper_bound_is_enforced_without_tolerance():
    from valider_yahoo import exact_local_check
    grid={'times':['1/4','1'],'strikes':['9/10','1','11/10']}
    surface=['1/5','3/20','11/100','1/4','1/5','4/25']
    # Both slices have gamma=1; the sole cell's variance is exactly 2/15.
    for scheme in ('forward','backward'):
        assert exact_local_check(grid,surface,.05,.5,scheme)['passed']
        assert not exact_local_check(grid,surface,.05,.1,scheme)['passed']


@pytest.mark.parametrize('attempt',[1,2,3])
def test_real_yahoo_archives_pass_on_same_fixed_mesh(tmp_path,attempt):
    source=Path(__file__).resolve().parents[1]/'data/raw/yahoo/2026-10-26'/f'attempt_{attempt:02d}.json'
    raw=json.loads(source.read_text());cfg=settings(strike_step=50)
    c.save(tmp_path/'raw_snapshot.json',raw)
    result=c.process_archive(raw,cfg,tmp_path,Progress(tmp_path,quiet=True))
    assert result['status']=='accepted_exact_F0',result
    assert result['expiry_count']==5 and result['quote_count']==59
    assert result['joint_call_and_put_interval_count']==121
    cert=json.loads((tmp_path/'curves_estimees.csv.uncertainty.json').read_text())
    assert cert['accepted_count']==5 and cert['rejected_count']==0 and not cert['allow_partial']
    assert c.verify_bundle(tmp_path,cfg,Progress(tmp_path,quiet=True))['status']=='verified_exact_F0'
    selected=json.loads((tmp_path/'snapshot.json').read_text())
    original={r['contractSymbol']:r for chain in raw['chains'] for f in ('calls','puts') for r in chain[f]}
    assert all(row==original[row['contractSymbol']] for chain in selected['chains'] for f in ('calls','puts') for row in chain[f])


def test_dense_original_yahoo_frame_still_rejects(tmp_path):
    raw=json.loads((Path(__file__).resolve().parents[1]/'data/raw/yahoo/2026-10-26/attempt_03.json').read_text())
    cfg=settings(strike_step=0)
    c.save(tmp_path/'raw_snapshot.json',raw)
    result=c.process_archive(raw,cfg,tmp_path,Progress(tmp_path,quiet=True))
    assert result['status']=='not_accepted' and result['reason']=='parity_or_data_quality_failed'
    assert not (tmp_path/'F0.witness.json').exists()
