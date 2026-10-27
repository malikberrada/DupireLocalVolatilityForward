"""An evidence-backed comparison of selected statements, not a novelty oracle.

Semantic annotations are explicit, editable evidence. Validation checks their
coverage and provenance; it does not prove equivalence of published theorems.
"""
from pathlib import Path
import re
from .io import read, write, copy, sha, require, digest

RELATIONS = {"same_component", "additional_project_hypothesis", "different_framework",
             "outside_selected_statement", "unknown"}
LABELS = {"same_component": "Composante commune", "additional_project_hypothesis": "Hypothèse supplémentaire du projet",
          "different_framework": "Cadre différent", "outside_selected_statement": "Hors de l’énoncé comparé",
          "unknown": "Non évalué"}


def validate(registry):
    require(registry.get("format") in {"dupire-theorem-crosswalk-v1", "dupire-theorem-crosswalk-v2"}, "Unknown comparison registry")
    axes = registry["axes"]
    require(len({a["id"] for a in axes}) == len(axes) and len(axes) >= 10, "Duplicate or missing axes")
    ids = {a["id"] for a in axes}
    results = registry["results"]
    require(len({r["id"] for r in results}) == len(results), "Duplicate theorem/result identifier")
    for result in results:
        require(result["url"].startswith("https://") and result["statement_locator"] and result["version"],
                "Each result needs a primary URL, a version and a locator")
        allowed = {"full_text_sections_reviewed", "abstract_only"}
        if registry["format"] == "dupire-theorem-crosswalk-v2":
            allowed.add("abstract_and_public_appendix_reviewed")
        require(result["access"] in allowed, "Unknown access level")
        if result["paper_id"] == "KKT2024" and result["access"] == "full_text_sections_reviewed":
            review = result.get("full_text_review", {})
            require(review.get("reviewer") and review.get("review_date") and
                    re.fullmatch(r"[0-9a-f]{64}", review.get("source_sha256", "")),
                    "A completed KKT2024 review needs a named reviewer, date and source hash")
        require(set(result["comparisons"]) == ids, "Incomplete hypothesis coverage: " + result["id"])
        for axis, item in result["comparisons"].items():
            require(item["relation"] in RELATIONS and bool(item["prior_condition"]), "Malformed comparison")
            require(item["locator"] and item["basis"] in {"source_reading", "scope_inference", "not_reviewed"},
                    "Missing evidence locator or inference label")
            if item["relation"] == "unknown":
                require(item["basis"] == "not_reviewed", "Unknown condition cannot be marked reviewed")
            if result["access"] == "abstract_only":
                require(item["basis"] != "source_reading" or "résumé" in item["locator"].lower(),
                        "Abstract-only source cannot support a full-text assertion")
            if result["access"] == "abstract_and_public_appendix_reviewed" and item["basis"] == "source_reading":
                require(any(s in item["locator"].lower() for s in ("résumé", "annexe")),
                        "Partial access supports only the reviewed abstract or appendix")
    require(registry["scientific_priority_certified"] is False, "This software does not certify scientific priority")
    return registry


def matrix(registry):
    validate(registry)
    lines = ["# Comparaison hypothèse par hypothèse", "",
             "Les relations portent sur les énoncés nommés ci-dessous. Une propriété hors de ces énoncés peut exister ailleurs dans le même article.", "",
             "Les lectures et les inférences de portée sont des annotations explicites ; le programme vérifie leur couverture et leur cohérence, pas leur vérité sémantique.", "",
             "Le théorème 2 du projet est une condition suffisante. Aucune équivalence de théorèmes ni priorité scientifique n’est certifiée.", ""]
    for result in registry["results"]:
        lines += ["## " + result["id"], "", result["title"], "",
                  "Énoncé : **" + result["statement_locator"] + "**. Version : " + result["version"] + ".", "",
                  "Source primaire : " + result["url"], "", "Accès : `" + result["access"] + "`. " + result["scope_note"], "",
                  "| Hypothèse / propriété du projet | Condition antérieure | Relation et preuve consultée |",
                  "| --- | --- | --- |"]
        for axis in registry["axes"]:
            item = result["comparisons"][axis["id"]]
            evidence = "inférence de portée" if item["basis"] == "scope_inference" else (
                "lecture de la source" if item["basis"] == "source_reading" else "non évalué")
            parts = [axis["label"] + " : " + axis["project_condition"], item["prior_condition"],
                     LABELS[item["relation"]] + "; " + item["locator"] + "; " + evidence]
            lines.append("| " + " | ".join(x.replace("|", "∣").replace("\n", " ") for x in parts) + " |")
        if result.get("unresolved"):
            lines += ["", "À vérifier : " + result["unresolved"]]
        lines += [""]
    gap_text = ("Le texte principal KKT2024 et la thèse de Kundu (2017) restent à examiner intégralement. L’annexe publique KKT2024 est comparée."
                if registry["format"] == "dupire-theorem-crosswalk-v2" else
                "Le texte intégral KKT2024 reste un blocage à la comparaison exhaustive. Joindre ce PDF ne remplace pas la lecture et l’annotation de ses hypothèses.")
    lines += ["## Décision de portée", "",
              "L’utilisation de Bernstein, d’un LP, de contraintes de forme ou de bornes locales est antérieure. L’objet candidat reste le certificat rationnel avec seuil quantifié préservant les observations pour les deux stencils.", "",
              gap_text, "",
              "L’exemple discriminant illustre le système précis du projet ; il ne démontre pas la supériorité d’une implémentation sur les modèles publiés.", ""]
    return "\n".join(lines)


