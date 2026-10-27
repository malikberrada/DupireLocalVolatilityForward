# Contribution audit and bibliographic review

Audit version **0.5.3**, used with **dupire-joint 0.1.6**. Install from the repository root as described in the [main README](../README.md). The self-contained reference workflow is `scripts/reproduce.py --profile core`. Commands naming personal historical campaigns require those campaign files; automated reading does not recreate them.

The audit keeps mathematical certificates, provenance, literature annotations, and declared human readings separate. See [the current research guide](../docs/RESEARCH.md) for the manuscript's results, including the additional endpoint-preservation separation.

## Corrected reading record

Version 0.5.3 revised **18 analyses and 162 hypothesis rows** from the supplied v052 workbook. It corrected attribution, separated sufficient condition C1 from exact scalar threshold C3, and removed unsupported originality claims. Six source PDFs were matched to named statements and recorded hashes. Applying these corrections requires no local language model.

Two additional arguments are included: the scalar C3 time threshold follows algebraically from Buehler-Ryskin constraints (18) and (21) in the restricted class; a time-affine polynomial satisfies C1's continuous assumptions while obstructing a literal identification with the displayed Zhang assumption A5. The latter does not refute Zhang's lemma or exclude other derivations of C1.

The original detailed receipt is [verification_v053.md](bibliography/verification_v053.md). The corrected workbook is `validation/corrections/lectures_corrigees.json`. It remains pending a reader's declaration, with 19 unfilled comparisons preserved. Original generated receipts retain their source language and recorded content.

To apply corrections to an existing personal campaign:

```powershell
& $PyDupire -u audit_apport/rectifier_lectures.py `
  --workbook runs/analyses_bibliographiques_v052/lectures_a_valider.json `
  --campaign runs/lectures_bibliographiques_v050 --out runs/corrected_readings

& $PyDupire -u audit_apport/rectifier_lectures.py `
  --verify runs/corrected_readings --campaign runs/lectures_bibliographiques_v050

& $PyDupire -I -S audit_apport/verifier_arguments.py
```

Correction checks the six sources, locates statement titles on their pages, rebuilds campaign passage IDs, and records field changes. It refuses already modified or accepted analyses. New outputs preserve prior sealed folders. Verification without `--campaign` checks the retained dossier without claiming to reread unavailable PDFs.

The reading workflow, including optional Ollama drafts, is documented in [LECTURES.md](LECTURES.md). Diagnostics flag role confusion, unsupported novelty, and necessity/sufficiency errors; they invite review rather than certify semantic correctness. French locators and alphanumeric identifiers such as `S0.2` remain supported.

## Mathematical evidence without a new Yahoo capture

```powershell
& $PyDupire -u audit_apport/auditer_apport.py --evidence-only --out runs/contribution_evidence
& $PyDupire -u audit_apport/auditer_apport.py --verify runs/contribution_evidence
& $PyDupire -u audit_apport/verifier_joint_independant.py runs/contribution_evidence/joint_discriminant
```

The third command uses only the Python standard library; the first two use the installed engine. Older 0.2 audit folders remain readable. Windows requires timezone data where the native database is absent.

The joint example keeps the same six positive-width intervals, irregular strikes, and variance bounds `[3/100,1/25]`. Forward and backward are separately feasible, their coarse intersection has an exact dual gap `991/8000000`, and one time halving yields a common exact witness. The grid changes from `2x3` to `3x3`; the first feasible dyadic level is exactly 1. The constant-neighbor time threshold is `1/15`. The midpoint construction remains inside the observed intervals at all later certified temporal levels.

See [JOINT_SEPARATION.md](literature/JOINT_SEPARATION.md) for the original lemmas. The later standard-library dossier in [analyse_dependances](../analyse_dependances/README.txt) adds the complete terminal-interval characterization and the ten-term endpoint-preservation dual.

## Audit an existing market result

```powershell
& $PyDupire -u audit_apport/auditer_apport.py `
  --criterion-run runs/criterion `
  --accepted-dir runs/accepted_market --out runs/contribution_audit
