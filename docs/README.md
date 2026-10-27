# Documentation

The guides below describe engine version **0.1.6** and the accompanying manuscript, **Dupire Local Volatility: Joint Feasibility and Observation Preserving Refinement**.

| Guide | What it covers |
|---|---|
| [Research results](RESEARCH.md) | Questions answered, theorem correspondence, exact separation, and scope |
| [Reproducibility](REPRODUCIBILITY.md) | Installation, profiles, output files, and success criteria |
| [Data and provenance](DATA.md) | Archived Yahoo inputs, verified downloads, selection, and processing |
| [Exact criteria](CRITERE_PROUVE.md) | Fixed-grid alternative, sufficient refinement theorem, and proof |
| [Constructive calibration](CONSTRUCTIVE.md) | Bernstein coefficient constraints, certificate generation, and verification |
| [Numerical LP mathematics](MATHEMATICS.md) | Historical `solve`/`verify` semantics, binary64 models, audits, and relaxation |
| [Yahoo normalization](YAHOO_NORMALIZATION.md) | Put-call parity, nominal curves, uncertainty envelopes, and settlement conventions |
| [Yahoo quality](YAHOO_QUALITY.md) | Snapshot diagnostics, expiry selection, and interpretation of rejected books |
| [Crossed-book policy](CROSSED_BOOK_POLICY.md) | Explicit rejection or exclusion, provenance, and certificate scope |
| [Validation record](../VALIDATION.md) | Archived local checks and native Ubuntu/Windows CI |
| [Proof reconstruction](../analyse_dependances/README.txt) | Standard-library commands and generated proof files |
| [Contribution audit](../audit_apport/README.md) | Exact examples, claim audits, literature records, and review workflow |
| [Reading workflow](../audit_apport/LECTURES.md) | Source extraction, review status, and interpretation checks |
| [Literature positioning](../positionnement_litterature/README.md) | Comparators, ablations, and exports |
| [Mathematical alignment](../positionnement_litterature/docs/ALIGNEMENT_MATHEMATIQUE.md) | Assumptions that must match before comparing results |

Run commands from the repository root unless a guide says otherwise. In PowerShell, `$PyDupire` denotes the absolute `.venv312\Scripts\python.exe` path established in the root README. For Bash, use `.venv312/bin/python` with the same arguments and replace PowerShell backtick continuations with backslashes.

Existing French filenames, command names, JSON keys, and status values remain stable so archived workflows continue to work. Original proof notes, source quotations, and generated bibliographic receipts retain their source language and recorded hashes; the English guides explain their purpose and limits.
