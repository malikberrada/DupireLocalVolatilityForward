from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path

from dupire_joint.progress import Progress
from . import __version__
from .io import read, write, copy, require, seal, check_manifest
from .literature import generate, verify_comparison
from .trace import audit, verify_audit
from .discriminant import search, verify_search
from .joint_separation import search as search_joint, verify_search as verify_joint
from .novelty import generate as generate_claims, verify_assessment

ROOT = Path(__file__).resolve().parents[1]


def legacy_report(data):
    lit, market, example = data["literature"], data["yahoo"], data["discriminant"]
    lines = ["# Audit de l’apport constructif", "",
       "Ce dossier compare des énoncés identifiés, reconstruit la provenance de l’instance Yahoo et recherche un cas synthétique discriminant. Aucune priorité scientifique n’est certifiée.", "",
       "## Comparaison des hypothèses", "",
       f"{lit['selected_results']} résultats ou formulations, {lit['axes']} axes, {lit['comparison_cells']} cellules. Voir `literature/matrice_hypotheses.md`.", "",
       "Les annotations distinguent lecture de source et inférence de portée. Une propriété hors d’un énoncé n’est pas déclarée absente de l’article entier.", "",
       "Texte intégral KKT2024 comparé : `" + str(lit["full_text_KKT2024_review_complete"]) + "`. Les inconnues restent ouvertes.", "",
       "## Traçabilité Yahoo", "",
       "Statut : `" + market["status"] + "`.", "",
       f"{market['observation_count']} observations ({market['call_count']} calls, {market['put_count']} puts), grille {market['shape']}.", "",
       "Les livres bruts sont reliés individuellement aux observations normalisées dans `yahoo/observation_links.json`. La sélection est rejouée, les courbes recalculées et le témoin rationnel joint revérifié. Les fichiers d’entrée sont conservés octet pour octet.", "",
       "Les hash ne prouvent ni l’authenticité du fournisseur ni la synchronisation des bid/ask. Le contrôle ne prouve pas non plus que la sélection ait été décidée avant examen des prix. La normalisation reste nominale et la chaîne brute entière n’est pas certifiée.", ""]
    if market.get("replay_metadata"):
        lines += ["Les fichiers de sélection et de courbes de cet exemple livré ont été reconstruits rétrospectivement depuis l’archive. La grille et le certificat initialement archivés ont été conservés. Cette reconstruction ne constitue pas une nouvelle collecte.", ""]
    lines += ["## Exemple discriminant", "", "Origine : recherche synthétique contrôlée, distincte de Yahoo.", ""]
    if example["status"] == "discriminating_example_certified":
        lines += ["| Problème | Conclusion et preuve |", "| --- | --- |",
                  "| Grille initiale, sans bornes locales | F0 faisable, témoin rationnel |",
                  "| Même grille, avec bornes locales | Infaisable, séparateur rationnel |",
                  "| Grille raffinée, mêmes observations et bornes | Faisable, témoin commun forward/backward |", "",
                  f"Grille initiale : {example['coarse_shape']}. Grille raffinée : {example['refined_shape']}, niveau {example['first_verified_polynomial_level']}.", "",
                  "Bornes de **variance** : " + ", ".join(example["variance_bounds"]) + ". Elles sont propres à ce test synthétique et ne remplacent pas les paramètres Yahoo.", "",
                  f"Le théorème garantit tous les niveaux à partir de {example['guaranteed_level_by_sufficient_bound']}. Le témoin explicite passe déjà au niveau {example['first_verified_polynomial_level']}. Cela mesure le conservatisme de la borne suffisante.", "",
                  "Les nœuds originaux et les six intervalles sont identiques entre les deux problèmes. Aucun prix observé n’est retiré, élargi ou interpolé. L’échec éventuel du polynôme à un niveau intermédiaire ne prouve pas l’infaisabilité du LP à ce niveau.", "",
                  "Le résultat montre que les contraintes locales et le choix de grille changent effectivement la faisabilité dans le système du projet. Il ne prouve aucun emboîtement général des ensembles admissibles ni aucune supériorité sur les modèles publiés.", ""]
    else:
        lines += ["Aucun cas discriminant trouvé dans le budget déclaré. Cela ne prouve pas son inexistence.", ""]
    lines += ["## Relecture", "",
              "`python -u .\\audit_apport\\auditer_apport.py --verify CHEMIN_DU_DOSSIER`", "",
              "La relecture contrôle les hash, refait la normalisation et les inégalités rationnelles, puis régénère la matrice à partir des annotations. Elle n’appelle ni solveur ni réseau ; elle ne relit pas sémantiquement les articles à la place du chercheur.", ""]
    return "\n".join(lines)