```

`--accepted-dir` must contain the actual `raw_snapshot.json`, `snapshot.json`, `selection.json`, `curves_estimees.csv`, `curves_estimees.csv.uncertainty.json`, and `F0.exact_grid.json`. `--criterion-run` supplies `criterion.problem.json` and `criterion.certificate.json`. `--logical-grid` is optional and defaults to the accepted directory's grid. Missing or inconsistent inputs fail explicitly.

Without downloading a new chain, the audit checks:

1. recorded selection replayed from every raw row;
2. nominal curves reconstructed by rational parity intersection;
3. normalized calls and puts with unchanged retained bid-ask intervals;
4. source hash, axes, and the joint certificate's observed constraints;
5. the rational witness and directly recomputed inequalities.

Provenance checks bind the declared data chain. They do not authenticate Yahoo, certify bid-ask times, prove robustness over uncertain curves, or establish that the selection rule preceded development-time price inspection. Initial selection in multiples of 50 remains an observation restriction.

A complete included example is available:

```powershell
& $PyDupire -u audit_apport/auditer_apport.py --demo --out runs/contribution_demo
& $PyDupire -u audit_apport/auditer_apport.py --verify audit_apport/validation/demo
```

The demo reuses original `attempt_03` and its 0.1.6 exact grid and joint certificate. Selection and curve files were reconstructed retrospectively; `REPLAY_ORIGIN.json` records this. It is not a new market observation. Verification recomputes normalization, proofs, and observation links from copied input bytes, rather than checking hashes alone. Each generated audit requires a new output folder.

## Hypothesis comparisons and source attachment

`literature/theoremes.json` records **16 axes and 8 results or formulations**, including Buehler-Ryskin Results 3.2-3.3, Kundu et al. 2016 equations (18)-(25), Kundu-Kumar-Tomar 2024's abstract and public technical appendix, SANOS Proposition 3.8 and Theorem 3.7, methodological comparisons with Chataigner-Crepey-Dixon, Zhang Lemma S0.2, and Austing's exact repricing scheme. The two additional axes concern the new scalar lemmas, rather than hypotheses of the sufficient polynomial theorem.

The generated hypothesis matrix contains 128 comparisons. Annotations record targeted readings and explicitly labeled scope inferences, not automatic equivalence proofs. The archived KKT2024 main-text and Kundu 2017 thesis access gaps remain recorded.

```powershell
& $PyDupire -u audit_apport/auditer_apport.py --demo `
  --source 'KKT2024=C:\Articles\KKT2024.pdf' --out runs/audit_with_source
```

Attaching a document does not change its reading status. `a_completer_KKT2024.json` identifies missing axes. After actual review, supply a **copy** of `literature/theoremes.json` using `--comparisons PATH`. A `full_text_sections_reviewed` entry requires `full_text_review` with `reviewer`, `review_date`, and the exact `source_sha256`, together with the same attached source. This binds a declaration; it does not validate interpretation automatically.

## Additional polynomial discriminant

The finite catalog uses `T in [1/4,5/4]` and strikes `[9/10,1,27/25]`. Its six positive-spread observations remain identical at every level; inserted nodes are unknowns, not quotes. The first selected family is

$$
P(T,x)=\frac45-x+\frac{x^2}{4}\left(1+\frac{T-1/4}{50}\right)^2.
$$

Variance bounds are `391/10000` and `803/20000`, approximately 19.77% to 20.04% in volatility. This synthetic experiment does not alter Yahoo data. It supplies feasible `F0` on `2x3`, exact coarse joint infeasibility, joint feasibility at space-time level 2 on `5x9` with unchanged observations, and a certified Bernstein witness whose conservative bound guarantees level 6 onward.

Polynomial failure at an intermediate level does not exclude every nodal calibration. A search failure in a finite family does not establish nonexistence. `--max-candidates 1..3` and `--max-level 0..6` bound that search; `--joint-candidates 1..3` and `--joint-max-level 0..6` bound the separate joint example. A zero joint refinement budget retains the three coarse certificates without materializing the fourth.

