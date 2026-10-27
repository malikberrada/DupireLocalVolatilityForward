# Reading and analysis workflow

Version **0.5.3**. This workflow retrieves accessible source texts, retains their bytes, extracts page and line locators, prepares C1-C3 comparisons, and incorporates explicitly declared readings. Missing access remains visible. Model output is a draft requiring review against the source, particularly for equations.

## Correct the historical v052 workbook

The 18 completed drafts passed structural checks, which do not validate their arguments. Version 0.5.3 supplies documented revisions through `rectifier_lectures.py --workbook ... --campaign ... --out ...`; see the [audit README](README.md). No new Ollama request is required.

Outputs include `lectures_corrigees.json`, the original input, field-level changes, source links, and `verification_bibliographique.md`. Copy the corrected workbook outside its sealed output before further review; retain the old workbook and receipts.

The revision removes the circular ZHANG/C3 reference and incorrect necessity claims for C1. It derives C3's scalar threshold from Buehler-Ryskin inequalities and documents the obstruction to a literal application of Zhang Lemma S0.2 to the full C1 class. It does not automatically record a whole-text reading or accept a reader's interpretation. Later mathematical results are summarized in [the research guide](../docs/RESEARCH.md).

## Prepare a campaign

Install from the repository root in `.venv312`; `$PyDupire` is the explicit interpreter defined in the root README.

```powershell
& $PyDupire -m pip install -r audit_apport/requirements_lectures.txt

& $PyDupire -u audit_apport/completer_lectures.py preparer `
  --priority-dir runs/priorite_bibliographique_v040 `
  --telecharger --decouvrir --workers 2 --out runs/reading_campaign
```

`--telecharger` tries named public routes from `bibliography/source_routes.json`. `--decouvrir` also examines Crossref full-text links after known routes fail. There is no paid-account login, author messaging, or access bypass. Progress and access errors are recorded without converting failures into completed readings.

To attach legitimately obtained local texts, repeat preparation into a new output:

```powershell
& $PyDupire -u audit_apport/completer_lectures.py preparer `
  --priority-dir runs/priorite_bibliographique_v040 `
  --source 'KKT2024=C:\Articles\KKT2024.pdf' `
  --source 'KUNDU2017=C:\Articles\Kundu_Thesis.pdf' `
  --telecharger --decouvrir --out runs/campaign_with_sources
```

`--url 'WORK_ID=https://...'` adds a public route. Without `--telecharger`, only local or attached files are read. An institutional CV is not treated as a thesis. Abstracts, previews, and access barriers are flagged. An extracted PDF still requires identity, version, and extent checks; a one-page PDF may be a preview.

| Output | Contents |
|---|---|
| `documents.json` | Retrieval outcomes, hashes, and indicative title check |
| `documents/WORK_ID/pages.json` | Extracted pages and lines |
| `tasks.json` | 37 comparisons with assumptions and candidate passages |
| `lectures.md` | Retrieved texts and remaining access gaps |
| `lectures_a_valider.json` | Workbook requiring review |

Locators use **physical PDF pages starting at 1**, not printed page numbers. HTML/text uses labeled virtual blocks of 80 lines. Scans require external OCR; extraction errors remain recorded.

## Optional local Ollama drafts

A local Ollama server and an already installed model are required. This module does not download a model or invoke a remote model service.

```powershell
& $PyDupire -u audit_apport/completer_lectures.py analyser `
  --campaign runs/reading_campaign --model 'qwen3.5:35b' `
  --out runs/reading_drafts

# Start with one comparison.
& $PyDupire -u audit_apport/completer_lectures.py analyser `
  --campaign runs/reading_campaign --model 'qwen3.5:35b' `
  --pair CARR2014_C1 --max-pairs 1 --out runs/carr_c1_draft
```

For each work/claim pair and batch, the schema requires all relevant axes (14 for C1, 6 for C2, 7 for C3), prior assumptions and conclusion with quantifiers, direct-specialization analysis, limits, and passage IDs from the supplied source.

Invented passages, missing axes, truncated outputs, and tool requests are rejected. Passage existence can be checked; semantic interpretation cannot. Up to ten selected blocks per comparison do not constitute a whole-work reading. Absence from selected blocks does not mean absence from the source.

Outputs are `WORK_ID_Cn.draft.json`, `analysis_log.json`, and `lectures_a_valider.json`, saved after each comparison. Server failure is explicit. No comparison is accepted automatically; a wholly failed run exits with code 2.

## Resume and diagnose historical partial drafts

The retained 0.5.1 execution contained twelve drafts (two C1, five C2, five C3), none automatically accepted. Its six failed pairs were:

| Pair | Recorded console category |
|---|---|
| `SANOS2026_C1` | `invalid_analysis_schema` |
| `CCD2020_C1` | `incomplete_hypothesis_coverage` |
| `ZHANG2025_C1` | `invalid_analysis_schema` |
| `ZHANG2025_C2` | `invalid_analysis_schema` |
| `ZHANG2025_C3` | `incomplete_hypothesis_coverage` |
| `FH2015_C1` | `invalid_analysis_schema` |

These are historical run states, not the current 18-draft correction count. The precise rejected fields require that run's `analysis_log.json` and `diagnostics/*.response.json`. Its console log did not report truncation. The old array schema allowed duplicate axis IDs, but the supplied log alone does not establish that duplication caused a particular failure.