def comparison_report(registry, registry_sha256):
    unknown = [{"result": r["id"], "axis": a, "locator": v["locator"]}
               for r in registry["results"] for a, v in r["comparisons"].items() if v["relation"] == "unknown"]
    kkt = [r for r in registry["results"] if r["paper_id"] == "KKT2024"]
    report = {"selected_results": len(registry["results"]), "axes": len(registry["axes"]),
              "comparison_cells": len(registry["results"])*len(registry["axes"]), "unknown_cells": unknown,
              "registry_sha256": registry_sha256, "semantic_annotations_auto_verified": False,
              "full_text_KKT2024_review_complete": all(r["access"] == "full_text_sections_reviewed" for r in kkt),
              "scientific_priority_certified": False}
    if registry["format"] == "dupire-theorem-crosswalk-v2":
        report["selected_result_ids"] = [r["id"] for r in registry["results"]]
        report["full_text_KKT2024_review_complete"] = bool(kkt) and report["full_text_KKT2024_review_complete"]
        report["KKT2024_public_appendix_reviewed"] = any(r["access"] == "abstract_and_public_appendix_reviewed" for r in kkt)
        report["critical_source_gaps"] = registry.get("critical_source_gaps", [])
    return report


def generate(registry_path, out, attachments=()):
    out = Path(out)
    registry = validate(read(registry_path))
    copy(registry_path, out / "theoremes.json")
    registered = []
    known = {r["paper_id"] for r in registry["results"]}
    known.update(s["paper_id"] for s in registry.get("background_sources", []))
    for value in attachments:
        paper_id, separator, name = value.partition("=")
        require(separator and paper_id in known and re.fullmatch(r"[A-Z0-9]+", paper_id),
                "Use --source PAPER_ID=path with a known paper ID")
        source = Path(name)
        dest = out / "sources" / (paper_id + source.suffix.lower())
        require(not dest.exists(), "Duplicate attachment for " + paper_id)
        copy(source, dest)
        registered.append({"paper_id": paper_id, "path": dest.relative_to(out).as_posix(),
                           "sha256": sha(dest), "reading_completed_by_attaching": False})
    (out / "matrice_hypotheses.md").write_text(matrix(registry), encoding="utf-8")
    write(out / "sources_locales.json", registered)
    for result in registry["results"]:
        if result["paper_id"] == "KKT2024" and result["access"] == "full_text_sections_reviewed":
            expected = result["full_text_review"]["source_sha256"]
            require(any(s["paper_id"] == "KKT2024" and s["sha256"] == expected for s in registered),
                    "Attach the exact source used for the completed KKT2024 review with --source")
    report = comparison_report(registry, sha(out/"theoremes.json"))
    write(out / "comparison.json", report)
    # A concrete checklist for completing the gated source review.
    write(out / "a_completer_KKT2024.json", {"paper_id": "KKT2024", "full_text_sha256": None,
          "reviewer": None, "review_date": None, "instructions": "Read the full statement and proof. Fill exact pages/equations; update a copy of theoremes.json, then pass --comparisons. Attachment alone changes no scientific claim.",
          "hypotheses_to_check": [a["id"] for a in registry["axes"]],
          "check_equivalent_refinement_bound_and_preserved_quotes": True})
    return report


def verify_comparison(folder):
    folder = Path(folder)
    registry = validate(read(folder / "theoremes.json"))
    require((folder / "matrice_hypotheses.md").read_text(encoding="utf-8") == matrix(registry), "Matrix differs from annotations")
    report = read(folder / "comparison.json")
    require(report == comparison_report(registry, sha(folder/"theoremes.json")),
            "Literature summary differs from the declared source access and annotations")
    require(report["registry_sha256"] == sha(folder / "theoremes.json"), "Registry hash changed")
    unknown = [{"result": r["id"], "axis": a, "locator": v["locator"]}
               for r in registry["results"] for a, v in r["comparisons"].items() if v["relation"] == "unknown"]
    require(report["unknown_cells"] == unknown and report["scientific_priority_certified"] is False,
            "Literature uncertainty was suppressed")
    for source in read(folder / "sources_locales.json"):
        from .io import safe_child
        require(sha(safe_child(folder, source["path"])) == source["sha256"], "Attached source hash changed")
        require(not source["reading_completed_by_attaching"], "Attaching a source cannot certify its interpretation")
    sources = read(folder / "sources_locales.json")
    for result in registry["results"]:
        if result["paper_id"] == "KKT2024" and result["access"] == "full_text_sections_reviewed":
            require(any(s["paper_id"] == "KKT2024" and s["sha256"] == result["full_text_review"]["source_sha256"]
                        for s in sources), "Reviewed KKT2024 source is missing")
    return {"verified": True, "structural_comparisons": report["comparison_cells"],
            "semantic_annotations_auto_verified": False, "scientific_priority_certified": False}
