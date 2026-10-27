"""Keep computational proofs separate from a bibliographic priority claim."""
from .io import read, write, require


def assessment(literature, joint):
    separated = joint["status"] in {"joint_separation_certified", "joint_separation_and_time_refinement_certified"}
    refined = joint["status"] == "joint_separation_and_time_refinement_certified"
    return {
        "format": "dupire-contribution-evidence-v1",
        "verdict": "mathematical_evidence_verified_priority_unconfirmed" if separated else "search_incomplete",
        "new_elements_relative_to_the_previous_project_dossier": {
            "individual_feasibility_with_empty_intersection": separated,
            "same_quotes_time_refinement_restores_joint_feasibility": refined,
            "minimal_dyadic_time_level_proved": refined and joint["first_feasible_time_level_proved"],
            "explicit_time_compatibility_lemma_in_a_restricted_class": separated,
        },
        "mathematical_evidence": [
            {"claim": "Separate feasibility does not imply joint feasibility",
             "proofs": ["joint_discriminant/coarse_forward.certificate.json",
                        "joint_discriminant/coarse_backward.certificate.json",
                        "joint_discriminant/coarse_joint.certificate.json"], "verified": separated},
            {"claim": "Time refinement can restore joint feasibility with all quotes and bounds unchanged",
             "proofs": ["joint_discriminant/coarse_joint.certificate.json",
                        "joint_discriminant/refined_joint.certificate.json"], "verified": refined},
        ],
        "literature_comparison_cells": literature["comparison_cells"],
        "semantic_annotations_auto_verified": False,
        "critical_source_gaps": literature.get("critical_source_gaps", []),
        "classical_tools_not_claimed_as_new": ["Farkas alternative", "Bernstein positivity",
                                               "consistency plus strict margin", "implicit midpoint recurrence"],
        "novelty_from_search_absence_inferred": False,
        "scientific_priority_certified": False,
        "interpretation": "Les nouvelles preuves renforcent une contribution candidate. Elles ne prouvent pas que ces résultats n’ont jamais été publiés.",
    }


def generate(folder, literature, joint):
    result = assessment(literature, joint)
    write(folder/"claims.json", result)
    return result


def verify_assessment(folder, literature, joint):
    result = read(folder/"claims.json")
    require(result == assessment(literature, joint), "Contribution assessment differs from its verified evidence")
    return {"verified": True, "mathematical_new_elements": result["new_elements_relative_to_the_previous_project_dossier"],
            "scientific_priority_certified": False}
