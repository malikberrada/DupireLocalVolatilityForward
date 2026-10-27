ANALYSE DES DEPENDANCES DU PROJET DUPIRE - 27 OCTOBRE 2026

Ouvrir Analyse_dependances_Dupire_20261027.pdf pour les preuves et la portee.
La source LaTeX est incluse. Aucun texte integral tiers n'est redistribue.

Resultat supplementaire demontre : sur les spreads positifs de l'exemple,
aucun fit backward grossier ne peut conserver son prix central final et etre
un fit conjoint apres une seule subdivision. Ecart strict : 1153/128000000.
Un certificat dual complementaire a dix termes verifie aussi directement
la contradiction avec conservation des prix, avec marge 4739/384000000.
Cela distingue la recuperation en un niveau du raffinement conservant les
prix calibres de Buehler-Ryskin, section 4.4. Ce n'est pas une preuve de
priorite mondiale ni d'independance de tous les outils classiques.

Le PDF derive C1 et les composantes de C3 depuis les estimations et contraintes
connues. Il donne aussi une caracterisation exacte avec fourchette terminale
pour trois strikes a voisins constants, avec construction rationnelle.

Verification (Python 3.10+, bibliotheque standard seulement), dans ce dossier :

  python -I -S verifier_dependances.py
  python -I -S verifier_dependances.py --verify-json preuves_dependances.json

Regenerer le certificat dual et exporter les preuves et les caracterisations :

  python -I -S generer_dependances.py --out ../runs/preuves_dependances

Le certificat conservation_endpoint.certificate.json est reconstruit depuis
les contraintes et leurs boites de prix. Le certificat stocke dans ce dossier
n'est pas lu par le generateur. La copie nouvellement ecrite est ensuite verifiee.
La caracterisation est accompagnee de temoins rationnels aux deux extremites
de l'intervalle atteignable et pour la fourchette centrale observee.

Fichiers supplementaires produits :
  separation_robuste.json
  caracterisation_trois_strikes.json
  C1_C3_derivations.json
  preuves/C1_taylor_quotient.tex
  preuves/C3_seuil_point_milieu.tex
  preuves/caracterisation_trois_strikes.tex
  preuves/separation_robuste.tex
  generation.json

Les quatre fichiers preuves/*.tex sont des fragments extraits du rapport
maitre, pas des documents LaTeX autonomes. Le generateur reproduit les preuves
redigees ; il ne decouvre ni ne prouve automatiquement de nouveaux theoremes.
Par defaut, le PDF fourni est recopie : aucune installation TeX n'est requise.
Pour recompiler le rapport depuis sa source (pdflatex doit etre sur le PATH) :

  python -I -S generer_dependances.py --out ../runs/preuves_dependances --compile-pdf

Depuis le dossier genere, le controle autonome est identique :

  python -I -S verifier_dependances.py --verify-json preuves_dependances.json

Le programme ne contacte aucun reseau et n'appelle aucun solveur. Les preuves
generales sont redigees, pas verifiees dans un assistant de preuve formelle.
Les tests d'extremites ne sont pas presentes comme une preuve universelle.
Le verificateur independant et les certificats precedents sont conserves pour
recontroler integralement l'exemple mathematique avant les nouvelles bornes.

sources.json distingue les PDF obtenus des simples notices et apercus. Les
empreintes lient les versions effectivement consultees. Elles ne valident pas
automatiquement les interpretations bibliographiques.

Ce dossier est autonome. Il ne remplace ni ne valide des lectures humaines,
et ne modifie pas vos campagnes bibliographiques ou votre registre v0.5.3.