```powershell
& $PyDupire -u audit_apport/completer_lectures.py analyser `
  --campaign runs/lectures_bibliographiques_v050 --model 'qwen3.5:35b' `
  --resume runs/analyses_bibliographiques_v051 `
  --axes-per-call 1 --retries 2 --out runs/resumed_drafts

& $PyDupire -u audit_apport/completer_lectures.py diagnostiquer `
  --workbook runs/resumed_drafts/lectures_a_valider.json `
  --analysis-dir runs/resumed_drafts
```

Resume checks the same campaign's hashes, copies successful drafts unchanged, and retries missing comparisons. Do not modify sealed inputs first. The six pairs cover 69 axes; one-axis calls can each incur up to two retries.

The 0.5.2 schema requires a property for every axis ID and includes the schema in the prompt. Decoding converts that object to the workbook's ordered list without filling missing content. Older lists remain accepted only with complete, valid, unique coverage; duplicate JSON keys are rejected.

Defaults remain `--num-predict 8000`, `--thinking off`, `--axes-per-call 7`, and `--retries 1`. A rejected multi-axis batch falls back to individual-axis calls with the same checks; connection failures do not multiply per-axis requests. Divergent conclusions remain `unresolved`.

Diagnostics identify empty fields, unknown relations, missing references, and inconsistent IDs through messages and `details.path`. They retain final responses, `done_reason`, token counts, and settings, rather than private reasoning. One complete JSON object wrapped in a Markdown fence may be unwrapped and logged. Incomplete JSON, invented citations, and tool requests remain rejected. See [Ollama structured-output documentation](https://docs.ollama.com/capabilities/structured-outputs).

The 19 source-missing comparisons remain open in the archived workbook. Partial runs return code 2 while preserving usable results. Different assumptions or a missing identical formula do not by themselves exclude a corollary or adaptation.

## Review and declare readings

Copy the workbook outside the sealed folder:

```powershell
Copy-Item runs/reading_drafts/lectures_a_valider.json runs/my_readings.json
```

Without Ollama, start from preparation's workbook. For each source actually read, supply `reviewer`, `review_date`, `version_id`, `identity_confirmed`, and `pages_reviewed`. Check and correct every claim's `analysis`. References can use any indexed block, including passages beyond the initial selection. IDs have the form `p0001:l0001-0016`.

After actual review, record a comparison:

```powershell
& $PyDupire -u audit_apport/completer_lectures.py valider `
  --campaign runs/reading_campaign --workbook runs/my_readings.json `
  --work-id CARR2014 --claim C1 --reviewer 'Abdelmalik Berrada' `
  --date 2026-10-27 --pages '27-30' --scope selected_statement `
  --identity-confirmed --out runs/carr_reviewed.json
```

Use the actual date and pages reviewed. This changes only the named decision and checks that cited passages lie on declared pages. For multiple decisions, use the newest output workbook in each successive command or explicitly edit their `decision` fields to `accepted`.

`selected_statement` records a targeted reading. `full_work` requires all pages declared read, `full_text_extent_confirmed: true`, resolved hypotheses, a derivability analysis, and `--extent-confirmed`. These are reader declarations, not automatic proof of reading or theorem truth.

Record the exact version actually reviewed. Its public date remains unknown until a sourced event identifies that version. For example, a checked `public_version_event` may contain:

```json
{
  "id": "primary_record_checked_v2",
  "kind": "arxiv_submitted",
  "date_parts": [2014, 1, 31],
  "version_id": "arxiv-v2",
  "evidence_url": "https://arxiv.org/abs/1308.2326v2",
  "locator": "Submission history [v2]"
}
```

This example is not another work's publication date. A newer PDF must not be dated by the first submission of a different file.

## Export accepted analyses and reverify

```powershell
& $PyDupire -u audit_apport/completer_lectures.py exporter `
  --campaign runs/reading_campaign --workbook runs/carr_reviewed.json `
  --out runs/reviewed_priority_record

& $PyDupire -u audit_apport/priorite_bibliographique.py --verify runs/reviewed_priority_record

& $PyDupire -u audit_apport/completer_lectures.py verifier `
  --campaign runs/reading_campaign --reextraire
```

Export carries existing mathematical evidence and public project records, attaches accepted sources with page/line locators and hypothesis annotations, and preserves remaining gaps. A targeted comparison does not exclude the rest of a source.

Use `exporter --as-of YYYY-MM-DD` when review occurs after the registry cutoff. Add `--project-record PATH.json --project-source public_article.pdf` to record a newly public project version.

Ordinary verification checks bytes, hashes, passages, and decisions without a network or model. `--reextraire` also compares a fresh PDF extraction, which can require review after extractor-version changes. `scientific_priority_certified` stays `false`; the bibliographic conclusion is limited to documented sources and annotations.

## Recorded tests

Tests cover synthetic PDFs, previews, missing sources, invented references, omitted axes, targeted acceptance, and partial/full exports. Positive priority-workflow fixtures use explicitly fictional publications. Ollama's contract is tested with simulated responses; no large model was run for the original delivery validation. `validation/reading_retrieval.json` records the actual retrieval/extraction trial. Third-party PDFs are not redistributed.