def report(data):
    if data["version"] == "0.2.0":
        return legacy_report(data)
    lit, old, joint = data["literature"], data["discriminant"], data["joint_discriminant"]
    lines = [f"# Éléments supplémentaires pour l’évaluation de la contribution — {data['version']}", "",
             "Le résultat ci-dessous établit une distinction mathématique supplémentaire. La priorité bibliographique reste non confirmée.", "",
             "## Faisabilité séparée et intersection", "",
             "Les problèmes comparés conservent les mêmes observations et les mêmes bornes de variance. Origine : construction synthétique déclarée.", ""]
    if joint["status"] in {"joint_separation_certified", "joint_separation_and_time_refinement_certified"}:
        lines += ["| Problème | Résultat exact |", "| --- | --- |",
                  "| Forward seul, grille initiale | Faisable, témoin rationnel |",
                  "| Backward seul, mêmes données | Faisable, autre témoin rationnel |",
                  "| Forward ET backward, mêmes données | Impossible, séparateur combinant les deux familles |"]
        if joint["refined_joint"] == "feasible_exact":
            lines += ["| Après subdivision temporelle, mêmes strikes et six spreads | Faisable conjointement |"]
        lines += ["", "Écart du séparateur : `"+joint["joint_separator"]["exact_separation_margin"]+"`.", "",
                  f"Grille initiale : {joint['coarse_shape']}. Bornes de variance : {joint['variance_bounds']}.", "",
                  "L’intersection vide est prouvée pour toutes les sélections dans les spreads, pas seulement pour les deux témoins proposés.", ""]
        if joint["refined_joint"] == "feasible_exact":
            lines += [f"Grille raffinée : {joint['refined_shape']}, niveau temporel {joint['first_materialized_time_level']}.", "",
                      "Premier niveau dyadique faisable établi : `"+str(joint["first_feasible_time_level_proved"])+"`.", ""]
        lines += ["Le nouveau lemme donne un seuil de compatibilité pour une classe à trois strikes et prix voisins constants. Dans cette famille, le témoin à point milieu préserve les observations à tous les niveaux ultérieurs au seuil. Voir `literature/JOINT_SEPARATION.md` et `joint_discriminant/theory.json`.", "",
                  "Ce raffinement ne porte que sur le temps. Il s’agit d’une construction distincte du polynôme et du raffinement espace-temps du théorème 2 de la version 0.1.6.", ""]
    else:
        lines += ["Aucun séparateur conjoint trouvé dans le budget déclaré. Aucune inexistence n’est conclue.", ""]
    lines += ["## Comparaison bibliographique", "",
              f"{lit['selected_results']} énoncés ou formulations × {lit['axes']} axes = {lit['comparison_cells']} comparaisons annotées.", "",
              "Voir les énoncés nommés et leurs niveaux d’accès dans `literature/matrice_hypotheses.md`. Une différence avec un énoncé sélectionné n’exclut pas tous les autres résultats d’un article.", "",
              "Les annotations sont déclarées et traçables ; leur interprétation sémantique n’est pas prouvée par le programme.", "",
              "## Exemple polynomial précédent", "", "Statut : `"+old["status"]+"`.", ""]
    if lit.get("critical_source_gaps"):
        insertion = lines.index("## Exemple polynomial précédent")
        lines[insertion:insertion] = ["Sources restant à examiner : "+" ; ".join(lit["critical_source_gaps"])+".", ""]
    if old["status"] == "discriminating_example_certified":
        lines += ["Il établit un effet des contraintes locales et du raffinement.", ""]
        individual = old.get("individual_stencil_obstructions", {})
        if individual and all(c["verified"] for c in individual.values()):
            lines += ["Ses contraintes forward et backward sont déjà impossibles séparément sur la grille grossière : il n’isole pas l’effet de leur intersection.", ""]
    else:
        lines += ["Aucun exemple polynomial complet trouvé dans le budget déclaré ; aucune inexistence n’est conclue.", ""]
    market = data["yahoo"]
    if market is None:
        lines += ["## Données de marché", "", "Mode `--evidence-only` : aucune nouvelle évaluation Yahoo dans ce dossier.", ""]
    else:
        lines += ["## Traçabilité Yahoo", "", "Statut : `"+market["status"]+"`.", "",
                  f"{market['observation_count']} observations ({market['call_count']} calls, {market['put_count']} puts), grille {market['shape']}.", "",
                  "La sélection est rejouée depuis les livres bruts ; les courbes nominales, la normalisation et le certificat joint sont revérifiés. Les hash lient les fichiers et ne prouvent pas l’authenticité Yahoo, la synchronisation des prix ou une sélection décidée avant observation des données.", ""]
        if market.get("replay_metadata"):
            lines += ["Le demo utilise l’archive antérieure avec métadonnées de sélection et de courbes reconstruites rétrospectivement. Ce n’est pas une nouvelle collecte.", ""]
    lines += ["## Portée scientifique", "",
              "Les nouveaux certificats établissent F_forward et F_backward non vides avec F_joint vide, puis une réparation par subdivision temporelle conservant les observations. Ce sont des éléments supplémentaires par rapport au dossier précédent.", "",
              "Le fichier `claims.json` relie les revendications à leurs preuves et aux lacunes documentaires. Les outils de Farkas, Bernstein, consistance avec marge et point milieu ne sont pas revendiqués comme nouveaux. Aucune priorité scientifique n’est attribuée automatiquement.", "",
              "## Relecture", "",
              "`python -u .\\audit_apport\\auditer_apport.py --verify CHEMIN_DU_DOSSIER`", "",
              "Vérificateur indépendant des quatre preuves, bibliothèque standard Python seulement :", "",
              "`python -u .\\audit_apport\\verifier_joint_independant.py CHEMIN_DU_DOSSIER\\joint_discriminant`", ""]
    return "\n".join(lines)