## Bibliographic dossier and declared priority argument

The retained 0.4 dossier contains 13 works, three separate claims, 37 annotated comparisons, seven Crossref metadata snapshots, and a log of searches actually performed:

| Label | Claim tracked |
|---|---|
| C1 | Quantified sufficient refinement with original observations preserved |
| C2 | Rational example of separate feasibility and an empty intersection |
| C3 | Exact time threshold for three strikes with constant neighbors |

```powershell
& $PyDupire -u audit_apport/priorite_bibliographique.py `
  --audit-dir runs/contribution_evidence --out runs/bibliographic_priority
& $PyDupire -u audit_apport/priorite_bibliographique.py --verify runs/bibliographic_priority
```

The first command copies and reverifies the existing audit without Yahoo acquisition or a new LP solve. Without `--audit-dir`, the standard library can produce a bibliographic dossier while marking mathematical evidence as absent. Do not put the output inside the source audit. `rapport_priorite.md` and `priority.json` retain passages, assumptions, derivability annotations, and claim-specific gaps.

To supplement the record, copy `bibliography/review.template.json`, record the reader, date, pages, assumptions, conclusion, exact version, and source hash, then attach the same text. `relation` accepts `component_prior`, `different_statement`, `equivalent_or_stronger`, or `unresolved`; `derivability` accepts `component_only`, `not_a_direct_corollary`, `direct_specialization`, or `unresolved`. `selected_statement` remains targeted; `full_work` declares a whole-work review.

A public dated project version must be documented separately using `bibliography/project_record.template.json`, locating C1-C3 individually. The public GitHub repository now exists, but its existence alone does not fill or backdate a historical priority form.

```powershell
& $PyDupire -u audit_apport/priorite_bibliographique.py `
  --audit-dir runs/contribution_evidence --reviews my_reviews.json `
  --source 'KKT2024=C:\Articles\KKT2024.pdf' `
  --project-record project_public_record.json `
  --source 'PROJECT=C:\Articles\public_project_version.pdf' `
  --out runs/completed_bibliographic_record
```

Use a copied `--registry` and its adjacent `snapshots` when the exact reviewed version needs an additional dated public event. Do not date a current PDF by the first appearance of a different file. The status `priority_argument_documented_in_declared_corpus` requires the sources, dated versions, derivability analyses, and public project record for every required comparison. It remains limited to that corpus. `scientific_priority_certified` stays `false`.

Only explicit metadata refresh contacts Crossref:

```powershell
& $PyDupire -u audit_apport/priorite_bibliographique.py `
  --refresh-metadata --out runs/refreshed_bibliography
```

`created`, `indexed`, and `deposited` are not used as publication dates. Month/year precision is preserved. Network failure retains the previous snapshot and records `refresh_log.json`. Refresh does not change reading status. The default cutoff remains 27 October 2026; later events are not treated as prior work at that cutoff.

## Outputs and tests

| Output | Contents |
|---|---|
| `rapport.md`, `audit.json`, `claims.json` | Conclusions, candidate contributions, and limits |
| `literature/matrice_hypotheses.md` | 128 comparisons and open axes |
| `joint_discriminant/*.problem.json`, `*.certificate.json` | Four exact separate/joint/refined proofs |
| `joint_discriminant/theory.json` | Scalar threshold and uniform interval-preservation bounds |
| `yahoo/lineage.json`, `yahoo/observation_links.json` | Contract-level provenance |
| `discriminant/*.problem.json`, `*.certificate.json` | Polynomial discriminant's rational evidence |
| `discriminant/polynomial.json`, `search_protocol.json` | Construction, margins, and search budget |
| `manifest.json` | Saved output hashes |

```powershell
& $PyDupire -m pytest audit_apport/tests -q
```

The included examples establish the specified mathematical statements and recorded provenance. They do not establish general priority, complete reproduction of every comparator, or empirical superiority over prior calibration methods.
