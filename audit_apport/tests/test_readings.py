"""Evidence/approval gates. All test publications and annotations are synthetic."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from dossier import priority
from dossier import readings as r
from dossier import reading_sources as s
from dossier import reading_model as m
from dossier.io import write, read, sha, digest, seal


def synthetic_pdf(path, pages=2, blank=False):
    """Minimal PDF authored for tests; no third-party article is embedded."""
    texts = ["SYNTHETIC TEST PAPER - not an actual publication. "+
             "Theorem assumption feasibility forward backward bounds refinement discrete local volatility. "*22]*pages
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for i, text in enumerate(texts):
        page_id, stream_id = len(objects)+1, len(objects)+2
        kids.append(f"{page_id} 0 R")
        content = b"" if blank else ("BT /F1 9 Tf 30 760 Td ("+text+") Tj ET").encode()
        objects += [(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>").encode(),
                    b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"+content+b"\nendstream"]
    objects[1] = ("<< /Type /Pages /Count "+str(pages)+" /Kids ["+" ".join(kids)+"] >>").encode()
    raw, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(raw)); raw += f"{i} 0 obj\n".encode()+obj+b"\nendobj\n"
    xref = len(raw)
    raw += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    raw += b"".join(f"{v:010d} 00000 n \n".encode() for v in offsets[1:])
    raw += f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(raw)
    return path


@pytest.fixture
def campaign(tmp_path):
    paper = synthetic_pdf(tmp_path/"synthetic.pdf")
    registry = read(priority.ROOT/"bibliography/registry.json")
    registry["works"] = [{"id": "SYNTHETIC", "title": "Synthetic test paper", "url": "https://example.org/synthetic",
                          "selected_version": "test-v1", "access": "synthetic_fixture_only", "source_sha256": None,
                          "required_for_claims": ["C1", "C2", "C3"], "events": [
                              {"id": "test_event", "kind": "published-online", "date_parts": [2020, 1, 1],
                               "version_id": "test-v1", "evidence_url": "https://example.org/synthetic", "locator": "synthetic field"}]}]
    registry["reviews"] = []
    registry["new_evidence"] = ["Synthetic unit-test data, no actual scientific findings."]
    reg = tmp_path/"registry.json"; write(reg, registry)
    original = tmp_path/"priority"
    priority.generate(original, reg)
    out = tmp_path/"campaign"
    r.prepare(original, out, attachments=["SYNTHETIC="+str(paper)])
    return out


def approved(campaign, full=False):
    edited = read(campaign/"lectures_a_valider.json")
    work = edited["works"][0]
    work.update(reviewer="Synthetic test reader", review_date="2026-10-27", identity_confirmed=True,
                full_text_extent_confirmed=full, pages_reviewed=[1, 2] if full else [1])
    tasks = read(campaign/"tasks.json")
    blocks = s.passages(read(campaign/read(campaign/"documents.json")[0]["pages_path"]))
    evidence = blocks[0]["id"]
    for decision, task in zip(work["decisions"], tasks):
        decision.update(decision="accepted", scope="full_work" if full else "selected_statement")
        analysis = decision["analysis"]
        analysis.update(hypotheses="Synthetic test hypotheses.", conclusion="Synthetic test conclusion.",
                        relation="different_statement", derivability="not_a_direct_corollary",
                        derivation_note="Synthetic test analysis, not an actual theorem exclusion.", evidence_ids=[evidence])
        for axis in analysis["axes"]:
            axis.update(prior_condition="Synthetic prior condition.", relation="different_framework", evidence_ids=[evidence])
    return edited


def test_pdf_page_locations_are_physical_and_scans_are_not_marked_read(tmp_path):
    pdf = synthetic_pdf(tmp_path/"paper.pdf")
    text = s.extract(pdf)
    assert text["page_count"] == 2 and text["location_kind"] == "pdf_physical_page"
    assert text["status"] == "text_extracted_extent_unconfirmed"
    blank = s.extract(synthetic_pdf(tmp_path/"blank.pdf", blank=True))
    assert blank["status"] == "ocr_or_text_recovery_needed"


def test_http_200_publisher_preview_is_not_usable_full_text(tmp_path):
    path = tmp_path/"preview.html"
    path.write_text("<html><script>do_not_include</script><p>This is a preview of subscription content.</p>"+"abstract "*150+"</html>")
    extracted = s.extract(path)
    assert extracted["status"] == "preview_or_access_wall"
    assert "do_not_include" not in json.dumps(extracted)


def test_cambridge_extract_page_is_not_classified_as_main_text(tmp_path):
    path = tmp_path/"extract.html"
    path.write_text("<html><h1>Synthetic paper</h1><h2>Extract</h2><p>Get access</p>"+"metadata "*200+"</html>")
    assert s.extract(path)["status"] == "html_metadata_or_excerpt"


def test_acquisition_stays_pending_and_builds_all_three_distinct_hypothesis_sets(campaign):
    checked = r.verify(campaign)
    assert checked["sources_extracted"] == 1 and checked["comparison_tasks"] == 3
    assert checked["readings_automatically_completed"] == 0
    tasks = read(campaign/"tasks.json")
    assert [len(t["axes"]) for t in tasks] == [14, 6, 7]
    assert all(d["decision"] == "pending" for d in read(campaign/"lectures_a_valider.json")["works"][0]["decisions"])


def test_kundu_cv_is_never_a_thesis_download_candidate():
    routes = read(r.ROOT/"bibliography/source_routes.json")["routes"]
    assert routes["KUNDU2017"] == []
    assert not any("nktomar.pdf" in u for urls in routes.values() for u in urls)


def test_missing_pdf_is_logged_and_does_not_complete_a_reading(tmp_path):
    work = {"id": "SYNTHETIC", "title": "Synthetic test paper"}
    result = r.acquire(work, tmp_path, local=tmp_path/"missing.pdf")
    assert result["status"] == "source_unavailable_or_not_usable" and not result["reading_completed"]
    assert result["attempts"][0]["status"] == "retrieval_or_extraction_failed"


def test_fallback_does_not_overwrite_earlier_retrieval_evidence(tmp_path, monkeypatch):
    first = b"<html>This is a preview of subscription content.</html>"
    second = ("Synthetic test paper "+"theorem assumption bounds "*100).encode()
    def fetch(url, timeout):
        raw = first if url.endswith("preview") else second
        return raw, {"requested_url": url, "raw_sha256": "recorded"}
    monkeypatch.setattr(s, "download", fetch)
    monkeypatch.setattr(s, "crossref_routes", lambda doi, timeout: (["https://example.org/full"], {}))
    result = r.acquire({"id": "SYNTHETIC", "title": "Synthetic test paper", "doi": "10.1234/test"}, tmp_path,
                       urls=["https://example.org/preview"], download_open=True, discover=True)
    assert len(list((tmp_path/"documents/SYNTHETIC").glob("attempt_*"))) == 2
    assert (tmp_path/"documents/SYNTHETIC/attempt_01.html").read_bytes() == first
    assert result["source_path"].endswith("attempt_02.txt")


def test_forged_or_unavailable_passage_is_rejected(campaign):
    task = read(campaign/"tasks.json")[0]
    draft = r.empty_analysis(task)
    draft["evidence_ids"] = ["p9999:l0001-0016"]
    with pytest.raises(ValueError, match="unavailable passage"):
        m.validate_draft(draft, task, {b["id"] for b in task["selected_passages"]})


def test_resolved_hypothesis_requires_source_and_all_axes(campaign):
    task = read(campaign/"tasks.json")[0]
    draft = r.empty_analysis(task)
    draft["axes"][0]["relation"] = "same_condition"
    with pytest.raises(ValueError, match="needs a source passage"):
        m.validate_draft(draft, task, {b["id"] for b in task["selected_passages"]})
    draft["axes"].pop()
    with pytest.raises(ValueError, match="omitted/duplicated"):
        m.validate_draft(draft, task, set())


@pytest.mark.parametrize("url", ["https://api.example.org", "http://example.org", "http://localhost:11434/x",
                                 "http://user:secret@localhost:11434", "http://localhost:11434?target=remote"])
def test_article_text_is_not_sent_to_a_remote_model(url):
    with pytest.raises(ValueError, match="local loopback"):
        m.local_endpoint(url)


def test_model_api_contract_and_fake_completion_fields_are_checked(campaign, monkeypatch):
    task = read(campaign/"tasks.json")[0]
    answer = r.empty_analysis(task)
    seen = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            return json.dumps({"done": True, "done_reason": "stop", "model": "synthetic-model",
                               "message": {"content": json.dumps(answer)}}).encode()
    class Opener:
        def open(self, request, timeout):
            seen.update(json.loads(request.data)); return Response()
    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *args: Opener())
    draft, receipt = m.analyse(task, task["selected_passages"], "synthetic-model")
    assert seen["stream"] is False and isinstance(seen["format"], dict)
    assert seen['think'] is False and seen['options']['num_predict']==8000
    assert seen['format']['properties']['axes']['required']==[a['id'] for a in task['axes']]
    assert set(seen['format']['properties']['evidence_ids']['items']['enum']) == {b['id'] for b in task['selected_passages']}
    assert not receipt["human_approved"] and receipt["scope"] == "selected_statement"
    answer["scientific_priority_certified"] = True
    with pytest.raises(ValueError, match="missing/extra fields"):
        m.analyse(task, task["selected_passages"], "synthetic-model")


def test_model_drafts_remain_pending_even_when_analysis_is_resolved(campaign, tmp_path, monkeypatch):
    def fake(task, blocks, *args):
        analysis = r.empty_analysis(task)
        analysis.update(relation="different_statement", derivability="not_a_direct_corollary", evidence_ids=[blocks[0]["id"]])
        return analysis, {"model_requested": "synthetic-model", "human_approved": False}
    monkeypatch.setattr(r, "model_analyse", fake)
    out = tmp_path/"drafts"
    result = r.analyse_campaign(campaign, out, "synthetic-model", max_pairs=1)
    assert result["drafts_ready"] == 1 and result["readings_automatically_completed"] == 0
    work = read(out/"lectures_a_valider.json")["works"][0]
    assert work["reviewer"] is None and work["identity_confirmed"] is False
    assert all(d["decision"] == "pending" for d in work["decisions"])


def test_unavailable_model_is_recorded_and_partial_work_is_saved(campaign, tmp_path, monkeypatch):
    def failed(*args): raise OSError("synthetic unavailable model")
    monkeypatch.setattr(r, "model_analyse", failed)
    result = r.analyse_campaign(campaign, tmp_path/"drafts", "synthetic-model", max_pairs=1)
    assert result["drafts_failed"] == 1
    assert (tmp_path/"drafts/lectures_a_valider.json").exists()


def test_pending_workbook_cannot_clear_bibliographic_gaps(campaign, tmp_path):
    with pytest.raises(ValueError, match="No reader-accepted"):
        r.export(campaign, campaign/"lectures_a_valider.json", tmp_path/"export")


def test_accepted_selected_reading_exports_sources_and_keeps_whole_work_gap(campaign, tmp_path):
    path = tmp_path/"reviewed.json"; write(path, approved(campaign))
    out = tmp_path/"export"
    result = r.export(campaign, path, out)
    assert result["accepted_comparisons_exported"] == 3
    assert all(s == "comparison_incomplete" for s in result["claim_statuses"].values())
    assert priority.verify(out)["reading_evidence"]["accepted_comparisons"] == 3


def test_full_synthetic_review_clears_reading_gaps_but_still_needs_public_project_record(campaign, tmp_path):
    path = tmp_path/"reviewed.json"; write(path, approved(campaign, full=True))
    result = r.export(campaign, path, tmp_path/"export")
    assert set(result["claim_statuses"].values()) == {"comparison_complete_public_project_record_missing"}
    assert not result["scientific_priority_certified"]


def test_full_review_cannot_omit_a_page(campaign):
    value = approved(campaign, full=True)
    value["works"][0]["pages_reviewed"] = [1]
    with pytest.raises(ValueError, match="every page"):
        r.accepted_reviews(campaign, value)


def test_full_review_cannot_leave_hypotheses_unresolved(campaign):
    value = approved(campaign, full=True)
    value["works"][0]["decisions"][0]["analysis"]["axes"][0]["relation"] = "unresolved"
    with pytest.raises(ValueError, match="each hypothesis"):
        r.accepted_reviews(campaign, value)


def test_source_identity_and_hash_must_match_reader_declaration(campaign):
    value = approved(campaign)
    value["works"][0]["source_sha256"] = "a"*64
    with pytest.raises(ValueError, match="different source bytes"):
        r.accepted_reviews(campaign, value)
    value = approved(campaign)
    value["works"][0]["identity_confirmed"] = False
    with pytest.raises(ValueError, match="source identity"):
        r.accepted_reviews(campaign, value)


def test_full_reading_is_not_backdated_to_first_work_posting(campaign, tmp_path):
    value = approved(campaign, full=True)
    value["works"][0]["version_id"] = "different-later-test-version"
    path = tmp_path/"reviewed.json"; write(path, value)
    result = r.export(campaign, path, tmp_path/"export")
    assert set(result["claim_statuses"].values()) == {"comparison_incomplete"}


def test_changed_page_index_is_detected_even_if_outer_manifest_is_resealed(campaign):
    doc = read(campaign/"documents.json")[0]
    path = campaign/doc["pages_path"]
    data = read(path); data["pages"][0]["lines"][0] = "forged text"
    write(path, data); doc["pages_sha256"] = sha(path)
    write(campaign/"documents.json", [doc]); seal(campaign)
    with pytest.raises(ValueError, match="Page/line evidence changed"):
        r.verify(campaign)


def test_changed_exported_locator_is_detected_after_resealing(campaign, tmp_path):
    path = tmp_path/"reviewed.json"; write(path, approved(campaign))
    out = tmp_path/"export"; r.export(campaign, path, out)
    data = read(out/"reading_evidence/accepted_reviews.json")
    data[0]["evidence_ids"] = ["p9999:l0001-0016"]
    write(out/"reading_evidence/accepted_reviews.json", data); seal(out)
    with pytest.raises(ValueError, match="differs from accepted reading"):
        priority.verify(out)


def test_offline_verification_does_not_call_retrieval_or_model(campaign, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("No network/model during verify")
    monkeypatch.setattr(s, "download", forbidden)
    monkeypatch.setattr(r, "model_analyse", forbidden)
    assert r.verify(campaign)["network_used"] is False


def test_locator_must_match_the_actual_page_and_line_ids(campaign,tmp_path):
    path=tmp_path/'reviewed.json';write(path,approved(campaign))
    out=tmp_path/'export';r.export(campaign,path,out)
    accepted=read(out/'reading_evidence/accepted_reviews.json')
    accepted[0]['locator']='invented page 9999'
    write(out/'reading_evidence/accepted_reviews.json',accepted)
    registry=read(out/'registry.json')
    next(v for v in registry['reviews'] if v['claim_id']==accepted[0]['claim_id'])['locator']='invented page 9999'
    write(out/'registry.json',registry)
    with pytest.raises(ValueError,match='locator differs'):
        r.verify_export_evidence(out)


def test_optional_reextraction_compares_every_page(campaign):
    assert r.verify(campaign, reextract=True)["text_extraction_replayed"] is True


def test_project_hypotheses_cannot_be_silently_removed(campaign):
    data = read(campaign/"protocol.json")
    data["claims"]["C1"].pop()
    write(campaign/"protocol.json", data); seal(campaign)
    with pytest.raises(ValueError, match="project hypotheses"):
        r.verify(campaign)


def test_campaign_cannot_be_modified_by_nested_outputs(campaign):
    with pytest.raises(ValueError, match="outside the sealed"):
        r.analyse_campaign(campaign, campaign/"drafts", "synthetic-model")
    with pytest.raises(ValueError, match="outside the sealed"):
        r.export(campaign, campaign/"lectures_a_valider.json", campaign/"export")


def test_reader_can_record_one_comparison_without_approving_other_pairs(campaign, tmp_path):
    value = approved(campaign)
    for d in value['works'][0]['decisions']: d['decision']='pending'
    source = tmp_path/'draft.json'; write(source,value)
    out = tmp_path/'reviewed.json'
    result = r.approve(campaign,source,out,'SYNTHETIC','C1','Synthetic test reader','2026-10-27','1-2',True)
    decisions=read(out)['works'][0]['decisions']
    assert [d['decision'] for d in decisions] == ['accepted','pending','pending']
    assert result['scientific_priority_certified'] is False


def test_reader_identity_confirmation_and_page_ranges_are_explicit(campaign,tmp_path):
    with pytest.raises(ValueError, match='confirm the source identity'):
        r.approve(campaign,campaign/'lectures_a_valider.json',tmp_path/'reviewed.json',
                  'SYNTHETIC','C1','Synthetic test reader','2026-10-27','1-2')
    assert r.page_range('1-3,5,7-8') == [1,2,3,5,7,8]
    with pytest.raises(ValueError):r.page_range('8-2')


def test_truncated_final_answer_and_counts_are_saved_without_thinking_text(campaign,tmp_path,monkeypatch):
    task=read(campaign/'tasks.json')[0]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,size):return json.dumps({'done':True,'done_reason':'length','eval_count':5000,
            'prompt_eval_count':2100,'message':{'content':'{"hypotheses":','thinking':'PRIVATE_LOCAL_MODEL_TRACE_MARKER'}}).encode()
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr(m.urllib.request,'build_opener',lambda *args:Opener())
    target=tmp_path/'response.json'
    with pytest.raises(m.AnalysisError) as caught:
        m.analyse(task,task['selected_passages'],'synthetic-model',diagnostic=target)
    assert caught.value.code=='truncated_output'
    saved=read(target)
    assert saved['done_reason']=='length' and saved['eval_count']==5000
    assert saved['content']=='{"hypotheses":'
    assert 'PRIVATE_LOCAL_MODEL_TRACE_MARKER' not in target.read_text()


def test_single_json_fence_is_recorded_but_unavailable_citations_are_still_refused(campaign,tmp_path,monkeypatch):
    task=read(campaign/'tasks.json')[0];answer=r.empty_analysis(task)
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,size):return json.dumps({'done':True,'done_reason':'stop',
            'message':{'content':'```json\n'+json.dumps(answer)+'\n```','thinking':None}}).encode()
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr(m.urllib.request,'build_opener',lambda *args:Opener())
    draft,receipt=m.analyse(task,task['selected_passages'],'synthetic-model')
    assert receipt['generation']['single_json_fence_removed'] is True
    answer['evidence_ids']=['p9999:l0001-0016']
    with pytest.raises(m.AnalysisError) as caught:m.analyse(task,task['selected_passages'],'synthetic-model')
    assert caught.value.code=='unknown_evidence_id'


def test_transient_failure_is_retried_and_its_category_is_retained(campaign,tmp_path,monkeypatch):
    calls=[]
    def fake(task,blocks,*args):
        calls.append(task['pair_id'])
        if len(calls)==1:raise m.AnalysisError('truncated_output','Synthetic truncation',{'done_reason':'length'})
        value=r.empty_analysis(task);value['hypotheses']='Synthetic prior hypotheses.'
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',fake)
    result=r.analyse_campaign(campaign,tmp_path/'drafts','synthetic-model',pairs=['SYNTHETIC_C2'])
    assert result['drafts_ready']==1 and result['drafts_failed']==0 and len(calls)==2
    attempts=read(tmp_path/'drafts/diagnostics/SYNTHETIC_C2.attempts.json')
    assert attempts[0]['error_code']=='truncated_output' and attempts[1]['status']=='draft_ready'


def test_resumption_reuses_successful_drafts_and_retries_only_missing_pairs(campaign,tmp_path,monkeypatch):
    def first(task,blocks,*args):
        if task['claim_id']!='C2':raise m.AnalysisError('truncated_output','Synthetic failure')
        value=r.empty_analysis(task);value['hypotheses']='Synthetic prior statement.'
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',first)
    old=tmp_path/'old'
    initial=r.analyse_campaign(campaign,old,'synthetic-model',retries=0)
    assert initial['drafts_ready']==1 and initial['drafts_failed']==2
    calls=[]
    def second(task,blocks,*args):
        calls.append(task['claim_id'])
        value=r.empty_analysis(task);value['hypotheses']='Synthetic prior statement.'
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',second)
    new=tmp_path/'new'
    result=r.analyse_campaign(campaign,new,'synthetic-model',resume=old)
    assert result['drafts_reused']==1 and result['drafts_ready']==3 and result['drafts_failed']==0
    assert calls==['C1','C1','C3']  # C1 is analysed in two complete hypothesis batches.
    assert (old/'SYNTHETIC_C2.draft.json').read_bytes()==(new/'SYNTHETIC_C2.draft.json').read_bytes()
    assert all(d['decision']=='pending' for d in read(new/'lectures_a_valider.json')['works'][0]['decisions'])


def test_resume_rejects_a_different_campaign(campaign,tmp_path,monkeypatch):
    import shutil
    def fake(task,blocks,*args):
        value=r.empty_analysis(task);value['hypotheses']='Synthetic prior statement.'
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',fake)
    old=tmp_path/'old';r.analyse_campaign(campaign,old,'synthetic-model',max_pairs=1)
    other=tmp_path/'other';shutil.copytree(campaign,other)
    write(other/'extra_record.json',{'different_campaign':True});seal(other)
    with pytest.raises(ValueError,match='different reading campaign'):
        r.analyse_campaign(other,tmp_path/'new','synthetic-model',resume=old)


def test_resume_supports_completed_v050_metadata(campaign,tmp_path,monkeypatch):
    def fake(task,blocks,*args):
        value=r.empty_analysis(task);value['hypotheses']='Synthetic prior statement.'
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',fake)
    old=tmp_path/'old';r.analyse_campaign(campaign,old,'synthetic-model',max_pairs=1)
    data=read(old/'analysis.json');data['format']='dupire-reading-model-drafts-v1'
    write(old/'analysis.json',data)
    path=old/'SYNTHETIC_C1.draft.json';saved=read(path)
    task=read(campaign/'tasks.json')[0]
    saved['receipt']={'model_requested':'synthetic-model','draft_sha256':digest(saved['analysis']),
                      'prompt_evidence_ids':[b['id'] for b in task['selected_passages']],
                      'human_approved':False,'scope':'selected_statement'}
    write(path,saved)
    log=read(old/'analysis_log.json');log[0]['receipt']=saved['receipt'];write(old/'analysis_log.json',log)
    seal(old)
    result=r.analyse_campaign(campaign,tmp_path/'new','synthetic-model',resume=old)
    assert result['drafts_reused']==1 and result['drafts_generated']==2


def test_batch_disagreement_stays_unresolved_and_retains_every_axis(campaign):
    from dossier.reading_recovery import merge_batches
    task=read(campaign/'tasks.json')[0]
    first={**task,'axes':task['axes'][:7]};second={**task,'axes':task['axes'][7:]}
    a,b=r.empty_analysis(first),r.empty_analysis(second)
    a['relation']='different_statement';a['evidence_ids']=[task['selected_passages'][0]['id']]
    merged=merge_batches([a,b],task,{v['id'] for v in task['selected_passages']})
    assert len(merged['axes'])==14 and merged['relation']=='unresolved'
    assert any('divergentes' in x for x in merged['limitations'])


def test_named_result_anchor_wins_over_generic_keyword_density():
    from dossier.reading_recovery import select_anchored
    extracted={'pages':[{'page':1,'lines':['forward backward feasibility bound '*20]},
                        {'page':2,'lines':['Theorem 16. A named calibration result with its assumptions.']}]}
    task={'work_id':'SYNTHETIC','claim_id':'C1'}
    registry={'reviews':[{'work_id':'SYNTHETIC','locator':'Theorem 16'}]}
    chosen=select_anchored(extracted,task,registry,max_blocks=1)
    assert chosen[0]['page']==2


def test_project_reference_contains_equations_and_is_labelled_as_project_work():
    from dossier.reading_recovery import project_reference
    for cid in ['C1','C2','C3']:
        ref=project_reference(r.ROOT,cid)
        assert ref['role']=='project_result_not_prior_art' and len(ref['source_sha256'])==64
        assert ref['text'].strip()


def test_workbook_diagnosis_does_not_invent_failure_causes(campaign):
    from dossier.reading_recovery import diagnose
    d=diagnose(campaign/'lectures_a_valider.json')
    assert d['drafts_present']==0 and d['empty_pairs_with_sources']==3
    assert d['failure_details_supplied'] is False and d['exact_failure_causes_known'] is False


def test_quality_warnings_do_not_silently_change_scientific_annotations(campaign):
    value=r.empty_analysis(read(campaign/'tasks.json')[0])
    value['derivation_note']="Le travail antérieur ne contient pas ce résultat."
    saved=deepcopy(value)
    assert 'whole_work_absence_asserted_from_selected_passages' in m.quality_warnings(value)
    assert value==saved


def test_partial_model_result_returns_nonzero_exit_status(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'analyse_campaign',lambda *args,**kwargs:{'status':'partial_model_drafts','drafts_failed':1})
    assert r.main(['analyser','--campaign',str(tmp_path),'--out',str(tmp_path/'out'),'--model','synthetic-model'])==2


@pytest.mark.parametrize('good',[
    {'SYNTHETIC0_C3','SYNTHETIC1_C2','SYNTHETIC2_C2','SYNTHETIC2_C3'},
    {'SYNTHETIC0_C1','SYNTHETIC0_C2','SYNTHETIC0_C3','SYNTHETIC1_C2','SYNTHETIC1_C3',
     'SYNTHETIC2_C2','SYNTHETIC2_C3','SYNTHETIC4_C1','SYNTHETIC4_C2','SYNTHETIC4_C3',
     'SYNTHETIC5_C2','SYNTHETIC5_C3'}
])
def test_observed_partial_patterns_are_resumed_without_losing_drafts(campaign,tmp_path,monkeypatch,good):
    # Six explicitly synthetic works, three claims each; no actual publication is invented.
    registry=read(campaign/'input_priority/registry.json')
    template=registry['works'][0];registry['works']=[]
    for i in range(6):
        work=deepcopy(template);work['id']='SYNTHETIC'+str(i);registry['works'].append(work)
    reg=tmp_path/'six_registry.json';write(reg,registry)
    source_priority=tmp_path/'six_priority';priority.generate(source_priority,reg)
    paper=campaign/read(campaign/'documents.json')[0]['source_path']
    six=tmp_path/'six_campaign'
    r.prepare(source_priority,six,attachments=[w['id']+'='+str(paper) for w in registry['works']])
    def partial(task,blocks,*args):
        if task['pair_id'] not in good:raise m.AnalysisError('truncated_output','Synthetic truncation, not a diagnosis of the user run')
        value=r.empty_analysis(task);value['hypotheses']='Synthetic prior hypotheses.'
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',partial)
    old=tmp_path/'partial';first=r.analyse_campaign(six,old,'synthetic-model',retries=0)
    assert first['drafts_ready']==len(good) and first['drafts_failed']==18-len(good)
    called=[]
    def fixed(task,blocks,*args):
        called.append(task['pair_id'])
        value=r.empty_analysis(task);value['hypotheses']='Synthetic prior hypotheses.'
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',fixed)
    new=tmp_path/'resumed';last=r.analyse_campaign(six,new,'synthetic-model',resume=old)
    assert last['drafts_reused']==len(good) and last['drafts_generated']==18-len(good)
    assert last['drafts_ready']==18 and last['drafts_failed']==0
    assert len(set(called))==18-len(good) and not good.intersection(called)
    for pair in good:assert (old/(pair+'.draft.json')).read_bytes()==(new/(pair+'.draft.json')).read_bytes()
    assert last['scientific_priority_certified'] is False


def test_resumption_preserves_the_existing_diagnostic_files(campaign,tmp_path,monkeypatch):
    def fake(task,blocks,*args):
        write(args[6],{'synthetic_final_response':'diagnostic preservation fixture'})
        value=r.empty_analysis(task);value['hypotheses']='Synthetic prior hypotheses.'
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',fake)
    old=tmp_path/'old';r.analyse_campaign(campaign,old,'synthetic-model',max_pairs=1)
    new=tmp_path/'new';r.analyse_campaign(campaign,new,'synthetic-model',resume=old)
    for source in (old/'diagnostics').glob('SYNTHETIC_C1*'):
        assert (new/'diagnostics'/source.name).read_bytes()==source.read_bytes()


def test_named_axis_schema_and_wire_conversion_preserve_the_actual_comparisons(campaign,monkeypatch):
    task=read(campaign/'tasks.json')[0];answer=r.empty_analysis(task)
    answer['axes']={a['axis_id']:a for a in reversed(answer['axes'])}
    answer['axes'][task['axes'][0]['id']]['prior_condition']='Synthetic prior condition, kept verbatim.'
    seen={}
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,size):return json.dumps({'done':True,'done_reason':'stop','message':{'content':json.dumps(answer)}}).encode()
    class Opener:
        def open(self,request,timeout):seen.update(json.loads(request.data));return Response()
    monkeypatch.setattr(m.urllib.request,'build_opener',lambda *args:Opener())
    value,receipt=m.analyse(task,task['selected_passages'],'synthetic-model')
    assert [a['axis_id'] for a in value['axes']]==[a['id'] for a in task['axes']]
    assert value['axes'][0]['prior_condition']=='Synthetic prior condition, kept verbatim.'
    assert receipt['generation']['wire_axes_layout']=='named_properties'
    schema=seen['format']['properties']['axes']
    assert schema['additionalProperties'] is False
    for key,row in schema['properties'].items():assert row['properties']['axis_id']['enum']==[key]
    assert json.loads(seen['messages'][1]['content'])['response_schema']==seen['format']


@pytest.mark.parametrize('corruption',['missing','mismatched_id','unknown_id'])
def test_named_axis_conversion_never_fills_or_renames_a_missing_hypothesis(campaign,corruption):
    task=read(campaign/'tasks.json')[0];answer=r.empty_analysis(task)
    answer['axes']={a['axis_id']:a for a in answer['axes']};first=task['axes'][0]['id']
    if corruption=='missing':del answer['axes'][first]
    elif corruption=='mismatched_id':answer['axes'][first]['axis_id']='invented_axis'
    else:answer['axes']['invented_axis']=deepcopy(answer['axes'][first])
    before=deepcopy(answer)
    with pytest.raises(m.AnalysisError):m.normalise_axes(answer,task)
    assert answer==before


def test_duplicate_json_keys_are_rejected_instead_of_silently_overwritten():
    with pytest.raises(m.AnalysisError) as caught:m.strict_json('{"axes":{"a":1,"a":2}}')
    assert caught.value.code=='duplicate_json_key'


@pytest.mark.parametrize('field,bad,code,path',[
    ('derivation_note','  ','empty_analysis_text','derivation_note'),
    ('axes',None,'invalid_field_type','axes'),
    ('relation',['unresolved'],'unknown_analysis_relation','relation'),
    ('evidence_ids',[None],'invalid_field_type','evidence_ids'),
])
def test_schema_failures_name_the_specific_field(campaign,field,bad,code,path):
    task=read(campaign/'tasks.json')[0];answer=r.empty_analysis(task);answer[field]=bad
    with pytest.raises(m.AnalysisError) as caught:m.validate_draft(answer,task,set())
    assert caught.value.code==code and caught.value.details['path']==path


def test_actual_model_response_and_validation_path_are_both_saved(campaign,tmp_path,monkeypatch):
    task=read(campaign/'tasks.json')[1];answer=r.empty_analysis(task);answer['axes'][0]['prior_condition']=None
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,size):return json.dumps({'done':True,'done_reason':'stop',
            'message':{'content':json.dumps(answer),'thinking':'PRIVATE SYNTHETIC TEXT'}}).encode()
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr(m.urllib.request,'build_opener',lambda *args:Opener())
    diagnostic=tmp_path/'response.json'
    with pytest.raises(m.AnalysisError):m.analyse(task,task['selected_passages'],'synthetic-model',diagnostic=diagnostic)
    saved=read(diagnostic)
    assert saved['validation_error']['code']=='empty_prior_condition'
    assert saved['validation_error']['details']['path']=='axes[0].prior_condition'
    assert json.loads(saved['content'])==answer
    assert 'PRIVATE SYNTHETIC TEXT' not in diagnostic.read_text()


def test_failed_multi_axis_response_is_recovered_by_complete_individual_calls(campaign,tmp_path,monkeypatch):
    called=[]
    def fake(task,blocks,*args):
        called.append([a['id'] for a in task['axes']])
        if len(task['axes'])>1:raise m.AnalysisError('incomplete_hypothesis_coverage','Synthetic omitted axis',{'missing':['synthetic']})
        value=r.empty_analysis(task);value['hypotheses']='Synthetic prior result, no priority conclusion.'
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',fake)
    out=tmp_path/'fallback';result=r.analyse_campaign(campaign,out,'synthetic-model',pairs=['SYNTHETIC_C2'],retries=0)
    assert result['drafts_ready']==1 and result['drafts_failed']==0
    assert len(called)==7 and len(called[0])==6 and all(len(x)==1 for x in called[1:])
    draft=read(out/'SYNTHETIC_C2.draft.json')
    assert len(draft['analysis']['axes'])==6 and draft['receipt']['single_axis_fallback_used'] is True
    assert draft['receipt']['human_approved'] is False
    assert all(d['decision']=='pending' for d in read(out/'lectures_a_valider.json')['works'][0]['decisions'])


def test_individual_recovery_still_rejects_an_invented_citation(campaign,tmp_path,monkeypatch):
    def fake(task,blocks,*args):
        if len(task['axes'])>1:raise m.AnalysisError('invalid_analysis_schema','Synthetic failure')
        value=r.empty_analysis(task);value['evidence_ids']=['p9999:l0001-0016']
        return value,{'human_approved':False}
    monkeypatch.setattr(r,'model_analyse',fake)
    out=tmp_path/'bad';result=r.analyse_campaign(campaign,out,'synthetic-model',pairs=['SYNTHETIC_C2'],retries=0)
    assert result['drafts_ready']==0 and result['drafts_failed']==1
    assert result['failure_counts']=={'unknown_evidence_id':1}
    assert not (out/'SYNTHETIC_C2.draft.json').exists()


def test_transport_failure_does_not_trigger_repeated_single_axis_calls(campaign,tmp_path,monkeypatch):
    called=[]
    def fake(task,blocks,*args):called.append(task);raise m.AnalysisError('transport_error','Synthetic offline server')
    monkeypatch.setattr(r,'model_analyse',fake)
    result=r.analyse_campaign(campaign,tmp_path/'offline','synthetic-model',pairs=['SYNTHETIC_C2'],retries=0)
    assert len(called)==1 and result['failure_counts']=={'transport_error':1}
