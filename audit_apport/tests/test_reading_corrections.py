"""Source-bound corrections and the exact, explicitly scoped arguments."""
from copy import deepcopy
from fractions import Fraction as Q
from pathlib import Path

import pytest

from dossier import reading_corrections as c
from dossier import readings
from dossier.argument_checks import verify_arguments, threshold_interval
from dossier.io import read, write, sha, digest
from dossier.reading_model import quality_warnings


@pytest.fixture
def reviewed_data():
    folder=c.ROOT/'validation/corrections'
    return read(folder/'input_workbook.json'),read(c.ROOT/'bibliography/corrections_v053.json'),read(folder/'source_bindings.json')


def decisions(book):
    return {w['work_id']+'_'+d['claim_id']:d for w in book['works'] for d in w['decisions']}


def test_reviewed_corrections_apply_to_exactly_eighteen_drafts_and_preserve_nineteen_untouched_cells(reviewed_data):
    original,packet,bindings=reviewed_data;before=deepcopy(original)
    corrected,changes=c.make_book(original,packet,bindings)
    assert len(changes)==18 and sum(len(d['analysis']['axes']) for d in packet['comparisons'])==162
    assert original==before
    old,new=decisions(original),decisions(corrected);affected={v['pair_id'] for v in changes}
    assert sum(old[p]==new[p] for p in old if p not in affected)==19
    assert all(v['decision']=='pending' for v in new.values())
    assert corrected['scientific_priority_certified'] is False
    for a,b in zip(original['works'],corrected['works']):
        assert {k:v for k,v in a.items() if k!='decisions'}=={k:v for k,v in b.items() if k!='decisions'}


def test_circular_attribution_is_removed_and_positive_diffusion_is_not_called_the_same_stencil_bounds(reviewed_data):
    original,packet,bindings=reviewed_data
    corrected,_=c.make_book(original,packet,bindings);rows=decisions(corrected)
    z=next(a for a in rows['ZHANG2025_C3']['analysis']['axes'] if a['axis_id']=='free_terminal_centre')
    assert z['relation']=='outside_cited_statement' and 'jamais un antécédent' in z['prior_condition']
    carr=next(a for a in rows['CARR2014_C3']['analysis']['axes'] if a['axis_id']=='positive_variance_bounds')
    assert carr['relation']=='different_framework'
    assert rows['BR2016_C3']['analysis']['derivability']=='component_only'
    assert rows['ZHANG2025_C1']['analysis']['derivability']=='not_a_direct_corollary'
    assert 'application littérale' in rows['ZHANG2025_C1']['analysis']['derivation_note']


def test_corrected_c1_notes_preserve_sufficiency_and_do_not_claim_scientific_originality(reviewed_data):
    corrected,_=c.make_book(*reviewed_data)
    for pair,d in decisions(corrected).items():
        if not d.get('bibliographic_verification'):continue
        assert 'la nouveauté réside' not in str(d['analysis']).lower()
        assert d['scope']=='selected_statement' and d['bibliographic_verification']['human_approved'] is False
        if pair.endswith('_C1'):assert 'suffisant' in d['analysis']['derivation_note']


@pytest.mark.parametrize('mutation',['analysis','source','accepted'])
def test_corrections_refuse_a_modified_draft_source_or_accepted_reading(reviewed_data,mutation):
    book,packet,bindings=reviewed_data;book=deepcopy(book)
    work=next(w for w in book['works'] if w['work_id']=='BR2016')
    if mutation=='analysis':work['decisions'][0]['analysis']['derivation_note']='Manual reader change must be preserved.'
    elif mutation=='source':work['source_sha256']='0'*64
    else:work['decisions'][0]['decision']='accepted'
    with pytest.raises(ValueError):c.make_book(book,packet,bindings)


def test_source_anchors_are_relocated_in_the_campaign_index_instead_of_changing_endpoint_digits(tmp_path,monkeypatch):
    monkeypatch.setattr(readings,'verify',lambda path:{'status':'synthetic_campaign_fixture'})
    paper=tmp_path/'synthetic.txt';paper.write_text('SYNTHETIC source, no real article.')
    source_hash=sha(paper)
    write(tmp_path/'documents.json',[{'work_id':'SYNTHETIC','source_sha256':source_hash,
                                    'source_path':'synthetic.txt','pages_path':'pages.json'}])
    packet={'sources':{'SYNTHETIC':{'source_sha256':source_hash,'version_id':'synthetic',
                                   'references':{'lemma':{'page':3,'needle':'Synthetic named result'}}}}}
    def index(prefix):
        write(tmp_path/'pages.json',{'extractor':'synthetic fixture','pages':[{'page':3,
             'lines':['Synthetic filler']*prefix+['Synthetic named result']+['Synthetic text']*30}]})
        return c.bind_references(tmp_path,packet)['SYNTHETIC']['references']['lemma']
    first,second=index(0),index(24)
    assert first['line']==1 and second['line']==25 and first['evidence_id']!=second['evidence_id']
    packet['sources']['SYNTHETIC']['references']['lemma']['needle']='Unavailable source anchor'
    with pytest.raises(ValueError,match='anchor is unavailable'):c.bind_references(tmp_path,packet)


