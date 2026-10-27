"""Acquire -> extract -> compare -> review -> export to the existing priority audit.

Acquisition and model drafts never complete a reading. Export accepts explicit
reader decisions and checks source bytes, physical/virtual locations and scope.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import shutil
import tempfile

from .io import read, write, copy, sha, digest, require, safe_child, seal, check_manifest
from . import priority
from . import reading_sources as sources
from .reading_model import validate_draft, local_endpoint, analyse as model_analyse

ROOT = Path(__file__).resolve().parents[1]
READY = {"text_extracted_extent_unconfirmed", "text_extraction_partial"}


def progress(phase, **details):
    print(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "phase": phase, **details},
                     ensure_ascii=False), flush=True)


def new_folder(out):
    out = Path(out).resolve()
    require(not out.exists() or not any(out.iterdir()), "Use a new output folder to preserve previous readings")
    out.mkdir(parents=True, exist_ok=True)
    return out


def protocol():
    original = read(ROOT/"literature/theoremes.json")
    c1 = [{"id": a["id"], "condition": a["project_condition"]} for a in original["axes"][:14]]
    def axes(items):
        return [{"id": key, "condition": condition} for key, condition in items]
    return {"format": "dupire-reading-protocol-v1", "claims": {
        "C1": c1,
        "C2": axes([("same_data", "Mêmes six spreads strictement positifs, mêmes bornes et géométrie pour les trois LP"),
                    ("individual_witnesses", "Un témoin forward et un autre backward sur la même grille 2x3"),
                    ("common_prices", "Le problème joint exige le même vecteur de prix; variances locales éventuellement distinctes"),
                    ("joint_separator", "Infaisabilité pour toutes les sélections dans les spreads, séparateur rationnel combiné"),
                    ("time_repair", "Subdivision temporelle seule, strikes et observations conservés; premier niveau faisable prouvé"),
                    ("exact_arithmetic", "Vérification exacte des témoins et du séparateur; aucune infaisabilité déduite d’un échec numérique")]),
        "C3": axes([("three_strikes", "Trois strikes éventuellement irréguliers; kappa=2/(h_minus*h_plus)"),
                    ("constant_neighbours", "Prix voisins constants pendant l’étape; gamma initial strictement positif"),
                    ("positive_variance_bounds", "Bornes de variance constantes 0<l<u"),
                    ("free_terminal_centre", "Extrémité centrale libre pour le seuil nécessaire et suffisant; contraintes terminales supplémentaires séparées"),
                    ("step_threshold", "DeltaT <= 2*(u-l)/(x^2*kappa*l*u) pour un incrément commun aux deux familles"),
                    ("midpoint_construction", "Point milieu à variance harmonique 2*l*u/(l+u), positivité et bornes vérifiées"),
                    ("all_later_levels", "Conservation des observations à tous les niveaux dyadiques ultérieurs dans la famille démontrée")])},
            "questions": ["Les hypothèses du théorème antérieur s’appliquent-elles exactement ?",
                          "Les quantificateurs et la conclusion sont-ils au moins aussi forts ?",
                          "Une spécialisation directe fournit-elle le résultat du projet ? Justifier les étapes.",
                          "Quels passages restent non lus ou nécessitent une vérification d’équation ?"],
            "automatic_semantic_certification": False}


def mapping(values, allowed, label):
    result = {}
    for value in values:
        work_id, separator, rest = value.partition("=")
        require(separator and rest and work_id in allowed and work_id not in result, "Use "+label+" WORK_ID=value once per work")
        result[work_id] = rest
    return result


def acquire(work, folder, local=None, urls=(), download_open=False, discover=False, timeout=15):
    """All failures become explicit gaps; no access-wall source is accepted."""
    workdir = folder/"documents"/work["id"]
    workdir.mkdir(parents=True, exist_ok=True)
    attempts = []
    if local:
        candidates = [("local", str(Path(local).resolve()))]
    else:
        candidates = [("url", url) for url in dict.fromkeys(urls)] if download_open else []
    # No metadata/CV URL is inferred from work['url']; KUNDU2017 has no known thesis route.
    for mode, location in candidates:
        try:
            if mode == "local":
                src = Path(location)
                require(src.is_file() and src.stat().st_size <= sources.MAX_BYTES, "Missing/oversized local source")
                raw = src.read_bytes()
                receipt = {"local_input": str(src), "raw_sha256": sha(src)}
            else:
                raw, receipt = sources.download(location, timeout)
            ext = ".pdf" if raw.lstrip().startswith(b"%PDF-") else ".html" if b"<html" in raw[:2000].lower() else ".txt"
            number = len(list(workdir.glob('attempt_*')))+1
            dest = workdir/(f"attempt_{number:02d}"+ext)
            dest.write_bytes(raw)
            extraction = sources.extract(dest)
            hint = sources.identity_hint(work["title"], extraction)
            attempt = {**receipt, "status": extraction["status"], "source_path": dest.relative_to(folder).as_posix(),
                       "source_sha256": sha(dest), "identity": hint}
            attempts.append(attempt)
            if extraction["status"] in READY:
                pages_file = workdir/"pages.json"
                write(pages_file, extraction)
                expected = work.get("source_sha256")
                return {"work_id": work["id"], "status": extraction["status"], "attempts": attempts,
                        "source_path": dest.relative_to(folder).as_posix(), "source_sha256": sha(dest),
                        "pages_path": pages_file.relative_to(folder).as_posix(), "pages_sha256": sha(pages_file),
                        "page_count": extraction["page_count"], "location_kind": extraction["location_kind"], "identity": hint,
                        "source_matches_previous_hash": sha(dest) == expected if expected else None,
                        "reading_completed": False}
        except Exception as error:
            attempts.append({"location": location, "status": "retrieval_or_extraction_failed", "error": str(error)[:500]})
    if download_open and discover and work.get("doi"):
        try:
            discovered, receipt = sources.crossref_routes(work["doi"], timeout)
            additional = [url for url in dict.fromkeys(discovered) if url not in urls][:3]
            if additional:
                result = acquire(work, folder, urls=additional, download_open=True, discover=False, timeout=timeout)
                result["attempts"] = attempts+[{"status": "crossref_fulltext_links", **receipt}]+result["attempts"]
                return result
            attempts.append({"status": "no_additional_crossref_fulltext_route", **receipt})
        except Exception as error:
            attempts.append({"status": "discovery_failed", "error": str(error)[:500]})
    return {"work_id": work["id"], "status": "source_unavailable_or_not_usable", "attempts": attempts,
            "reading_completed": False}


def empty_analysis(task):
    return {"hypotheses": "À documenter dans le texte exact.", "conclusion": "À comparer à la revendication du projet.",
            "relation": "unresolved", "derivability": "unresolved", "derivation_note": "Analyse de spécialisation directe à effectuer.",
            "evidence_ids": [], "axes": [{"axis_id": a["id"], "prior_condition": "Non évalué.",
                                           "relation": "unresolved", "evidence_ids": []} for a in task["axes"]],
            "limitations": ["Aucune lecture scientifique complète n’est attestée par l’extraction ou le classement de passages."]}


def make_tasks(registry, documents, folder, plan):
    docs = {d["work_id"]: d for d in documents}
    tasks = []
    for work in registry["works"]:
        doc = docs[work["id"]]
        extracted = read(safe_child(folder, doc["pages_path"])) if doc.get("pages_path") else None
        for cid in work["required_for_claims"]:
            claim = next(c for c in registry["claims"] if c["id"] == cid)
            blocks = sources.select_passages(extracted, cid) if extracted else []
            tasks.append({"pair_id": work["id"]+"_"+cid, "work_id": work["id"], "claim_id": cid,
                          "work_title": work["title"], "claim": claim, "axes": plan["claims"][cid],
                          "selected_passages": blocks, "selection_scope": "selected_statement",
                          "source_sha256": doc.get("source_sha256"),
                          "source_version_requires_confirmation": work["selected_version"],
                          "automatic_reading_completed": False})
    return tasks


def workbook(registry, documents, tasks):
    items = []
    for work in registry["works"]:
        doc = next(d for d in documents if d["work_id"] == work["id"])
        items.append({"work_id": work["id"], "source_sha256": doc.get("source_sha256"),
                      "version_id": work["selected_version"], "identity_confirmed": False, "full_text_extent_confirmed": False,
                      "reviewer": None, "review_date": None, "pages_reviewed": [], "public_version_event": None,
                      "decisions": [{"claim_id": t["claim_id"], "decision": "pending", "scope": "selected_statement",
                                     "analysis": empty_analysis(t)} for t in tasks if t["work_id"] == work["id"]]})
    return {"format": "dupire-reading-workbook-v1", "scientific_priority_certified": False,
            "instructions": "Copy this file outside the sealed campaign before editing. Confirm identity/version/extent; identify pages actually read; review each hypothesis and implication; set decision=accepted only after reading. Model drafts remain pending.",
            "works": items}


def overview(registry, documents):
    lines = ["# Lectures bibliographiques à compléter", "",
             "Les textes extraits et les passages classés préparent une lecture. Aucun téléchargement ne certifie une analyse scientifique.", "",
             "| Travail | Accès obtenu | Pages extraites | Identité |", "| --- | --- | --- | --- |"]
    for work in registry["works"]:
        doc = next(d for d in documents if d["work_id"] == work["id"])
        lines.append(f"| {work['id']} | {doc['status']} | {doc.get('page_count', 0)} | {doc.get('identity', {}).get('hint', 'à fournir')} |")
    lines += ["", "Copier `lectures_a_valider.json` hors du dossier scellé avant de le compléter. Les passages ont des identifiants page/ligne et des empreintes. Les numéros sont ceux des pages physiques PDF, ou des blocs de 80 lignes pour HTML/texte.", "",
              "Pour chaque revendication : examiner les hypothèses, la conclusion, les quantificateurs et la possibilité d’une spécialisation directe. Une annotation portant sur des passages sélectionnés garde cette portée. Pour `full_work`, documenter la lecture de toutes les pages et confirmer l’étendue du texte, y compris les annexes pertinentes.", "",
              "Les pages dont l’extraction échoue requièrent une vérification visuelle/OCR externe. Les équations extraites doivent être contrôlées dans le PDF. Les CV, résumés et aperçus ne remplacent pas un texte principal ou une thèse.", ""]
    return "\n".join(lines)


def prepare(priority_dir, out, attachments=(), extra_urls=(), download_open=False, discover=False, workers=2, timeout=15):
    require(1 <= workers <= 4 and 1 <= timeout <= 45, "Use workers 1..4 and timeout 1..45 seconds")
    source = Path(priority_dir).resolve()
    out = Path(out).resolve()
    require(not out.is_relative_to(source), "Reading output must be outside the input priority audit")
    checked = priority.verify(source)
    out = new_folder(out)
    registry = priority.validate(read(source/"registry.json"))
    ids = {w["id"] for w in registry["works"]}
    local = mapping(attachments, ids, "--source")
    urls = mapping(extra_urls, ids, "--url")
    require(not urls or download_open, "--url requires --telecharger")
    require(not discover or download_open, "--decouvrir requires --telecharger")
    shutil.copytree(source, out/"input_priority")
    write(out/"input_verification.json", checked)
    plan = protocol()
    write(out/"protocol.json", plan)
    routes = read(ROOT/"bibliography/source_routes.json")["routes"]
    original_sources = {a["work_id"]: safe_child(out/"input_priority", a["path"]) for a in read(source/"attachments.json")}
    documents = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {}
        for work in registry["works"]:
            wid = work["id"]
            own = local.get(wid) or original_sources.get(wid)
            candidates = ([urls[wid]] if wid in urls else [])+routes.get(wid, [])
            progress("source_started", work_id=wid)
            jobs[pool.submit(acquire, work, out, own, candidates, download_open, discover, timeout)] = wid
        for future in as_completed(jobs):
            result = future.result(); documents.append(result)
            progress("source_completed", work_id=jobs[future], status=result["status"], completed=len(documents), total=len(jobs))
    documents.sort(key=lambda d: next(i for i, w in enumerate(registry["works"]) if w["id"] == d["work_id"]))
    write(out/"documents.json", documents)
    tasks = make_tasks(registry, documents, out, plan)
    write(out/"tasks.json", tasks)
    write(out/"lectures_a_valider.json", workbook(registry, documents, tasks))
    (out/"lectures.md").write_text(overview(registry, documents), encoding="utf-8")
    write(out/"campaign.json", {"format": "dupire-reading-campaign-v1", "download_requested": download_open,
                               "discovery_requested": discover, "workers": workers, "network_used": download_open,
                               "scientific_priority_certified": False, "readings_automatically_completed": 0})
    seal(out)
    checked = verify(out)
    return {**checked, "network_used": download_open, "verification_network_used": False}


def verify(folder, reextract=False):
    folder = Path(folder).resolve()
    count = check_manifest(folder)
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and
              p.name not in {'manifest.json', 'events.jsonl', 'status.json'}}
    require(actual == set(read(folder/'manifest.json')['sha256']), "Reading campaign inventory changed")
    data = read(folder/"campaign.json")
    require(data["format"] == "dupire-reading-campaign-v1" and data["scientific_priority_certified"] is False and
            data["readings_automatically_completed"] == 0, "Unsupported automated reading/priority claim")
    require(priority.verify(folder/"input_priority") == read(folder/"input_verification.json"), "Input audit receipt changed")
    registry = priority.validate(read(folder/"input_priority/registry.json"))
    docs = read(folder/"documents.json")
    require([d["work_id"] for d in docs] == [w["id"] for w in registry["works"]], "Reading corpus changed")
    for doc in docs:
        require(doc["reading_completed"] is False, "Acquisition cannot complete a reading")
        if not doc.get("source_path"):
            require(doc["status"] == "source_unavailable_or_not_usable", "Undocumented missing source")
            continue
        require(sha(safe_child(folder, doc["source_path"])) == doc["source_sha256"], "Source bytes changed")
        page_file = safe_child(folder, doc["pages_path"])
        require(sha(page_file) == doc["pages_sha256"], "Extracted text changed")
        extracted = read(page_file)
        require(extracted["source_sha256"] == doc["source_sha256"] and extracted["page_count"] == len(extracted["pages"]),
                "Extracted pages not bound to source")
        require([v["page"] for v in extracted["pages"]] == list(range(1, extracted["page_count"]+1)), "Missing/duplicate page identity")
        for page in extracted["pages"]:
            require(page["sha256"] == digest({"page": page["page"], "lines": page["lines"]}), "Page/line evidence changed")
        if reextract:
            fresh = sources.extract(safe_child(folder, doc["source_path"]))
            require(fresh["pages"] == extracted["pages"] and fresh["source_sha256"] == extracted["source_sha256"],
                    "Re-extraction differs; check source, extraction version and text recovery")
    require(read(folder/"protocol.json") == protocol(), "Reading protocol differs from the declared project hypotheses")
    tasks = make_tasks(registry, docs, folder, read(folder/"protocol.json"))
    require(tasks == read(folder/"tasks.json"), "Reading tasks differ from the complete extracted-page index")
    require(workbook(registry, docs, tasks) == read(folder/"lectures_a_valider.json"), "Sealed workbook was edited; use an external copy")
    require((folder/"lectures.md").read_text(encoding="utf-8") == overview(registry, docs), "Reading overview changed")
    return {"status": "reading_campaign_verified", "file_hashes": count, "works": len(docs), "comparison_tasks": len(tasks),
            "sources_extracted": sum(bool(d.get("pages_path")) for d in docs),
            "sources_missing": [d["work_id"] for d in docs if not d.get("pages_path")],
            "scientific_priority_certified": False, "readings_automatically_completed": 0,
            "text_extraction_replayed": reextract, "source_and_text_hashes_verified": True,
            "semantic_annotations_auto_verified": False, "network_used": False, "solver_called": False}


def analyse_campaign(campaign, out, model, endpoint="http://127.0.0.1:11434", pairs=(), max_pairs=37, timeout=600, context=16384,
                     resume=None, predict=8000, thinking='off', retries=1, axes_per_call=7):
    from .reading_recovery import run
    return run(campaign,out,model,model_analyse,endpoint,pairs,max_pairs,timeout,context,
               resume,predict,thinking,retries,axes_per_call)


def accepted_reviews(campaign, edited):
    registry = priority.validate(read(campaign/"input_priority/registry.json"))
    docs = {d["work_id"]: d for d in read(campaign/"documents.json")}
    tasks = {(t["work_id"], t["claim_id"]): t for t in read(campaign/"tasks.json")}
    require(edited.get("format") == "dupire-reading-workbook-v1" and edited.get("scientific_priority_certified") is False,
            "Unknown/unsupported reading workbook")
    items = edited["works"]
    require(len(items) == len(docs) and {w["work_id"] for w in items} == set(docs), "Workbook changed/duplicated corpus works")
    reviews, events = [], []
    for item in items:
        wid = item["work_id"]
        doc = docs[wid]
        expected_claims = {c for w, c in tasks if w == wid}
        require(len(item["decisions"]) == len(expected_claims) and {d["claim_id"] for d in item["decisions"]} == expected_claims,
                "Workbook changed/duplicated claim pairs")
        for decision in item["decisions"]:
            require(decision["decision"] in {"pending", "accepted", "rejected"}, "Unknown reader decision")
            if decision["decision"] != "accepted":
                continue
            require(doc.get("pages_path") and doc["status"] in READY, "Cannot accept an unavailable/preview source")
            require(item["source_sha256"] == doc["source_sha256"], "Review refers to different source bytes")
            require(item["identity_confirmed"] is True and isinstance(item["reviewer"], str) and item["reviewer"].strip() and
                    item["review_date"] and item["version_id"], "Accepted reading needs reader, date, source identity and exact version")
            date.fromisoformat(item["review_date"])
            extracted = read(safe_child(campaign, doc["pages_path"]))
            pages = item["pages_reviewed"]
            require(isinstance(pages, list) and pages and all(type(n) is int for n in pages) and
                    len(pages) == len(set(pages)) and set(pages) <= set(range(1, extracted["page_count"]+1)),
                    "List the actual pages read, without duplicates")
            scope = decision["scope"]
            require(scope in {"selected_statement", "full_work"}, "Accepted scope must be explicit")
            if scope == "full_work":
                require(item["full_text_extent_confirmed"] is True and set(pages) == set(range(1, extracted["page_count"]+1)),
                        "Full-work scope requires confirmed extent and declared coverage of every page")
                require(not extracted["extraction_errors"], "Recover failed text pages before exporting full-work analysis")
            blocks = {b["id"]: b for b in sources.passages(extracted)}
            task = tasks[wid, decision["claim_id"]]
            analysis = validate_draft(decision["analysis"], task, set(blocks))
            all_evidence = set(analysis["evidence_ids"]) | {eid for axis in analysis["axes"] for eid in axis["evidence_ids"]}
            require(all_evidence and all(blocks[eid]["page"] in pages for eid in all_evidence),
                    "Accepted conclusions must cite passages on pages actually declared read")
            if scope == "full_work":
                require(all(a["relation"] != "unresolved" for a in analysis["axes"]) and
                        analysis["derivability"] != "unresolved" and analysis["relation"] != "unresolved",
                        "Full-work exclusion needs each hypothesis, conclusion and derivation resolved")
            locator = "; ".join(f"{extracted['location_kind']} {blocks[e]['page']}, lines {blocks[e]['line_start']}–{blocks[e]['line_end']} ({e})"
                                for e in sorted(all_evidence))
            reviews.append({"work_id": wid, "claim_id": decision["claim_id"], "version_id": item["version_id"],
                            "reviewer": item["reviewer"], "review_date": item["review_date"], "source_sha256": doc["source_sha256"],
                            "scope": scope, "relation": analysis["relation"], "locator": locator,
                            "hypotheses": analysis["hypotheses"], "conclusion": analysis["conclusion"],
                            "derivability": analysis["derivability"], "derivation_note": analysis["derivation_note"],
                            "hypothesis_comparisons": analysis["axes"], "evidence_ids": sorted(all_evidence),
                            "pages_declared_read": sorted(pages), "reader_extent_confirmed": item["full_text_extent_confirmed"],
                            "reading_declaration_not_semantic_proof": True, "annotation_truth_auto_verified": False})
        event = item.get("public_version_event")
        if event is not None:
            require(event["kind"] in priority.PUBLIC_KINDS and event["evidence_url"].startswith("https://") and
                    event["locator"] and event["version_id"] == item["version_id"], "Public event must identify the exact reviewed version")
            priority.interval(event["date_parts"])
            require(doc.get("source_sha256") == item.get("source_sha256") and any(r["work_id"] == wid for r in reviews),
                    "New version dates need an accepted source-bound reading")
            events.append((wid, event))
    require(reviews, "No reader-accepted comparison. Model drafts and pending templates cannot complete readings")
    return reviews, events


def export(campaign, edited_workbook, out, as_of=None, project_record=None, project_source=None):
    campaign = Path(campaign).resolve()
    verify(campaign)
    require(not Path(out).resolve().is_relative_to(campaign), "Export output must be outside the sealed reading campaign")
    edited = read(edited_workbook)
    reviews, events = accepted_reviews(campaign, edited)
    registry = read(campaign/"input_priority/registry.json")
    if as_of:
        date.fromisoformat(as_of); registry["as_of"] = as_of
    require(all(r["review_date"] <= registry["as_of"] for r in reviews), "Review after cutoff; supply --as-of YYYY-MM-DD")
    for wid, event in events:
        work = next(w for w in registry["works"] if w["id"] == wid)
        require(event["id"] not in {e["id"] for e in work["events"]}, "Use a unique version-event ID")
        work["events"].append(event)
    input_dir = campaign/"input_priority"
    attachments = {a["work_id"]: safe_child(input_dir, a["path"]) for a in read(input_dir/"attachments.json")}
    needed = {r["work_id"] for r in reviews}
    for doc in read(campaign/"documents.json"):
        if doc["work_id"] in needed:
            attachments[doc["work_id"]] = safe_child(campaign, doc["source_path"])
    if project_source:
        require(project_record, "--project-source requires --project-record")
        attachments["PROJECT"] = Path(project_source).resolve()
    old_project = input_dir/"project_record.json"
    project = project_record or (old_project if read(old_project) is not None else None)
    math_audit = input_dir/"math_audit" if (input_dir/"math_audit").exists() else None
    with tempfile.TemporaryDirectory(prefix="dupire-readings-") as temp:
        temp = Path(temp)
        write(temp/"registry.json", registry)
        for work in registry["works"]:
            if work.get("snapshot"):
                copy(safe_child(input_dir, work["snapshot"]), safe_child(temp, work["snapshot"]))
        write(temp/"reviews.json", reviews)
        result = priority.generate(out, temp/"registry.json", math_audit,
                                   [wid+"="+str(path) for wid, path in attachments.items()], temp/"reviews.json", project)
    # Keep evidence and reader decisions inside the resulting self-contained audit.
    evidence_dir = Path(out)/"reading_evidence"
    evidence_dir.mkdir()
    write(evidence_dir/"accepted_reviews.json", reviews)
    copy(edited_workbook, evidence_dir/"reader_workbook.json")
    copy(campaign/"protocol.json", evidence_dir/"protocol.json")
    write(evidence_dir/"export.json", {"format": "dupire-reading-export-v1", "parent_campaign_manifest_sha256": sha(campaign/"manifest.json"),
                                      "accepted_comparisons": len(reviews), "scientific_priority_certified": False})
    for wid in needed:
        doc = next(d for d in read(campaign/"documents.json") if d["work_id"] == wid)
        copy(safe_child(campaign, doc["pages_path"]), evidence_dir/(wid+".pages.json"))
    seal(out)
    result = priority.verify(out)
    return {**result, "accepted_comparisons_exported": len(reviews), "reader_declarations_are_not_semantic_proofs": True}


def verify_export_evidence(folder):
    """Rebind accepted page/line IDs to source bytes in a standalone export."""
    folder = Path(folder)
    evidence = folder/"reading_evidence"
    receipt = read(evidence/"export.json")
    require(receipt["format"] == "dupire-reading-export-v1" and receipt["scientific_priority_certified"] is False,
            "Unsupported exported reading claim")
    accepted = read(evidence/"accepted_reviews.json")
    require(len(accepted) == receipt["accepted_comparisons"] and accepted, "Accepted reading count changed")
    registry = priority.validate(read(folder/"registry.json"))
    registered = {(r["work_id"], r["claim_id"]): r for r in registry["reviews"]}
    attachments = {a["work_id"]: a for a in read(folder/"attachments.json")}
    plan = read(evidence/"protocol.json")
    edited = read(evidence/"reader_workbook.json")
    for review in accepted:
        wid, cid = review["work_id"], review["claim_id"]
        require(registered.get((wid, cid)) == review, "Registry differs from accepted reading")
        require(attachments[wid]["sha256"] == review["source_sha256"], "Accepted reading lost its exact source")
        extracted = read(evidence/(wid+".pages.json"))
        require(extracted["source_sha256"] == review["source_sha256"], "Page index belongs to a different source")
        for page in extracted["pages"]:
            require(page["sha256"] == digest({"page": page["page"], "lines": page["lines"]}), "Exported text evidence changed")
        blocks = {b["id"]: b for b in sources.passages(extracted)}
        require(set(review["evidence_ids"]) <= set(blocks), "Exported evidence locator does not exist")
        work = next(w for w in edited["works"] if w["work_id"] == wid)
        decision = next(d for d in work["decisions"] if d["claim_id"] == cid)
        require(decision["decision"] == "accepted" and work["identity_confirmed"] is True and
                work["source_sha256"] == review["source_sha256"] and work["reviewer"] == review["reviewer"] and
                work["version_id"] == review["version_id"] and work["review_date"] == review["review_date"] and
                decision["scope"] == review["scope"], "Reader declaration differs from exported review")
        analysis = validate_draft(decision["analysis"], {"axes": plan["claims"][cid]}, set(blocks))
        all_ids = set(analysis['evidence_ids']) | {eid for axis in analysis['axes'] for eid in axis['evidence_ids']}
        require(set(review['evidence_ids']) == all_ids, "Exported evidence differs from the accepted analysis")
        locator = '; '.join(f"{extracted['location_kind']} {blocks[e]['page']}, lines {blocks[e]['line_start']}–{blocks[e]['line_end']} ({e})"
                            for e in sorted(all_ids))
        require(review['locator'] == locator, "Exported locator differs from page/line evidence")
        require(review["hypothesis_comparisons"] == analysis["axes"] and review["hypotheses"] == analysis["hypotheses"] and
                review["conclusion"] == analysis["conclusion"] and review["relation"] == analysis["relation"] and
                review["derivability"] == analysis["derivability"] and review["derivation_note"] == analysis["derivation_note"],
                "Reader analysis differs from registry review")
        require(set(review["pages_declared_read"]) == set(work["pages_reviewed"]) and
                all(blocks[eid]["page"] in work["pages_reviewed"] for eid in review["evidence_ids"]), "Evidence on an unread page")
        if review["scope"] == "full_work":
            require(work["full_text_extent_confirmed"] is True and
                    set(work["pages_reviewed"]) == set(range(1, extracted["page_count"]+1)) and
                    all(a["relation"] != "unresolved" for a in analysis["axes"]), "Full-work scope lost its page/hypothesis coverage")
    return {"verified": True, "accepted_comparisons": len(accepted), "semantic_annotations_auto_verified": False}


def show_passages(campaign, pair_id):
    campaign = Path(campaign).resolve(); verify(campaign)
    tasks = read(campaign/"tasks.json")
    task = next((t for t in tasks if t["pair_id"] == pair_id), None)
    require(task is not None, "Unknown comparison pair")
    return {"pair_id": pair_id, "claim": task["claim"], "axes": task["axes"], "selected_passages": task["selected_passages"],
            "scope": "selected_statement", "absence_in_other_passages_not_inferred": True}


def page_range(value):
    pages = set()
    for segment in value.split(','):
        match = re.fullmatch(r'\s*(\d+)(?:-(\d+))?\s*', segment)
        require(match is not None, "Pages syntax: 1-4,8,12-15")
        lo, hi = int(match[1]), int(match[2] or match[1])
        require(1 <= lo <= hi <= 1500, "Page ranges must be increasing within 1..1500")
        pages.update(range(lo, hi+1))
    return sorted(pages)


def approve(campaign, edited_workbook, out, work_id, claim_id, reviewer, review_date, pages,
            identity_confirmed=False, extent_confirmed=False, scope='selected_statement'):
    campaign = Path(campaign).resolve(); verify(campaign)
    target = Path(out).resolve()
    require(not target.is_relative_to(campaign) and not target.exists(), "Write a new workbook outside the sealed campaign")
    require(identity_confirmed, "Explicitly confirm the source identity/version after reading with --identity-confirmed")
    edited = read(edited_workbook)
    item = next((w for w in edited['works'] if w['work_id'] == work_id), None)
    require(item is not None, "Unknown work to approve")
    decision = next((d for d in item['decisions'] if d['claim_id'] == claim_id), None)
    require(decision is not None, "Unknown claim to approve")
    item.update(reviewer=reviewer, review_date=review_date, identity_confirmed=True,
                pages_reviewed=sorted(set(item['pages_reviewed']) | set(page_range(pages))))
    item['full_text_extent_confirmed'] = item['full_text_extent_confirmed'] or extent_confirmed
    decision.update(decision='accepted', scope=scope)
    # This is an explicit reader declaration, never a model approval.
    accepted_reviews(campaign, edited)
    write(target, edited)
    return {'status':'reader_declaration_recorded', 'work_id':work_id, 'claim_id':claim_id, 'scope':scope,
            'workbook':str(target), 'semantic_annotations_auto_verified':False, 'scientific_priority_certified':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Récupérer, lire, comparer et intégrer les antécédents de C1–C3")
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("preparer")
    prep.add_argument("--priority-dir", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    prep.add_argument("--source", action="append", default=[], metavar="WORK_ID=PATH")
    prep.add_argument("--url", action="append", default=[], metavar="WORK_ID=HTTPS_URL")
    prep.add_argument("--telecharger", action="store_true")
    prep.add_argument("--decouvrir", action="store_true", help="Interroger les liens de texte intégral Crossref après les routes connues")
    prep.add_argument("--workers", type=int, default=2)
    prep.add_argument("--timeout", type=int, default=15)
    model = commands.add_parser("analyser")
    model.add_argument("--campaign", type=Path, required=True)
    model.add_argument("--out", type=Path, required=True)
    model.add_argument("--model", required=True, help="Nom d’un modèle déjà disponible sur Ollama local")
    model.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    model.add_argument("--pair", action="append", default=[])
    model.add_argument("--max-pairs", type=int, default=37)
    model.add_argument("--timeout", type=int, default=600)
    model.add_argument("--num-ctx", type=int, default=16384)
    model.add_argument('--resume', type=Path, help='Reprendre les échecs et conserver les brouillons existants d’une même campagne')
    model.add_argument('--num-predict', type=int, default=8000)
    model.add_argument('--thinking', choices=['off','on','auto'], default='off')
    model.add_argument('--retries', type=int, default=1)
    model.add_argument('--axes-per-call', type=int, default=7)
    diag=commands.add_parser('diagnostiquer')
    diag.add_argument('--workbook', type=Path, required=True)
    diag.add_argument('--analysis-dir', type=Path)
    exp = commands.add_parser("exporter")
    exp.add_argument("--campaign", type=Path, required=True)
    exp.add_argument("--workbook", type=Path, required=True)
    exp.add_argument("--out", type=Path, required=True)
    exp.add_argument("--as-of")
    exp.add_argument("--project-record", type=Path)
    exp.add_argument("--project-source", type=Path)
    approve_cmd = commands.add_parser('valider', help='Enregistrer une déclaration explicite du lecteur après contrôle du brouillon')
    approve_cmd.add_argument('--campaign', type=Path, required=True)
    approve_cmd.add_argument('--workbook', type=Path, required=True)
    approve_cmd.add_argument('--out', type=Path, required=True)
    approve_cmd.add_argument('--work-id', required=True)
    approve_cmd.add_argument('--claim', required=True, choices=['C1','C2','C3'])
    approve_cmd.add_argument('--reviewer', required=True)
    approve_cmd.add_argument('--date', required=True)
    approve_cmd.add_argument('--pages', required=True)
    approve_cmd.add_argument('--scope', choices=['selected_statement','full_work'], default='selected_statement')
    approve_cmd.add_argument('--identity-confirmed', action='store_true')
    approve_cmd.add_argument('--extent-confirmed', action='store_true')
    check = commands.add_parser("verifier")
    check.add_argument("--campaign", type=Path, required=True)
    check.add_argument("--reextraire", action="store_true", help="Refaire l’extraction et comparer chaque page; pypdf requis pour les PDF")
    show = commands.add_parser("passages")
    show.add_argument("--campaign", type=Path, required=True)
    show.add_argument("--pair", required=True)
    args = parser.parse_args(argv)
    if args.command == "preparer":
        result = prepare(args.priority_dir, args.out, args.source, args.url, args.telecharger, args.decouvrir, args.workers, args.timeout)
    elif args.command == "analyser":
        result = analyse_campaign(args.campaign,args.out,args.model,args.ollama_url,args.pair,args.max_pairs,args.timeout,args.num_ctx,
                                  args.resume,args.num_predict,args.thinking,args.retries,args.axes_per_call)
    elif args.command == 'diagnostiquer':
        from .reading_recovery import diagnose
        result=diagnose(args.workbook,args.analysis_dir)
    elif args.command == "exporter":
        result = export(args.campaign, args.workbook, args.out, args.as_of, args.project_record, args.project_source)
    elif args.command == 'valider':
        result = approve(args.campaign, args.workbook, args.out, args.work_id, args.claim, args.reviewer,
                         args.date, args.pages, args.identity_confirmed, args.extent_confirmed, args.scope)
    elif args.command == "verifier":
        result = verify(args.campaign, args.reextraire)
    else:
        result = show_passages(args.campaign, args.pair)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 2 if result.get('status') == 'model_analysis_failed' or result.get('drafts_failed',0)>0 else 0
