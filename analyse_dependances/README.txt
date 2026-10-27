DUPIRE DEPENDENCY ANALYSIS - 27 OCTOBER 2026

Open Analyse_dependances_Dupire_20261027.pdf for the original written proofs
and their scope. Its LaTeX source is included. The original proof note is in
French; the maintained English research guide is ../docs/RESEARCH.md.
No third-party full text is redistributed in this folder.

Additional result: over the example's positive spreads, no coarse backward
fit can preserve its final central price and become a joint fit after one
temporal halving. The strict gap is 1153/128000000. A complementary ten-term
exact dual proves the endpoint-preservation contradiction directly, with
margin 4739/384000000. This separates that one-level recovery from the
calibrated-price-preserving construction in Buehler-Ryskin Section 4.4.
Their option of recalibrating on a finer grid remains compatible with the
example. General priority and independence from all classical tools are
not established.

The PDF derives C1 and the components of C3 from known estimates and
constraints. It also gives an exact characterization with a terminal quote
interval for three strikes with constant neighbors, with a rational
construction. The scalar recurrence is the classical implicit midpoint rule.

Verification (Python 3.10+, standard library only), from this folder:

  python -I -S verifier_dependances.py
  python -I -S verifier_dependances.py --verify-json preuves_dependances.json

Regenerate the dual and export the written proofs and characterizations:

  python -I -S generer_dependances.py --out ../runs/proof_dependencies

conservation_endpoint.certificate.json is rebuilt from the constraints and
price boxes. The generator does not read the stored endpoint certificate.
It then verifies the newly written certificate. The characterization includes
rational witnesses at both reachable endpoints and for the observed central
terminal interval.

Additional generated files:
  separation_robuste.json
  caracterisation_trois_strikes.json
  C1_C3_derivations.json
  preuves/C1_taylor_quotient.tex
  preuves/C3_seuil_point_milieu.tex
  preuves/caracterisation_trois_strikes.tex
  preuves/separation_robuste.tex
  generation.json

The four preuves/*.tex files are fragments extracted from the master note,
not standalone LaTeX documents. The generator reproduces written proofs;
it does not automatically discover or prove general theorems. By default,
it copies the supplied PDF, so no TeX installation is required. To recompile
from source, put pdflatex on PATH and run:

  python -I -S generer_dependances.py --out ../runs/proof_dependencies --compile-pdf

Independent verification from the generated folder:

  python -I -S verifier_dependances.py --verify-json preuves_dependances.json

No network or solver is used. The general proofs are authored mathematical
arguments rather than formally machine-verified proofs. Endpoint checks are
not presented as universal proofs. The independent verifier and original
certificates remain available to recheck the complete mathematical example.

sources.json distinguishes retrieved PDFs from abstracts and records. Hashes
bind the consulted versions; they do not validate bibliographic interpretation.
This folder is self-contained and does not accept human readings or modify
the bibliographic campaign's v0.5.3 registry.
