"""Chronology/evidence gates. Positive fixtures are explicitly synthetic."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest

from dossier import priority as p
from dossier.io import read, write, sha, seal


@pytest.fixture
def synthetic(tmp_path):
    """Invented records exercise logic; they are NOT research evidence."""
    article = tmp_path/"synthetic_article.txt"
    article.write_text("SYNTHETIC TEST FIXTURE, no actual theorem or publication.\n")
    public = tmp_path/"synthetic_project.txt"
    public.write_text("SYNTHETIC TEST FIXTURE, no actual public project. C1 C2 C3.\n")
    registry = read(p.ROOT/"bibliography/registry.json")
    registry["new_evidence"] = ["SYNTHETIC TEST FIXTURE ONLY"]
    registry["works"] = [{"id": "SYNTHETIC", "title": "Synthetic test work, not an actual reference",
                          "url": "https://example.org/synthetic", "selected_version": "test-v1",
                          "access": "test_fixture", "source_sha256": sha(article),
                          "required_for_claims": ["C1", "C2", "C3"],
                          "events": [{"id": "test-publication", "kind": "published-online", "date_parts": [2020, 1, 1],
                                      "version_id": "test-v1", "evidence_url": "https://example.org/synthetic",
                                      "locator": "synthetic publication field"}]}]
    registry["reviews"] = [{"work_id": "SYNTHETIC", "claim_id": cid, "version_id": "test-v1",
                            "reviewer": "Synthetic test reviewer", "review_date": "2026-10-27",
                            "source_sha256": sha(article), "scope": "full_work", "relation": "different_statement",
                            "locator": "Synthetic section", "hypotheses": "Synthetic hypotheses",
                            "conclusion": "Synthetic conclusion", "derivability": "not_a_direct_corollary",
                            "derivation_note": "Synthetic annotation only, not an actual semantic analysis."}
                           for cid in ("C1", "C2", "C3")]
    reg = tmp_path/"synthetic_registry.json"
    write(reg, registry)
    record = {"format": "dupire-project-public-record-v1", "identifier": "SYNTHETIC-NOT-A-PUBLICATION",
              "version": "synthetic-v1", "public_url": "https://example.org/synthetic-project",
              "date_parts": [2021, 5, 10], "source_sha256": sha(public),
              "claim_locators": {cid: "Synthetic section "+cid for cid in ("C1", "C2", "C3")},
              "metadata": {"provider": "Synthetic test provider", "record_url": "https://example.org/synthetic-project",
                           "locator": "synthetic field", "date_kind": "published-online"}}
    rec = tmp_path/"synthetic_release.json"
    write(rec, record)
    return reg, rec, ["SYNTHETIC="+str(article), "PROJECT="+str(public)]


def build(tmp_path, synthetic, **kwargs):
    reg, rec, sources = synthetic
    out = tmp_path/"out"
    p.generate(out, reg, attachments=sources, project_record=rec, **kwargs)
    return out, read(out/"priority.json")


@pytest.mark.parametrize("parts,lo,hi", [([1947], date(1947, 1, 1), date(1947, 12, 31)),
                                        ([1947, 1], date(1947, 1, 1), date(1947, 1, 31)),
                                        ([2024, 2, 29], date(2024, 2, 29), date(2024, 2, 29))])
def test_partial_dates_keep_their_precision(parts, lo, hi):
    assert p.interval(parts) == (lo, hi)
    assert len(p.date_record(parts)["date_parts"]) == len(parts)


@pytest.mark.parametrize("parts", [[], [True], [2023, 2, 29], [2020, 13], [2020, 1, 1, 1]])
def test_invalid_dates_fail_closed(parts):
    with pytest.raises((ValueError, TypeError)):
        p.interval(parts)


def test_imprecise_overlapping_dates_do_not_invent_priority():
    assert p.temporal_order([2020], [2020, 5, 10]) == "overlapping_or_same_date"
    assert p.temporal_order([2019], [2020, 1]) == "definitely_before"


def test_metadata_creation_is_never_publication_and_digitisation_is_not_first_print():
    work = {"id": "SYNTHETIC", "doi": "10.1234/test"}
    snapshot = {"work_id": "SYNTHETIC", "provider": "Crossref", "url": "https://api.crossref.org/works/test",
                "projection": {"DOI": "10.1234/test", "created": {"date-parts": [[1900]]},
                               "published-print": {"date-parts": [[1947, 1]]},
                               "published-online": {"date-parts": [[2008, 10, 24]]}}}
    events = p.crossref_events(work, snapshot)
    assert {e["kind"] for e in events} == {"published-print", "published-online"}
    assert p.earliest(events)["latest_possible"] == "1947-01-31"


def test_snapshot_doi_cannot_be_swapped():
    with pytest.raises(ValueError, match="DOI mismatch"):
        p.crossref_events({"id": "X", "doi": "10.1234/a"},
                          {"work_id": "X", "provider": "Crossref", "projection": {"DOI": "10.1234/b"}})


def test_dates_after_cutoff_are_not_prior_art(tmp_path, synthetic):
    reg = read(synthetic[0])
    reg["works"][0]["events"][0]["date_parts"] = [2026, 12, 1]
    write(synthetic[0], reg)
    _, data = build(tmp_path, synthetic)
    assert data["chronology"][0]["events"] == []
    assert "reviewed_version_public_date_unresolved" in data["comparison"][0]["blockers"]


def test_earliest_work_date_does_not_backdate_a_later_unpinned_version(tmp_path, synthetic):
    reg = read(synthetic[0])
    reg["works"][0]["events"][0]["version_id"] = "earlier-unreviewed-v0"
    write(synthetic[0], reg)
    _, data = build(tmp_path, synthetic)
    work = data["chronology"][0]
    assert work["earliest_documented_work_availability"] is not None
    assert work["selected_version_availability"] is None
    assert all(c["status"] == "comparison_incomplete" for c in data["claims"])


def test_default_corpus_is_not_silently_certified(tmp_path):
    p.generate(tmp_path/"out")
    d = read(tmp_path/"out/priority.json")
    assert (d["works"], d["comparison_cells"]) == (13, 37)
    assert d["project_public_record"]["status"] == "public_disclosure_not_supplied"
    assert all(c["status"] == "comparison_incomplete" for c in d["claims"])
    kkt = next(c for c in d["chronology"] if c["work_id"] == "KKT2024")
    assert any(e["date"]["display"] == "2023-03-10" for e in kkt["events"])
    assert not d["scientific_priority_certified"]


def test_complete_synthetic_documentation_remains_corpus_limited(tmp_path, synthetic):
    _, d = build(tmp_path, synthetic)
    assert all(c["status"] == "priority_argument_documented_in_declared_corpus" for c in d["claims"])
    assert not d["scientific_priority_certified"]
    assert not d["semantic_annotations_auto_verified"]
    assert not d["provider_authentication"]


def test_complete_comparison_without_public_version_does_not_establish_project_chronology(tmp_path, synthetic):
    reg, _, sources = synthetic
    p.generate(tmp_path/"out", reg, attachments=sources[:1])
    d = read(tmp_path/"out/priority.json")
    assert all(c["status"] == "comparison_complete_public_project_record_missing" for c in d["claims"])


def test_a_full_source_attachment_does_not_widen_a_selected_statement_review(tmp_path, synthetic):
    reg = read(synthetic[0])
    for r in reg["reviews"]:
        r["scope"] = "selected_statement"
    write(synthetic[0], reg)
    _, d = build(tmp_path, synthetic)
    assert all(c["status"] == "comparison_incomplete" for c in d["claims"])
    assert all(c["source_hash_bound"] for c in d["comparison"])


@pytest.mark.parametrize("derivation,relation", [("not_a_direct_corollary", "equivalent_or_stronger"),
                                                ("direct_specialization", "different_statement")])
def test_prior_equivalence_or_specialization_challenges_a_novelty_claim(tmp_path, synthetic, derivation, relation):
    reg = read(synthetic[0])
    reg["reviews"][0].update(derivability=derivation, relation=relation)
    write(synthetic[0], reg)
    _, d = build(tmp_path, synthetic)
    assert d["claims"][0]["status"] == "prior_equivalent_or_direct_specialization_identified"
    assert d["claims"][1]["status"] == "priority_argument_documented_in_declared_corpus"


def test_later_reviewed_equivalence_is_not_mislabelled_as_prior(tmp_path, synthetic):
    reg = read(synthetic[0])
    reg["works"][0]["events"][0]["date_parts"] = [2022, 1, 1]
    reg["reviews"][0]["relation"] = "equivalent_or_stronger"
    write(synthetic[0], reg)
    _, d = build(tmp_path, synthetic)
    assert d["comparison"][0]["dated_equivalence"] == "equivalent_in_later_reviewed_version"
    assert d["claims"][0]["status"] == "priority_argument_documented_in_declared_corpus"


def test_equivalence_with_overlapping_date_precision_remains_unordered(tmp_path, synthetic):
    reg = read(synthetic[0])
    reg["works"][0]["events"][0]["date_parts"] = [2021]
    reg["reviews"][0]["relation"] = "equivalent_or_stronger"
    write(synthetic[0], reg)
    _, d = build(tmp_path, synthetic)
    assert d["comparison"][0]["version_temporal_order"] == "overlapping_or_same_date"
    assert d["claims"][0]["status"] == "equivalence_or_specialization_requires_chronology"


def test_new_review_requires_the_exact_source_bytes(tmp_path, synthetic):
    reg = read(synthetic[0])
    edit = tmp_path/"review.json"
    r = deepcopy(reg["reviews"][0])
    r["source_sha256"] = "a"*64
    write(edit, [r])
    with pytest.raises(ValueError, match="exact reviewed source"):
        build(tmp_path, synthetic, reviews=edit)


def test_an_access_wall_is_not_a_full_text_review(tmp_path, synthetic):
    reg = read(synthetic[0])
    article = Path(synthetic[2][0].split("=", 1)[1])
    article.write_text("<html>This is a preview of subscription content</html>")
    for r in reg["reviews"]:
        r["source_sha256"] = sha(article)
    write(synthetic[0], reg)
    edit = tmp_path/"review.json"
    write(edit, [reg["reviews"][0]])
    with pytest.raises(ValueError, match="preview/access wall"):
        build(tmp_path, synthetic, reviews=edit)


def test_private_created_timestamp_cannot_be_a_public_project_record(tmp_path, synthetic):
    record = read(synthetic[1])
    record["metadata"]["date_kind"] = "created"
    write(synthetic[1], record)
    with pytest.raises(ValueError, match="Private timestamps"):
        build(tmp_path, synthetic)


def test_edited_conclusion_fails_even_after_resealing(tmp_path, synthetic):
    out, data = build(tmp_path, synthetic)
    data["scientific_priority_certified"] = True
    write(out/"priority.json", data)
    seal(out)
    with pytest.raises(ValueError, match="conclusions differ"):
        p.verify(out)


def test_changed_reviewed_source_is_detected(tmp_path, synthetic):
    out, _ = build(tmp_path, synthetic)
    (out/"sources/SYNTHETIC.txt").write_text("changed source")
    seal(out)
    with pytest.raises(ValueError, match="Attachment changed"):
        p.verify(out)


def test_verify_never_uses_network_and_rejects_refresh_options(tmp_path, synthetic, monkeypatch):
    out, _ = build(tmp_path, synthetic)
    def forbidden(*args, **kwargs):
        raise AssertionError("Network is forbidden during verification")
    monkeypatch.setattr(p.urllib.request, "urlopen", forbidden)
    assert p.verify(out)["network_used"] is False
    with pytest.raises(ValueError, match="cannot be mixed"):
        p.main(["--verify", str(out), "--refresh-metadata"])


def test_failed_metadata_refresh_keeps_frozen_evidence_without_promoting_readings(tmp_path, monkeypatch):
    def unavailable(work):
        raise OSError("synthetic provider failure")
    monkeypatch.setattr(p, "fetch_crossref", unavailable)
    result = p.generate(tmp_path/"out", refresh=True)
    assert result["network_used"] is True  # attempts occurred, including failed requests
    assert result["verification_network_used"] is False
    log = read(tmp_path/"out/refresh_log.json")
    assert len(log["results"]) == 7
    assert all(r["status"] == "refresh_failed_frozen_snapshot_retained" and not r["readings_promoted"] for r in log["results"])
    assert all(c["status"] == "comparison_incomplete" for c in read(tmp_path/"out/priority.json")["claims"])


def test_successful_metadata_refresh_does_not_promote_access_or_readings(tmp_path, monkeypatch):
    def updated(work):
        snapshot = read(p.ROOT/"bibliography"/work["snapshot"])
        if work["id"] == "KKT2024":
            snapshot["projection"]["published-online"]["date-parts"] = [[2022, 1, 1]]
        return snapshot
    monkeypatch.setattr(p, "fetch_crossref", updated)
    p.generate(tmp_path/"out", refresh=True)
    d = read(tmp_path/"out/priority.json")
    kkt = next(w for w in d["chronology"] if w["work_id"] == "KKT2024")
    assert kkt["selected_version_availability"]["latest_possible"] == "2022-01-01"
    registry = read(tmp_path/"out/registry.json")
    assert next(w for w in registry["works"] if w["id"] == "KKT2024")["access"] == "abstract_and_public_appendix_reviewed"
    assert all(c["status"] == "comparison_incomplete" for c in d["claims"])


def test_unsupported_universal_priority_flag_is_rejected(tmp_path, synthetic):
    reg = read(synthetic[0])
    reg["scientific_priority_certified"] = True
    write(synthetic[0], reg)
    with pytest.raises(ValueError, match="universal priority"):
        build(tmp_path, synthetic)


def test_output_cannot_be_nested_in_the_input_audit(tmp_path):
    with pytest.raises(ValueError, match="outside the mathematical audit"):
        p.generate(tmp_path/"input/output", audit_dir=tmp_path/"input")
