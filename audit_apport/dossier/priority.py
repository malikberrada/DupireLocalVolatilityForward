"""Dated, claim-specific bibliographic evidence; never a first-ever oracle.

Only --refresh-metadata uses the network. Review annotations are declarations,
not semantic theorem proofs. A hash binds bytes, not a public disclosure date.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import shutil
import urllib.request

from .io import read, write, copy, sha, require, seal, check_manifest, safe_child

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FIELDS = ("published", "published-online", "published-print", "posted")
PUBLIC_KINDS = set(PUBLIC_FIELDS) | {"arxiv_submitted", "ssrn_posted", "ssrn_revised"}
RELATIONS = {"component_prior", "different_statement", "equivalent_or_stronger", "unresolved"}
DERIVATIONS = {"unresolved", "component_only", "not_a_direct_corollary", "direct_specialization"}
CLAIMS = {"C1", "C2", "C3"}
SHA = re.compile(r"[0-9a-f]{64}\Z")


def interval(parts):
    """Inclusive bounds of a date, preserving year/month precision."""
    require(isinstance(parts, list) and 1 <= len(parts) <= 3 and
            all(type(v) is int for v in parts), "Date needs one to three integer date-parts")
    year, month, day = parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1
    start = date(year, month, day)
    end = (date(year, 12, 31) if len(parts) == 1 else
           date(year, month, calendar.monthrange(year, month)[1]) if len(parts) == 2 else start)
    return start, end


def date_record(parts):
    lo, hi = interval(parts)
    return {"date_parts": parts, "precision": ("year", "month", "day")[len(parts)-1],
            "display": "-".join(f"{v:04d}" if i == 0 else f"{v:02d}" for i, v in enumerate(parts)),
            "earliest_possible": lo.isoformat(), "latest_possible": hi.isoformat()}


def temporal_order(left, right):
    a, b = interval(left), interval(right)
    if a[1] < b[0]:
        return "definitely_before"
    if a[0] > b[1]:
        return "definitely_after"
    return "overlapping_or_same_date"


def crossref_events(work, snapshot):
    require(snapshot["work_id"] == work["id"] and snapshot["provider"] == "Crossref",
            "Snapshot belongs to another work/provider")
    m = snapshot["projection"]
    require(m["DOI"].lower() == work["doi"].lower(), "DOI mismatch in bibliographic snapshot")
    events = []
    for field in PUBLIC_FIELDS:
        if field not in m:
            continue
        parts = m[field]["date-parts"][0]
        interval(parts)
        events.append({"id": "crossref_"+field, "kind": field, "date_parts": parts,
                       "version_id": work.get("crossref_version_fields", {}).get(field),
                       "evidence_url": snapshot["url"], "locator": "message."+field+".date-parts[0]"})
    # created, deposited, indexed, copyright and license-start are NOT public events.
    return events


def events_for(work, folder, as_of):
    events = list(work.get("events", []))
    if work.get("snapshot"):
        events += crossref_events(work, read(safe_child(folder, work["snapshot"])))
    require(len({e["id"] for e in events}) == len(events), "Duplicate chronology event")
    usable, excluded = [], []
    for event in events:
        require(event["kind"] in PUBLIC_KINDS and event["evidence_url"].startswith("https://") and event["locator"],
                "A public event needs its primary record and field")
        interval(event["date_parts"])
        target = usable if interval(event["date_parts"])[1] <= date.fromisoformat(as_of) else excluded
        target.append(event)
    return usable, excluded


def earliest(events):
    if not events:
        return None
    # Earliest of imprecisely dated events is itself an interval, not an invented day.
    lo = min(interval(e["date_parts"])[0] for e in events)
    hi = min(interval(e["date_parts"])[1] for e in events)
    return {"earliest_possible": lo.isoformat(), "latest_possible": hi.isoformat(),
            "contributing_event_ids": [e["id"] for e in events if interval(e["date_parts"])[0] <= hi]}


def validate(registry):
    require(registry.get("format") == "dupire-priority-registry-v1", "Unknown priority registry")
    require(registry.get("scientific_priority_certified") is False, "Unsupported universal priority flag")
    date.fromisoformat(registry["as_of"])
    require({c["id"] for c in registry["claims"]} == CLAIMS and len(registry["claims"]) == 3,
            "Exactly three separate project claims are required")
    works = registry["works"]
    ids = {w["id"] for w in works}
    require(len(ids) == len(works) and len(ids) > 0, "Duplicate or missing works")
    for w in works:
        require(re.fullmatch(r"[A-Z0-9]+", w["id"]) and w["url"].startswith("https://") and
                w["title"] and w["selected_version"] and w["access"], "Missing work identity/version/access")
        require(set(w["required_for_claims"]) <= CLAIMS, "Unknown claim in corpus")
        source_hash = w.get("source_sha256")
        require(source_hash is None or SHA.fullmatch(source_hash), "Invalid source hash")
    for claim in registry["claims"]:
        require(any(claim["id"] in w["required_for_claims"] for w in works), "Empty declared claim corpus")
    pairs = set()
    for review in registry["reviews"]:
        key = review["work_id"], review["claim_id"]
        require(key not in pairs and key[0] in ids and key[1] in CLAIMS, "Duplicate/unknown review pair")
        work = next(w for w in works if w['id'] == key[0])
        require(key[1] in work['required_for_claims'], "Review is outside the declared claim corpus")
        pairs.add(key)
        require(review["relation"] in RELATIONS and review["scope"] in {"selected_statement", "full_work", "not_reviewed"}
                and review["derivability"] in DERIVATIONS, "Unknown review scope/relation/derivation")
        require(review["locator"] and review["hypotheses"] and review["conclusion"] and review["derivation_note"],
                "Review needs hypotheses, conclusion, exact locator and derivation analysis")
        if review["scope"] != "not_reviewed":
            require(review["reviewer"] and review["version_id"], "Review needs an identified reviewer/version")
            require(date.fromisoformat(review["review_date"]) <= date.fromisoformat(registry["as_of"]),
                    "Review occurs after audit cutoff")
        if review.get("source_sha256") is not None:
            require(SHA.fullmatch(review["source_sha256"]), "Malformed reviewed-source hash")
        if review["scope"] == "full_work":
            require(review.get("source_sha256") and review["derivability"] != "unresolved" and
                    review["relation"] != "unresolved", "Full-work exclusion needs source hash and derivation analysis")
    return registry


def access_hint(path):
    with Path(path).open('rb') as source:
        head = source.read(150000).lower()
    if head.startswith(b"%pdf-"):
        return "pdf_extent_not_auto_verified"
    if any(s in head for s in (b"this is a preview of subscription content", b"access through your institution",
                               b"checking your browser", b"verify you are human")):
        return "access_wall_or_preview"
    return "extent_not_auto_verified"


def attachment_status(work_id, expected_hash, attachments, folder):
    for item in attachments:
        if item["work_id"] == work_id and expected_hash and item["sha256"] == expected_hash:
            path = safe_child(folder, item["path"])
            require(sha(path) == expected_hash, "Reviewed attachment changed")
            return access_hint(path) != "access_wall_or_preview"
    return False


def validate_project(project, attachments, folder, as_of):
    if project is None:
        return {"status": "public_disclosure_not_supplied", "documented_claims": [],
                "public_record_authentication_auto_verified": False}
    require(project.get("format") == "dupire-project-public-record-v1", "Unknown public release record")
    require(project.get("identifier") and project.get("version") and
            project.get("public_url", "").startswith("https://"), "Public release needs an identifier, URL and version")
    require(isinstance(project.get("source_sha256"), str) and SHA.fullmatch(project["source_sha256"]),
            "Public version needs its exact document hash")
    require(interval(project["date_parts"])[1] <= date.fromisoformat(as_of), "Public date is after audit cutoff")
    metadata = project["metadata"]
    require(metadata["provider"] and metadata["record_url"].startswith("https://") and metadata["locator"] and
            metadata["date_kind"] in PUBLIC_KINDS, "Private timestamps/received dates are not public release records")
    require(set(project["claim_locators"]) <= CLAIMS and all(project["claim_locators"].values()),
            "Claim must be located in the dated public version")
    bound = attachment_status("PROJECT", project["source_sha256"], attachments, folder)
    return {"status": "public_release_documented_by_declaration" if bound else "public_version_attachment_missing",
            "documented_claims": sorted(project["claim_locators"]) if bound else [],
            "date": date_record(project["date_parts"]), "identifier": project["identifier"], "version": project["version"],
            "public_record_authentication_auto_verified": False}


def assessment(folder):
    folder = Path(folder)
    registry = validate(read(folder/"registry.json"))
    attachments = read(folder/"attachments.json")
    for a in attachments:
        require(a["reading_completed_by_attaching"] is False and sha(safe_child(folder, a["path"])) == a["sha256"],
                "Attachment changed or was improperly promoted to a reading")
    project = read(folder/"project_record.json")
    release = validate_project(project, attachments, folder, registry["as_of"])
    rows, chronology = [], []
    reviews = {(r["work_id"], r["claim_id"]): r for r in registry["reviews"]}
    for work in registry["works"]:
        events, excluded = events_for(work, folder, registry["as_of"])
        chronology.append({"work_id": work["id"], "title": work["title"], "url": work["url"],
                           "earliest_documented_work_availability": earliest(events),
                           "events": [{**e, "date": date_record(e["date_parts"])} for e in events],
                           "selected_version": work["selected_version"],
                           "selected_version_availability": earliest([e for e in events if e.get("version_id") == work["selected_version"]]),
                           "date_notes": [work[k] for k in ("date_note", "version_date_note", "metadata_conflict_note") if k in work],
                           "events_not_usable_at_cutoff": excluded,
                           "earliest_work_date_does_not_backdate_reviewed_passages": True})
        for claim in sorted(work["required_for_claims"]):
            r = reviews.get((work["id"], claim))
            blockers = []
            if r is None:
                rows.append({"work_id": work["id"], "claim_id": claim, "relation": "unresolved",
                             "blockers": ["review_missing"], "full_work_exclusion_documented": False,
                             "dated_equivalence": "not_assessed"})
                continue
            if r["scope"] != "full_work":
                blockers.append("full_work_review_not_documented")
            if r["relation"] == "unresolved":
                blockers.append("relation_unresolved")
            if r["derivability"] == "unresolved":
                blockers.append("derivability_unresolved")
            source_bound = attachment_status(work["id"], r.get("source_sha256"), attachments, folder)
            if not source_bound:
                blockers.append("reviewed_source_bytes_not_bound")
            version_events = [e for e in events if e.get("version_id") == r["version_id"]]
            # The work's first posting cannot date passages of an unpinned later PDF.
            if not version_events:
                blockers.append("reviewed_version_public_date_unresolved")
            order = "project_date_missing"
            if project is not None and claim in release["documented_claims"] and version_events:
                dated = earliest(version_events)
                p_lo, p_hi = interval(project["date_parts"])
                order = ("definitely_before" if date.fromisoformat(dated["latest_possible"]) < p_lo else
                         "definitely_after" if date.fromisoformat(dated["earliest_possible"]) > p_hi else
                         "overlapping_or_same_date")
            equivalent = r["relation"] == "equivalent_or_stronger" or r["derivability"] == "direct_specialization"
            dated_equivalence = ("prior_equivalent_or_specialization" if equivalent and source_bound and order == "definitely_before" else
                                 "equivalent_in_later_reviewed_version" if equivalent and source_bound and order == "definitely_after" else
                                 "equivalence_identified_chronology_pending" if equivalent else "none_asserted_in_reviewed_scope")
            if equivalent and dated_equivalence != "equivalent_in_later_reviewed_version":
                blockers.append("equivalence_or_direct_specialization_identified")
            rows.append({"work_id": work["id"], "claim_id": claim, "relation": r["relation"], "scope": r["scope"],
                         "locator": r["locator"], "source_hash_bound": source_bound,
                         "version_temporal_order": order, "dated_equivalence": dated_equivalence,
                         "full_work_exclusion_documented": not blockers, "blockers": blockers})
    outcomes = []
    for claim in registry["claims"]:
        cells = [c for c in rows if c["claim_id"] == claim["id"]]
        blockers = [{"work_id": c["work_id"], "reasons": c["blockers"]} for c in cells if c["blockers"]]
        public = claim["id"] in release["documented_claims"]
        if any(c["dated_equivalence"] == "prior_equivalent_or_specialization" for c in cells):
            status = "prior_equivalent_or_direct_specialization_identified"
        elif any(c["dated_equivalence"] == "equivalence_identified_chronology_pending" for c in cells):
            status = "equivalence_or_specialization_requires_chronology"
        elif blockers:
            status = "comparison_incomplete"
        elif not public:
            status = "comparison_complete_public_project_record_missing"
        else:
            status = "priority_argument_documented_in_declared_corpus"
        outcomes.append({"claim_id": claim["id"], "label": claim["label"], "status": status,
                         "public_project_version_documented": public, "unresolved_work_count": len(blockers),
                         "blockers": blockers})
    return {"format": "dupire-priority-assessment-v1", "as_of": registry["as_of"],
            "works": len(registry["works"]), "claims": outcomes, "comparison_cells": len(rows),
            "chronology": chronology, "comparison": rows, "project_public_record": release,
            "new_evidence": registry["new_evidence"],
            "math_evidence": read(folder/"math_receipt.json"),
            "scientific_priority_certified": False, "semantic_annotations_auto_verified": False,
            "provider_authentication": False, "exhaustive_literature_search": False}


def render(data, registry):
    lines = ["# Dossier de priorité bibliographique — 0.4.0", "",
             f"Arrêté au {data['as_of']} : {data['works']} travaux, {len(data['claims'])} revendications distinctes et {data['comparison_cells']} comparaisons.", "",
             "Le programme établit la traçabilité de l’argument bibliographique déclaré. Il ne certifie ni une première mondiale ni l’interprétation des théorèmes.", "",
             "Audit mathématique associé : `"+data["math_evidence"]["status"]+"`. La preuve mathématique et la priorité bibliographique sont évaluées séparément.", "",
             "## Nouveaux éléments", ""]
    lines += ["- "+item for item in data["new_evidence"]]
    lines += ["", "## Revendications", "", "| ID | Objet exact | État calculé | Travaux à compléter |",
              "| --- | --- | --- | --- |"]
    for claim in data["claims"]:
        lines.append(f"| {claim['claim_id']} | {claim['label']} | `{claim['status']}` | {claim['unresolved_work_count']} |")
    lines += ["", "Version publique du projet : `"+data["project_public_record"]["status"]+"`.", "",
              "Un fichier local, une empreinte SHA-256, un horodatage privé ou la date de création d’une notice DOI ne prouvent pas une divulgation publique. Le dossier fourni ne contient pas d’identifiant public daté du résultat du projet.", ""
              ] if data["project_public_record"]["status"] == "public_disclosure_not_supplied" else ["", "Version publique du projet : `"+data["project_public_record"]["status"]+"`. Les métadonnées sont déclarées et liées aux octets ; leur authenticité n’est pas prouvée hors ligne.", ""]
    lines += ["## Chronologie documentée", "", "Les dates de l’œuvre et celles de la version effectivement lue sont distinctes. Une date au mois reste au mois ; les plages servent uniquement à comparer l’ordre temporel.", "",
              "| Travail | Événements publics documentés | Version lue et datation |", "| --- | --- | --- |"]
    for work in data["chronology"]:
        dates = "; ".join(e["kind"]+" : "+e["date"]["display"] for e in work["events"])
        v = work["selected_version_availability"]
        version_date = (v["earliest_possible"]+" à "+v["latest_possible"]) if v else "non déterminée"
        lines.append(f"| [{work['work_id']}]({work['url']}) | {dates or 'non déterminé'} | {work['selected_version']} : {version_date} |")
    date_notes = [w['work_id']+" : "+note for w in data['chronology'] for note in w['date_notes']]
    if date_notes:
        lines += ["", "Précisions de datation :", ""]+["- "+note for note in date_notes]
    by_pair = {(r["work_id"], r["claim_id"]): r for r in registry["reviews"]}
    for claim in registry["claims"]:
        lines += ["", "## "+claim["id"]+" — "+claim["label"], "", claim["statement"], "",
                  "| Antécédent / passage | Hypothèses et conclusion comparées | Relation / dérivabilité / portée |",
                  "| --- | --- | --- |"]
        for row in data["comparison"]:
            if row["claim_id"] != claim["id"]:
                continue
            r = by_pair.get((row["work_id"], claim["id"]))
            if r is None:
                lines.append("| "+row["work_id"]+" | Lecture manquante | non évalué |")
                continue
            cells = [row["work_id"]+" : "+r["locator"], r["hypotheses"]+" → "+r["conclusion"],
                     r["relation"]+" ; "+r["derivability"]+" ; "+r["scope"]+". "+r["derivation_note"]]
            lines.append("| "+" | ".join(c.replace("|", "∣").replace("\n", " ") for c in cells)+" |")
        missing = next(c["blockers"] for c in data["claims"] if c["claim_id"] == claim["id"])
        if missing:
            lines += ["", "À compléter : "+" ; ".join(b["work_id"]+" ("+", ".join(b["reasons"])+")" for b in missing)+"."]
    lines += ["", "## Règles de conclusion", "",
              "Une différence d’énoncé ne suffit pas : la spécialisation directe doit également être examinée. Les méthodes classiques (LP, Bernstein, interpolation sans arbitrage, point milieu) ne sont pas revendiquées comme nouvelles.", "",
              "Le statut `priority_argument_documented_in_declared_corpus` exige, pour chaque travail requis, une relecture de l’ensemble du texte déclarée, ses octets exacts, une version publiquement datée et une analyse de dérivabilité résolue, ainsi qu’une version publique du projet localisant la revendication. Il reste limité au corpus déclaré et aux annotations fournies.", "",
              "Les résumés, aperçus éditeur et recherches sans résultat ne ferment aucune lacune de lecture. Joindre un document ne transforme pas sa portée en lecture intégrale. Le vérificateur recalcule les dates, les lacunes et les conclusions, sans réseau ni solveur.", ""]
    return "\n".join(lines)


def fetch_crossref(work):
    url = "https://api.crossref.org/works/"+work["doi"]
    request = urllib.request.Request(url, headers={"User-Agent": "DupireBibliographicAudit/0.4"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2_000_001)
    require(len(raw) <= 2_000_000, "Crossref response unexpectedly large")
    import hashlib
    m = json.loads(raw)["message"]
    require(m["DOI"].lower() == work["doi"].lower(), "Provider returned another DOI")
    fields = ("DOI", "title", "author", "container-title", "volume", "issue", "page", "article-number",
              *PUBLIC_FIELDS, "created", "deposited", "indexed", "URL", "link")
    return {"format": "dupire-bibliographic-snapshot-v1", "work_id": work["id"], "provider": "Crossref",
            "url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
            "projection": {k: m[k] for k in fields if k in m}, "projection_is_not_a_signed_timestamp": True}


def verify(folder):
    folder = Path(folder).resolve()
    count = check_manifest(folder)
    manifest = read(folder/"manifest.json")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and
              p.name not in {"manifest.json", "events.jsonl", "status.json"}}
    require(actual == set(manifest["sha256"]), "Priority dossier inventory changed")
    math = read(folder/"math_receipt.json")
    if math["status"] == "verified_exact_audit":
        from .app import verify_folder
        require(verify_folder(folder/"math_audit") == math, "Mathematical evidence receipt differs")
    else:
        require(math == {"status": "not_supplied"}, "Unknown mathematical evidence receipt")
    expected = assessment(folder)
    require(read(folder/"priority.json") == expected, "Priority conclusions differ from their evidence")
    require((folder/"rapport_priorite.md").read_text(encoding="utf-8") == render(expected, read(folder/"registry.json")),
            "Priority report differs from annotations")
    supplemental = {}
    if (folder/"reading_evidence").exists():
        from .readings import verify_export_evidence
        supplemental["reading_evidence"] = verify_export_evidence(folder)
    return {"status": "bibliographic_dossier_verified", "file_hashes": count, "works": expected["works"],
            "comparison_cells": expected["comparison_cells"],
            "claim_statuses": {c["claim_id"]: c["status"] for c in expected["claims"]},
            "project_public_record": expected["project_public_record"]["status"],
            "mathematical_evidence": math["status"], "semantic_annotations_auto_verified": False,
            "scientific_priority_certified": False, "solver_called": False, "network_used": False, **supplemental}


def generate(out, registry_path=ROOT/"bibliography/registry.json", audit_dir=None, attachments=(),
             reviews=None, project_record=None, refresh=False):
    out, registry_path = Path(out).resolve(), Path(registry_path).resolve()
    registry = validate(read(registry_path))
    require(not out.exists() or not any(out.iterdir()), "Use a new output directory to preserve prior evidence")
    if audit_dir:
        require(not out.is_relative_to(Path(audit_dir).resolve()), "Output must be outside the mathematical audit")
    out.mkdir(parents=True, exist_ok=True)
    for work in registry["works"]:
        if work.get("snapshot"):
            copy(safe_child(registry_path.parent, work["snapshot"]), safe_child(out, work["snapshot"]))
    if reviews is not None:
        edits = read(reviews)
        require(isinstance(edits, list), "--reviews must contain a list of explicit review annotations")
        pairs = [(r["work_id"], r["claim_id"]) for r in edits]
        require(len(set(pairs)) == len(pairs), "Duplicate supplied review")
        for r in edits:
            require(r.get("source_sha256") and r.get("reviewer") and r.get("review_date"),
                    "New reviews need exact source hash, reviewer and date")
        registry["reviews"] = [r for r in registry["reviews"] if (r["work_id"], r["claim_id"]) not in pairs]+edits
    validate(registry)
    metadata_refresh = []
    if refresh:
        for work in registry["works"]:
            if not work.get("snapshot"):
                continue
            try:
                snapshot = fetch_crossref(work)
                crossref_events(work, snapshot)
                write(safe_child(out, work["snapshot"]), snapshot)
                metadata_refresh.append({"work_id": work["id"], "status": "refreshed", "readings_promoted": False})
            except (OSError, ValueError, KeyError) as error:
                metadata_refresh.append({"work_id": work["id"], "status": "refresh_failed_frozen_snapshot_retained",
                                         "error": str(error), "readings_promoted": False})
    registered, known = [], {w["id"] for w in registry["works"]} | {"PROJECT"}
    for value in attachments:
        work_id, separator, path = value.partition("=")
        require(separator and work_id in known and work_id not in {a["work_id"] for a in registered},
                "Use --source KNOWN_WORK_ID=path once per work")
        src = Path(path)
        suffix = src.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,8}", src.suffix.lower()) else ".bin"
        dest = out/"sources"/(work_id+suffix)
        copy(src, dest)
        registered.append({"work_id": work_id, "path": dest.relative_to(out).as_posix(), "sha256": sha(dest),
                           "content_hint": access_hint(dest), "reading_completed_by_attaching": False})
    for r in registry["reviews"]:
        if reviews is not None and (r["work_id"], r["claim_id"]) in pairs:
            require(attachment_status(r["work_id"], r["source_sha256"], registered, out),
                    "Attach the exact reviewed source; a preview/access wall cannot complete a review")
    write(out/"registry.json", registry)
    write(out/"attachments.json", registered)
    write(out/"project_record.json", read(project_record) if project_record else None)
    write(out/"refresh_log.json", {"network_requested": refresh, "results": metadata_refresh,
                                   "manual_arxiv_ssrn_events_not_automatically_refreshed": True})
    if audit_dir:
        from .app import verify_folder
        receipt = verify_folder(audit_dir)
        shutil.copytree(audit_dir, out/"math_audit")
        require(verify_folder(out/"math_audit") == receipt, "Mathematical audit copy changed")
    else:
        receipt = {"status": "not_supplied"}
    write(out/"math_receipt.json", receipt)
    data = assessment(out)
    write(out/"priority.json", data)
    (out/"rapport_priorite.md").write_text(render(data, registry), encoding="utf-8")
    copy(ROOT/"bibliography/search_log.json", out/"search_log.json")
    copy(ROOT/"bibliography/project_record.template.json", out/"project_record.template.json")
    copy(ROOT/"bibliography/review.template.json", out/"review.template.json")
    seal(out)
    checked = verify(out)
    return {**checked, "network_used": bool(metadata_refresh), "verification_network_used": False,
            "metadata_refresh_results": metadata_refresh}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a dated, claim-specific bibliographic priority dossier")
    parser.add_argument("--registry", type=Path, default=ROOT/"bibliography/registry.json")
    parser.add_argument("--audit-dir", type=Path, help="Completed 0.3/0.4 math audit; copied and reverified offline")
    parser.add_argument("--source", action="append", default=[], metavar="WORK_ID=PATH")
    parser.add_argument("--reviews", type=Path, help="Explicit readings bound to attached source bytes")
    parser.add_argument("--project-record", type=Path, help="Dated public version and claim locators; never a private timestamp")
    parser.add_argument("--refresh-metadata", action="store_true", help="Request Crossref; never promotes abstract access or reviews")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", type=Path, help="Recompute the saved dossier without network or solver")
    args = parser.parse_args(argv)
    if args.verify:
        require(not any((args.audit_dir, args.source, args.reviews, args.project_record, args.refresh_metadata, args.out)),
                "--verify cannot be mixed with generation, refresh or attachment options")
        result = verify(args.verify)
    else:
        out = args.out or Path("runs")/("priorite_bibliographique_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
        result = generate(out, args.registry, args.audit_dir, args.source, args.reviews, args.project_record, args.refresh_metadata)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0