@pytest.mark.parametrize('factor,feasible',[(Q(1,2),True),(Q(1),True),(Q(1001,1000),False)])
def test_threshold_derivation_at_and_on_each_side_of_the_boundary(factor,feasible):
    x,kappa,lower,upper,gamma=Q(3,2),Q(17),Q(2,100),Q(7,100),Q(5,3)
    critical=2*(upper-lower)/(x*x*kappa*lower*upper);dt=critical*factor
    result=threshold_interval(dt,x,kappa,lower,upper,gamma)
    assert result['nonempty'] is feasible
    if feasible:
        d=Q(result['lower_increment']);a=x*x*dt/2;g1=gamma-kappa*d
        assert g1>0 and a*lower*gamma<=d<=a*upper*gamma and a*lower*g1<=d<=a*upper*g1
    else:assert Q(result['lower_increment'])>Q(result['upper_increment'])


def test_exact_a5_obstruction_is_scoped_to_the_literal_hypothesis_mapping():
    checked=verify_arguments();a5=checked['ZHANG2025_C1_literal_A5_application']
    assert a5['C1_continuous_conditions_checked'] is True and a5['P_TT']=='0'
    assert Q(a5['bounds']['variance_min'])>Q(39,2000) and Q(a5['bounds']['variance_max'])<Q(41,2000)
    assert a5['positive_time_mesh_violates_displayed_A5_with_exact_zero_envelope'] is True
    assert 'does not disprove' in a5['scope'] and checked['scientific_priority_certified'] is False


def test_new_argument_warnings_are_review_prompts_and_do_not_relabel_the_scientific_decision(reviewed_data):
    original,_,_=reviewed_data
    d=decisions(original)['ZHANG2025_C3']['analysis'];before=deepcopy(d)
    assert 'project_result_misidentified_as_prior_art' in quality_warnings(d,'C3')
    assert d==before
    value=deepcopy(d);value['derivation_note']='La nouveauté réside dans cette formule.'
    assert 'unsupported_scientific_originality_assertion' in quality_warnings(value,'C3')
    value['derivation_note']='La condition quadratique est nécessaire au raffinement.'
    assert 'sufficient_C1_refinement_bound_mislabelled_necessary' in quality_warnings(value,'C1')
    assert 'sufficient_C1_refinement_bound_mislabelled_necessary' not in quality_warnings(value,'C3')


def test_saved_correction_dossier_recomputes_the_changes_and_never_approves_a_reading():
    result=c.verify_result(c.ROOT/'validation/corrections')
    assert result['comparisons_corrected']==18 and result['axis_cells_rewritten']==162
    assert result['source_bytes_reverified'] is False and result['human_readings_automatically_accepted']==0
    assert result['semantic_annotations_auto_verified'] is False


def test_affine_time_example_also_passes_the_existing_bernstein_certificate_checker():
    import numpy as np
    from dupire_joint.constructive import exact_check,mesh_plan
    data=read(c.ROOT/'validation/affine_time_bernstein.json')
    coefficients=np.array([[Q(x) for x in row] for row in data['coefficients']],dtype=object)
    spec={key:Q(value) for key,value in data['spec'].items()}
    observations=[[Q(v) for v in row] for row in data['observations']]
    checked=exact_check(coefficients,spec,observations)
    assert checked['passed'] is True
    assert all(checked['constants'][name]==0 for name in ['M3','M4','Mtt'])
    plan=mesh_plan(checked['constants'],spec,[Q(1,4),Q(3,10),Q(7,20)],[Q(9,10),Q(1),Q(27,25)])
    assert plan['guaranteed_level']==0


def test_named_source_selection_finds_alphanumeric_lemma_ids_in_french_locators():
    from dossier.reading_recovery import select_anchored
    data={'pages':[{'page':1,'lines':['forward backward variance refinement '*30]},
                   {'page':5,'lines':['Lemma S0.2 (operator stability). Synthetic named statement.']}]}
    selected=select_anchored(data,{'work_id':'SYNTHETIC','claim_id':'C1'},
                             {'reviews':[{'work_id':'SYNTHETIC','locator':'§3.4, lemme S0.2'}]},max_blocks=1)
    assert selected[0]['page']==5