def verify_folder(folder, max_nodes=100000):
    folder = Path(folder).resolve()
    count = check_manifest(folder)
    data = read(folder/"audit.json")
    require(data["version"] in {"0.2.0", "0.3.0", "0.4.0", "0.5.0", "0.5.1", "0.5.2", "0.5.3"}, "Unknown audit version")
    require(data["scientific_novelty_certified"] is False, "Unsupported scientific-priority conclusion")
    literature = verify_comparison(folder/"literature")
    yahoo = verify_audit(folder/"yahoo", max_nodes) if data["yahoo"] is not None else None
    discriminant = verify_search(folder/"discriminant")
    require(data["literature"] == read(folder/"literature/comparison.json"), "Summary literature differs")
    if data["yahoo"] is not None:
        require(data["yahoo"] == read(folder/"yahoo/lineage.json"), "Summary Yahoo differs")
    require(data["discriminant"] == read(folder/"discriminant/result.json"), "Summary example differs")
    require((folder/"rapport.md").read_text(encoding="utf-8") == report(data), "Summary report differs")
    joint = claims = None
    if data["version"] in {"0.3.0", "0.4.0", "0.5.0", "0.5.1", "0.5.2", "0.5.3"}:
        joint = verify_joint(folder/"joint_discriminant")
        require(data["joint_discriminant"] == read(folder/"joint_discriminant/result.json"), "Summary joint evidence differs")
        claims = verify_assessment(folder, data["literature"], data["joint_discriminant"])
        require(data["claims"] == read(folder/"claims.json"), "Summary contribution assessment differs")
    return {"status": "verified_exact_audit", "file_hashes": count, "yahoo": yahoo,
            "discriminant": discriminant, "literature": literature, **({"joint_discriminant": joint, "claims": claims} if joint else {}),
            "solver_called": False, "network_used": False, "scientific_novelty_certified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare hypotheses, verify Yahoo lineage and find an exact discriminating example")
    parser.add_argument("--criterion-run", type=Path)
    parser.add_argument("--accepted-dir", type=Path, help="Collector accepted folder: raw, selected, selection, curves and F0.exact_grid")
    parser.add_argument("--logical-grid", type=Path, help="Optional external copy of the original F0.exact_grid.json")
    parser.add_argument("--comparisons", type=Path, default=ROOT/"literature/theoremes.json")
    parser.add_argument("--source", action="append", default=[], metavar="PAPER_ID=PATH", help="Attach a local source without changing its review status")
    parser.add_argument("--max-level", type=int, default=4)
    parser.add_argument("--max-candidates", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=100000)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--demo", action="store_true", help="Use the included archived Yahoo instance with reconstructed curve files")
    parser.add_argument("--evidence-only", action="store_true", help="Generate the new mathematical and literature evidence without Yahoo inputs")
    parser.add_argument("--joint-max-level", type=int, default=4, help="Time-only subdivision budget 0..6 for the separate/joint example")
    parser.add_argument("--joint-candidates", type=int, default=3, help="Declared joint-search catalogue budget 1..3")
    parser.add_argument("--verify", type=Path, help="Reverify a completed audit without solver or network")
    args = parser.parse_args(argv)
    if args.verify:
        print(json.dumps(verify_folder(args.verify, args.max_nodes), ensure_ascii=False, indent=2), flush=True)
        return 0
    if args.demo:
        if args.criterion_run or args.accepted_dir or args.logical_grid:
            parser.error("--demo cannot be mixed with personal market inputs")
        args.criterion_run = args.accepted_dir = ROOT/"fixtures/yahoo"
    if args.evidence_only and (args.demo or args.criterion_run or args.accepted_dir or args.logical_grid):
        parser.error("--evidence-only cannot be mixed with market inputs or --demo")
    if not args.evidence_only and (not args.criterion_run or not args.accepted_dir):
        parser.error("Provide --criterion-run AND --accepted-dir, or use --demo")
    if not 0 <= args.max_level <= 6 or not 1 <= args.max_candidates <= 3 or args.max_nodes < 6:
        parser.error("Require max-level 0..6, max-candidates 1..3, max-nodes >=6")
    if not 0 <= args.joint_max_level <= 6 or not 1 <= args.joint_candidates <= 3:
        parser.error("Require joint-max-level 0..6 and joint-candidates 1..3")
    version = importlib.metadata.version("dupire-joint")
    require(version == "0.1.6", "This add-on targets dupire-joint 0.1.6; install the source repository at version 0.1.6")
    out = args.out or Path("runs")/("audit_apport_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
    require(not out.exists() or not any(out.iterdir()), "Use a new --out folder; previous proofs are preserved")
    out.mkdir(parents=True, exist_ok=True)
    progress = Progress(out)
    with progress.phase("Compare the declared theorem hypotheses"):
        literature = generate(args.comparisons, out/"literature", args.source)
        copy(ROOT/"literature/CRITERE_PROUVE_0.1.6.md", out/"literature/CRITERE_PROUVE_0.1.6.md")
        copy(ROOT/"literature/JOINT_SEPARATION.md", out/"literature/JOINT_SEPARATION.md")
        copy(ROOT/"literature/recherche_complementaire.json", out/"literature/recherche_complementaire.json")
    yahoo = None
    if not args.evidence_only:
        with progress.phase("Rebuild Yahoo lineage from raw archived books"):
            yahoo = audit(args.accepted_dir, args.criterion_run, out/"yahoo", args.logical_grid, args.max_nodes)
    with progress.phase("Search a rational discriminating example"):
        example = search(out/"discriminant", args.max_level, args.max_candidates, progress)
    with progress.phase("Certify individual feasibility with an empty joint intersection"):
        joint = search_joint(out/"joint_discriminant", args.joint_max_level, args.joint_candidates, progress)
    claims = generate_claims(out, literature, joint)
    data = {"version": __version__, "dupire_joint": version, "literature": literature,
            "yahoo": yahoo, "discriminant": example, "joint_discriminant": joint, "claims": claims,
            "scientific_novelty_certified": False,
            "network_used": False, "solver_called": False}
    write(out/"audit.json", data)
    (out/"rapport.md").write_text(report(data), encoding="utf-8")
    seal(out)
    with progress.phase("Reverify every proof and lineage in the completed folder"):
        checked = verify_folder(out, args.max_nodes)
    print(json.dumps({"status": "audit_completed", "version": __version__, "trace": yahoo["status"] if yahoo else "not_requested",
                      "discriminant": example["status"], "joint_discriminant": joint["status"],
                      "report": str(out/"rapport.md"), "independent_reverification": checked["status"],
                      "KKT2024_full_text_reviewed": literature["full_text_KKT2024_review_complete"],
                      "scientific_novelty_certified": False}, ensure_ascii=False, indent=2), flush=True)
    return 0
