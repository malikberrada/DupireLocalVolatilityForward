"""Evidence annotations are human-reviewed; unknown never means absent."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path

STATUSES = {"documented", "penalized", "different_problem", "not_assessed"}
ACCESS = {"full_text_sections", "abstract_only", "metadata_only"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(registry):
    if registry.get("format") != "dupire-literature-registry-v1":
        raise ValueError("Unknown literature registry format")
    cutoff=date.fromisoformat(registry["cutoff"])
    features=set(registry["features"])
    ids=set()
    for paper in registry["papers"]:
        if paper["id"] in ids:raise ValueError("Duplicate paper id")
        ids.add(paper["id"])
        if date.fromisoformat(paper["available_date"])>cutoff:
            raise ValueError("Paper version is later than the review cutoff")
        if paper["access"] not in ACCESS:raise ValueError("Unknown access level")
        if not paper["url"].startswith("https://"):raise ValueError("Need a primary HTTPS source")
        if not paper["reviewed_locators"]:raise ValueError("Missing reviewed sections or abstract locator")
        for feature,evidence in paper["evidence"].items():
            if feature not in features:raise ValueError("Unknown feature")
            if evidence["status"] not in STATUSES:raise ValueError("Unknown evidence status; absence is not inferred")
            if evidence["status"]!="not_assessed" and not evidence.get("locator"):
                raise ValueError("An assessed property needs a precise locator")
            if paper["access"]!="full_text_sections" and evidence["status"]!="not_assessed":
                if evidence["locator"].casefold() not in {"abstract","résumé","metadata"}:
                    raise ValueError("Abstract-only access cannot support a full-text theorem claim")
    for claim in registry["claims"]:
        if not set(claim["sources"])<=ids:raise ValueError("Unknown claim source")
        if claim["status"] not in {"established_prior_art","candidate_contribution","engineering_contribution"}:
            raise ValueError("Unsupported claim status; this tool does not certify priority")
    return registry


def load(path):
    return validate(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def assess(registry):
    validate(registry)
    return {"cutoff":registry["cutoff"],"paper_count":len(registry["papers"]),
            "review_type":"targeted_mechanism_based_review_not_exhaustive",
            "novelty_status":"not_determined_by_this_tool",
            "unknown_is_not_absence":True,"claims":registry["claims"],
            "access_gaps":[p["id"] for p in registry["papers"] if p["access"]!="full_text_sections"],
            "remaining_checks":[
                "Read the full 2023/2024 Kundu-Kumar-Tomar surface paper before excluding equivalent results.",
                "Compare hypotheses and conclusions of SANOS 3.3 and Buehler-Ryskin 3.3, including boundary and transport operators.",
                "Check the exact observation-preserving refinement statement against additional numerical-analysis and constrained-approximation literature.",
                "Do not infer scientific novelty, speed superiority, or completeness from a finite bibliography or successful examples."]}


def bibliography(registry):
    entries=[]
    for p in registry["papers"]:
        fields={"title":p["title"],"author":" and ".join(p["authors"]),"year":str(p["year"]),
                "url":p["url"],"note":p["version"]}
        if p.get("doi"):fields["doi"]=p["doi"]
        body=",\n".join("  "+k+" = {"+v.replace("{","").replace("}","")+"}" for k,v in fields.items())
        entries.append("@misc{"+p["id"]+",\n"+body+"\n}\n")
    return "\n".join(entries)


def matrix_markdown(registry):
    labels={"documented":"Établi", "penalized":"Pénalisé", "different_problem":"Autre objet", "not_assessed":"?"}
    feature_ids=list(registry["features"])
    lines=["# Matrice des résultats documentés", "",
           "`?` signifie non évalué, jamais une preuve d'absence. Chaque cellule porte sur la version et les sections indiquées.","",
           "| Référence | "+" | ".join(registry["features"].values())+" |",
           "| --- | "+" | ".join("---" for _ in feature_ids)+" |"]
    for p in registry["papers"]:
        cells=[labels[p["evidence"].get(f,{"status":"not_assessed"})["status"]] for f in feature_ids]
        lines.append("| ["+p["id"]+"]("+p["url"]+") | "+" | ".join(cells)+" |")
    lines.extend(["","## Localisateurs et différences de problème",""])
    for p in registry["papers"]:
        lines.extend(["- **"+p["id"]+"** — "+p["version"]+" ; accès : `"+p["access"]+"` ; "+" ; ".join(p["reviewed_locators"])+".",
                      "  "+p["overlap"]+" "+p["comparison_caveat"]])
    return "\n".join(lines)+"\n"
