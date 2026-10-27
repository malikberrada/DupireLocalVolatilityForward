"""CLI: evidence map, exact audits, controlled ablations, reproducible report."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from fractions import Fraction as Q
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

from .catalogue import load,assess,bibliography,matrix_markdown,sha256
from .metrics import (direct_check,observations_hash,read_external_surface,sample_polynomial,
                      exact_stencil_errors,stringify)

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(stringify(value),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def levels(text):
    values=[int(v) for v in text.split(",")]
    if not values or values!=sorted(set(values)) or any(not 0<=v<=8 for v in values):
        raise argparse.ArgumentTypeError("Use increasing distinct levels in [0,8], e.g. 0,1,2")
    return values


def check_criterion(folder,out,logical_grid=None,max_nodes=20000):
    from dupire_joint.finite_criterion import Problem,verify,read_source
    folder=Path(folder)
    problem=Problem.load(read(folder/"criterion.problem.json"))
    if problem.scheme!="joint":
        raise ValueError("Supply a criterion run made with --scheme joint; this comparison requires the same surface for both stencils")
    certificate=read(folder/"criterion.certificate.json")
    checked=verify(problem,certificate,max_nodes)
    if not checked["verified"] or certificate["kind"]!="primal":
        raise ValueError("The supplied criterion run has no valid exact primal witness")
    direct=direct_check(problem,certificate["prices"])
    if not direct["passed"]:raise ValueError("Independent direct audit rejected the criterion witness")
    if logical_grid:
        _,_,obs,source=read_source(logical_grid,logical=True)
        if tuple(tuple(map(Q,row)) for row in obs)!=problem.observations:
            raise ValueError("Original exact observations differ")
        if problem.source and source["sha256"]!=problem.source.get("sha256"):
            raise ValueError("Original exact-grid file hash differs")
        shutil.copy2(logical_grid,out/"inputs/original_exact_grid.json")
    for suffix in ("problem","certificate"):
        shutil.copy2(folder/("criterion."+suffix+".json"),out/"inputs"/("criterion."+suffix+".json"))
    return problem,{"verified":True,"scheme":problem.scheme,"shape":list(problem.shape),
                    "problem_sha256":problem.digest(),"observations_sha256":observations_hash(problem),
                    "observation_count":len(problem.observations),"direct_audit":direct,
                    "original_source_rechecked":bool(logical_grid),
                    "scope":"declared finite grid and fixed nominal normalization; no constructive refinement certificate inferred"}


def refinement_comparison(payload,checked,selected,max_nodes,out,progress):
    from dupire_joint.constructive import mesh_plan,base_axes
    s={k:Q(v) for k,v in payload["spec"].items()}
    constants={k:Q(v) for k,v in checked["checks"]["constants"].items()}
    records=[[Q(v) for v in row] for row in payload["observations"]]
    t,x=base_axes(records)
    plan=mesh_plan(constants,s,t,x,max(64,max(selected)))
    # Continue after the first guaranteed level to compare later error bounds.
    from dupire_joint.constructive import geometry
    from dupire_joint.refinement import quadratic_parameters,quadratic_trial
    params=quadratic_parameters(constants,s,geometry(t,x));runs=[]
    for level in selected:
        with progress.phase("Exact polynomial stencil comparison",level=level):
            trial=quadratic_trial(params,constants,s,level)
            problem,prices,shape=sample_polynomial(payload,level,level,max_nodes)
            row={"level":level,"shape":shape,"bound":trial,"materialized":problem is not None}
            if problem is not None:
                direct=direct_check(problem,prices)
                errors=exact_stencil_errors(payload,problem,prices)
                if Q(errors["gamma_error"])>Q(trial["Egamma"]):raise ArithmeticError("Gamma bound failed")
                if trial["Evariance"] is not None:
                    if any(Q(v)>Q(trial["Evariance"]) for v in errors["variance_error"].values()):
                        raise ArithmeticError("Variance error bound failed")
                if trial["passed"] and not direct["passed"]:
                    raise ArithmeticError("A guaranteed mesh failed the independent check")
                row.update(direct=direct,actual_errors=errors)
                write(out/f"polynomial_level_{level:02d}.witness.json",
                      {"problem":problem.payload(),"prices":list(map(str,prices)),"audit":direct})
            runs.append(row)
    hashes={r["direct"]["observations_sha256"] for r in runs if r.get("direct")}
    if len(hashes)>1:raise ArithmeticError("Observations changed during refinement")
    return {"polynomial_certificate_verified_exact":True,"same_witness_for_both_schemes":True,
            "guaranteed_level":plan["guaranteed_level"],"all_further_levels_by_theorem":plan["guaranteed_level"] is not None,
            "quadratic_criterion":plan["quadratic_criterion"],"observations_unchanged":len(hashes)<=1,"runs":runs,
            "no_general_nesting_of_discrete_feasible_sets_assumed":True}


def make_report(registry,result):
    lines=["# Positionnement de l’apport constructif", "",
           "Revue ciblée arrêtée au "+registry["cutoff"]+". Les annotations de littérature proviennent d’une lecture humaine des sources listées. Les inconnues restent inconnues.","",
           "## Ce qui est établi et ce qui reste candidat", "",
           "| Élément | Positionnement | Sources |", "| --- | --- | --- |"]
    labels={"established_prior_art":"Antériorité identifiée", "candidate_contribution":"Apport candidat à comparer",
            "engineering_contribution":"Contribution d’implémentation"}
    for claim in registry["claims"]:
        lines.append("| "+claim["statement"]+" | "+labels[claim["status"]]+" | "+", ".join(claim["sources"])+" |")
    lines.extend(["", "L’apport candidat est la spécialisation certifiable : un témoin polynomial, une marge de variance et une géométrie commune donnent un seuil explicite pour les deux stencils, sans modifier les observations. Les ingrédients Bernstein, LP, Dupire et Taylor sont classiques.",
                  "", "Ce dossier ne certifie pas une priorité scientifique. Le texte intégral KKT2024 reste notamment à comparer. Les hypothèses de transport, de bords et de normalisation diffèrent entre méthodes.","",
                  "## Vérification des données réelles",""])
    real=result.get("criterion_run")
    if real:
        lines.append(f"Témoin exact revérifié : {real['observation_count']} intervalles, grille {real['shape']}, schéma `{real['scheme']}`. Le contrôle direct recalcule les contraintes depuis les coordonnées rationnelles.")
        lines.append("Liaison au fichier source exact contrôlée : `"+str(real["original_source_rechecked"])+"`. La normalisation est fixée ; ce témoin sur grille ne devient pas un certificat polynomial de raffinement.")
    else:lines.append("Aucun dossier de données réelles fourni ; aucun résultat de marché n’est inventé.")
    constructive=result["constructive"]
    lines.extend(["","## Expérience contrôlée de raffinement","",
                  "Origine du témoin : `"+result["constructive_source"]+"`. Il est contrôlé indépendamment des données réelles ci-dessus.",
                  "Niveau garanti par la borne suffisante : `"+str(constructive["guaranteed_level"])+"`. Ce seuil n’est pas présenté comme nécessaire.","",
                  "| Niveau | Grille | Borne variance (approx.) | Erreur maximale réelle (approx.) | Prix et bornes exacts |",
                  "| --- | --- | --- | --- | --- |"])
    for row in constructive["runs"]:
        bound=row["bound"]["Evariance"]
        b=f"{float(Q(bound)):.7g}" if bound is not None else "non définie"
        actual=row.get("actual_errors",{}).get("variance_error",{})
        e=f"{float(max(map(Q,actual.values()))):.7g}" if actual else "non matérialisée"
        passed=str(row.get("direct",{}).get("passed","non testé"))
        lines.append(f"| {row['level']} | {row['shape']} | {b} | {e} | {passed} |")
    experiments=result.get("experiments")
    lines.extend(["","## Comparateurs exécutés et adaptations",""])
    if experiments:
        ab=experiments["bernstein_ablation"];crw=experiments["crw_adapted"]
        kkt=experiments.get("kkt2016_slices")
        if kkt:
            lines.append("- KKTG2016 par échéance : `"+kkt["status"]+"`. Objectif des moindres carrés (24) et contraintes (18)–(23), en unités normalisées, au degré fixé. La sélection AIC et le modèle de surface KKT2024 ne sont pas reproduits. Les calendriers, les bid/ask durs et les bornes locales ne sont pas imposés par cette formulation par tranche.")
        lines.append("- Ablation Bernstein : `"+ab["status"]+"`. Même famille, mêmes quotes, même plancher de gamma ; les deux contraintes locales sont retirées et le calendrier est conservé. Ce n’est pas une reproduction KKT2016/KKT2024.")
        lines.append("- Objectif CRW : `"+crw["status"]+"`. La formule à quatre fonctions affines est reprise ; les contraintes sont celles de notre fenêtre F0. Les bid/ask restent souples. L’optimalité du coût n’est pas certifiée exactement.")
        lines.append("- LP nodal : adaptation du système commun du projet ; aucune reproduction du transport complet de BR2016. Les preuves exactes et les observations identiques sont enregistrées pour chaque niveau testé.")
        if ab.get("verification",{}).get("full_constructive_condition_verified"):
            lines.append("Sur ce jeu contrôlé, l’ablation satisfait aussi la condition locale complète : elle n’illustre donc pas à elle seule un bénéfice empirique de ces contraintes.")
        if experiments["nodal"] and experiments["nodal"][0]["conclusion"]=="feasible_exact":
            lines.append("Le LP nodal est déjà faisable au premier niveau testé. La borne constructive est suffisante et peut être conservatrice ; aucun gain de faisabilité n’est revendiqué sur cet exemple.")
        if crw.get("status")=="numeric_witness_only":
            audit=crw.get("numeric_lp_audit",{})
            lines.append("Le témoin CRW adapté n’a pas été reconstruit avec une forme exactement admissible. Audit numérique du LP arrondi : `"+str(audit.get("passed"))+"`, résidu maximal `"+str(audit.get("max_violation"))+"`. Cette limite de reconstruction n’est pas une preuve d’échec de la méthode publiée.")
        lines.extend(["","| Niveau LP nodal | Conclusion exacte |", "| --- | --- |"])
        for row in experiments["nodal"]:lines.append(f"| {row['level']} | `{row['conclusion']}` |")
    else:lines.append("Résolutions supplémentaires désactivées ; seules les preuves fournies ont été vérifiées.")
    lines.extend(["","Andreasen–Huge, SSVI, SANOS, Fengler, Tikhonov et les réseaux/GP publiés ne sont pas exécutés par défaut. Des surfaces issues de leurs implémentations réelles peuvent être importées et auditées sur les mêmes axes. Aucune supériorité de vitesse, de précision ou d’existence n’est déduite de leur absence.",
                  "","## Hypothèses à conserver","",
                  "Fenêtre intérieure finie, grille commune irrégulière, quotes retenues inchangées, courbes nominales fixées, gamma strictement positif et marge de variance pour le théorème constructif. Pas d’extension globale des queues ni de robustesse aux courbes incertaines.",
                  "","Voir `matrice_litterature.md` pour les versions et localisateurs, `references.bib` pour la bibliographie, et `inputs/registry.json` pour les annotations structurées."])
    return "\n".join(lines)+"\n"


def write_manifest(out):
    files={str(p.relative_to(out)):sha256(p) for p in sorted(out.rglob('*')) if p.is_file()
           and p.name not in ("manifest.json","events.jsonl","status.json") and "source_cache" not in p.parts}
    write(out/"manifest.json",{"format":"dupire-positioning-manifest-v1","sha256":files})


def verify_report(folder,max_nodes=20000):
    from dupire_joint.constructive import verify_payload
    from dupire_joint.finite_criterion import Problem,verify
    folder=Path(folder).resolve();manifest=read(folder/"manifest.json")
    for name,digest in manifest["sha256"].items():
        p=(folder/name).resolve()
        if not p.is_relative_to(folder):raise ValueError("Manifest path escapes report directory")
        if sha256(p)!=digest:raise ValueError("Report artifact hash mismatch: "+name)
    registry=load(folder/"inputs/registry.json");assess(registry)
    payload=read(folder/"inputs/constructive.certificate.json")
    checked=verify_payload(payload)
    if not checked["passed"]:raise ValueError("Constructive proof rejected")
    report=read(folder/"positionnement.json")
    by_level={r["level"]:r for r in report["constructive"]["runs"]}
    if report["constructive"]["guaranteed_level"]!=checked["mesh"]["guaranteed_level"]:
        raise ValueError("Reported guaranteed level differs")
    from dupire_joint.constructive import base_axes,geometry
    from dupire_joint.refinement import quadratic_parameters,quadratic_trial
    spec={k:Q(v) for k,v in payload["spec"].items()}
    constants={k:Q(v) for k,v in checked["checks"]["constants"].items()}
    ts,xs=base_axes([[Q(v) for v in row] for row in payload["observations"]])
    params=quadratic_parameters(constants,spec,geometry(ts,xs))
    for level,row in by_level.items():
        if quadratic_trial(params,constants,spec,level)!=row["bound"]:
            raise ValueError("Reported refinement bound differs")
    count=0
    for witness in folder.glob("polynomial_level_*.witness.json"):
        d=read(witness);p=Problem.load(d["problem"])
        level=int(witness.stem.split("_")[-1].split(".")[0])
        expected,prices,_=sample_polynomial(payload,level,level,max_nodes)
        if expected is None or expected.digest()!=p.digest() or list(map(Q,d["prices"]))!=prices:
            raise ValueError("Refined witness is not the declared polynomial on the preserved grid")
        # Some levels below the sufficient threshold may be infeasible: require
        # faithful audit, not feasibility at every experimental level.
        if direct_check(p,d["prices"])!=d["audit"]:raise ValueError("Polynomial mesh audit differs")
        if exact_stencil_errors(payload,p,prices)!=by_level[level]["actual_errors"]:
            raise ValueError("Actual stencil errors differ")
        count+=1
    for problem_file in list((folder/"inputs").glob("criterion.problem.json"))+list(folder.glob("nodal_level_*/joint.problem.json")):
        cert=problem_file.with_name(problem_file.name.replace(".problem.json",".certificate.json"))
        if cert.exists():
            p=Problem.load(read(problem_file))
            if problem_file.name=="joint.problem.json":
                from .metrics import polynomial_problem
                level=int(problem_file.parent.name.rsplit("_",1)[-1])
                if polynomial_problem(payload,level,level).digest()!=p.digest():
                    raise ValueError("Nodal comparison changed observations, bounds or grid")
            check=verify(p,read(cert),max_nodes)
            if not check["verified"]:raise ValueError("Finite-grid proof rejected")
            count+=1
    ablation=folder/"bernstein_shape_ablation.witness.json"
    if ablation.exists():
        from .experiments import weak_polynomial_check
        d=read(ablation)
        if d["spec"]!=payload["spec"] or d["observations"]!=payload["observations"]:
            raise ValueError("Ablation changed input assumptions")
        check=weak_polynomial_check([[Q(v) for v in row] for row in d["coefficients"]],
                  {k:Q(v) for k,v in d["spec"].items()},[[Q(v) for v in row] for row in d["observations"]])
        if not check["shape_quotes_gamma_floor_verified"] or check!=d["verification"]:
            raise ValueError("Ablation certificate rejected")
        count+=1
    numeric_baselines=0
    adapted=folder/"crw_adapted.witness.json"
    if adapted.exists():
        from .metrics import polynomial_problem
        p=(Problem.load(read(folder/"inputs/criterion.problem.json")) if (folder/"inputs/criterion.problem.json").exists()
           else polynomial_problem(payload,0,0))
        d=read(adapted);check=direct_check(p,d["prices"])
        if p.digest()!=d["problem_sha256"] or check!=d["verification"]:
            raise ValueError("Adapted baseline audit differs")
        numeric_baselines+=not check["shape_passed"]
    slices=folder/"kkt2016_slices.witness.json"
    if slices.exists():
        from .kkt2016 import check_coefficients
        from .metrics import polynomial_problem
        from dupire_joint.bernstein import basis
        p=(Problem.load(read(folder/"inputs/criterion.problem.json")) if (folder/"inputs/criterion.problem.json").exists()
           else polynomial_problem(payload,0,0))
        d=read(slices);degree=d["degree"];prices=[]
        for beta in d["coefficients"]:
            beta=list(map(Q,beta))
            if not check_coefficients(beta,degree,p.strikes[0],p.strikes[-1])["verified"]:
                raise ValueError("KKT2016 slice coefficient inequalities fail")
            prices.extend(sum((b*w for b,w in zip(beta,basis(degree,(x-p.strikes[0])/(p.strikes[-1]-p.strikes[0])))),Q(0)) for x in p.strikes)
        if list(map(Q,d["prices"]))!=prices or p.digest()!=d["problem_sha256"] or direct_check(p,prices)!=d["audit"]:
            raise ValueError("KKT2016 slice audit differs")
        count+=1
    return {"verified":True,"math_artifacts_rechecked":count+1,"file_hashes_rechecked":len(manifest["sha256"]),
            "solver_called":False,"network_used":False,"literature_annotations_reassessed":False,
            "numeric_baselines_without_exact_shape_certificate":numeric_baselines,
            "scientific_novelty_certified":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Position the constructive contribution using primary evidence and exact controlled comparisons")
    parser.add_argument("--criterion-run",type=Path,help="Existing 0.1.6 run with criterion.problem/certificate.json")
    parser.add_argument("--logical-grid",type=Path,help="Also bind the market proof to its original F0.exact_grid.json")
    parser.add_argument("--constructive-certificate",type=Path,help="Your polynomial certificate; default: included controlled example")
    parser.add_argument("--registry",type=Path,default=ROOT/"literature/registry.json")
    parser.add_argument("--levels",type=levels,default=[0,1,2])
    parser.add_argument("--threads",type=int,default=4)
    parser.add_argument("--time-limit",type=float,default=60)
    parser.add_argument("--max-nodes",type=int,default=20000)
    parser.add_argument("--skip-experiments",action="store_true")
    parser.add_argument("--fetch-sources",action="store_true",help="Optional source bytes and hashes; does not upgrade evidence annotations")
    parser.add_argument("--crossref-query",action="append",default=[],help="Optional discovery; candidates remain unreviewed")
    parser.add_argument("--external-surface",action="append",default=[],help="NAME=CSV with rational time,x,price at every market grid node")
    parser.add_argument("--verify",type=Path,help="Verify an existing report without network or solver")
    parser.add_argument("--out",type=Path)
    args=parser.parse_args(argv)
    if args.verify:
        checked=verify_report(args.verify,args.max_nodes)
        print(json.dumps(checked,indent=2),flush=True);return 0
    if not 1<=args.max_nodes<=100000:parser.error("max-nodes must be in [1,100000]")
    if args.logical_grid and not args.criterion_run:parser.error("logical-grid requires criterion-run")
    if args.external_surface and not args.criterion_run:parser.error("External surfaces need a declared criterion grid")
    from dupire_joint.progress import Progress
    from dupire_joint.constructive import verify_payload
    from dupire_joint.solver import SolverOptions,SolverSession
    from .experiments import bernstein_ablation,crw_comparison,nodal_comparison
    out=(args.out or Path("runs")/("positionnement_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))).resolve()
    if out.exists() and any(out.iterdir()):parser.error("Use a new empty --out directory; previous evidence is preserved")
    (out/"inputs").mkdir(parents=True,exist_ok=True)
    progress=Progress(out)
    registry=load(args.registry);shutil.copy2(args.registry,out/"inputs/registry.json")
    assessment=assess(registry)
    certificate=args.constructive_certificate or ROOT/"fixtures/constructive.certificate.json"
    with progress.phase("Verify polynomial certificate exactly"):
        payload=read(certificate);checked=verify_payload(payload)
        if not checked["passed"]:raise ValueError("The polynomial certificate is invalid")
        shutil.copy2(certificate,out/"inputs/constructive.certificate.json")
    result={"format":"dupire-literature-positioning-v1","bibliographic_assessment":assessment,
            "constructive_source":"user_supplied_certificate" if args.constructive_certificate else "included_controlled_synthetic_example",
            "constructive_certificate_sha256":sha256(certificate),"criterion_run":None,
            "environment":{"python":sys.version.split()[0],"dupire_joint":importlib.metadata.version("dupire-joint")},
            "published_implementation_dominance_claimed":False,"external_surfaces":[]}
    target=None
    if args.criterion_run:
        with progress.phase("Reverify market witness and original declared geometry"):
            target,result["criterion_run"]=check_criterion(args.criterion_run,out,args.logical_grid,args.max_nodes)
    result["constructive"]=refinement_comparison(payload,checked,args.levels,args.max_nodes,out,progress)
    if not args.skip_experiments:
        from .metrics import polynomial_problem
        with SolverSession(SolverOptions(args.threads,args.time_limit,1e-10,"ipm"),progress) as session:
            ablation=bernstein_ablation(payload,session,out)
            nodal=nodal_comparison(payload,args.levels,session,out,args.max_nodes)
            # If real data are supplied, CRW is evaluated on those data. It must
            # not be compared numerically to the synthetic Bernstein example.
            baseline_target=target or polynomial_problem(payload,0,0)
            crw=crw_comparison(baseline_target,session,out)
            crw["data_scope"]="market_input" if target else "controlled_polynomial_observations"
        from .kkt2016 import fit_slices
        with progress.phase("KKTG2016 / fixed-degree constrained least-squares slices"):
            degree=len(payload["coefficients"][0])-1
            kkt,kkt_values=fit_slices(baseline_target,degree,args.time_limit)
            kkt["data_scope"]="market_input" if target else "controlled_polynomial_observations"
            if kkt_values is not None:
                write(out/"kkt2016_slices.witness.json",{"degree":degree,"coefficients":kkt["coefficients"],
                      "prices":list(map(str,kkt_values)),"audit":kkt["direct_audit"],
                      "problem_sha256":baseline_target.digest()})
        result["experiments"]={"bernstein_ablation":ablation,"nodal":nodal,"crw_adapted":crw,"kkt2016_slices":kkt}
    for arg in args.external_surface:
        if "=" not in arg:raise ValueError("Use --external-surface NAME=FILE.csv")
        name,path=arg.split("=",1)
        values=read_external_surface(path,target)
        result["external_surfaces"].append({"name":name,"file_sha256":sha256(path),
                  "audit":direct_check(target,values),"implementation_provenance_verified":False,
                  "training_runtime_measured":False})
        write(out/("external_"+str(len(result["external_surfaces"]))+".witness.json"),
              {"prices":list(map(str,values)),"problem_sha256":target.digest(),"source_sha256":sha256(path)})
    if args.fetch_sources:
        from .retrieval import fetch_sources
        result["source_downloads"]=fetch_sources(registry,out/"source_cache",progress)
    if args.crossref_query:
        from .retrieval import crossref_candidates
        found=[]
        for query in args.crossref_query:
            try:found.append(crossref_candidates(query,registry["cutoff"]))
            except Exception as exc:found.append({"query":query,"status":"retrieval_failed","reason":str(exc)})
        write(out/"unreviewed_candidates.json",found)
    write(out/"positionnement.json",result)
    write(out/"claims.json",assessment)
    (out/"rapport.md").write_text(make_report(registry,result),encoding="utf-8")
    (out/"matrice_litterature.md").write_text(matrix_markdown(registry),encoding="utf-8")
    (out/"references.bib").write_text(bibliography(registry),encoding="utf-8")
    progress.event("Positioning complete",force=True,state="completed",novelty="not_determined_by_this_tool")
    write_manifest(out)
    print(json.dumps({"status":"positioning_completed","novelty_status":assessment["novelty_status"],
                      "primary_references":len(registry["papers"]),"report":str(out/"rapport.md"),
                      "market_witness_verified":result["criterion_run"] is not None,
                      "constructive_guaranteed_level":result["constructive"]["guaranteed_level"]},indent=2),flush=True)
    return 0
