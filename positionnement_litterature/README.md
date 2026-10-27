> Intégration dans le dépôt : installer depuis la racine selon [le README principal](../README.md). Le parcours autonome testé est `scripts/reproduce.py --profile core`. Les commandes historiques ci-dessous qui nomment une campagne personnelle nécessitent les fichiers de cette campagne ; ils ne sont pas recréés par une lecture automatique.

# Positionner l’apport constructif — complément 0.1.0

Ce complément s’utilise dans ton environnement `.venv312` avec **dupire-joint
0.1.6** installé. Il produit un positionnement bibliographique vérifiable,
des comparaisons mathématiques et des expériences contrôlées. Les annotations
de littérature sont issues de lectures humaines ; le programme vérifie les
preuves et organise les références. Il ne certifie pas une priorité scientifique.

Extraire l’archive dans le dossier du projet : elle crée le sous-dossier
`positionnement_litterature`, avec ses propres scripts et données de contrôle.

## Une commande avec ton exécution Yahoo

```powershell
python -u .\positionnement_litterature\positionner_apport.py `
  --criterion-run .\runs\critere_yahoo `
  --threads 4 `
  --out .\runs\positionnement_litterature
```

Pour lier également le contrôle au fichier de normalisation d’origine :

```powershell
python -u .\positionnement_litterature\positionner_apport.py `
  --criterion-run .\runs\critere_yahoo `
  --logical-grid ".\runs\yahoo_valide_20261026T203526_495751Z\collecte\accepted\F0.exact_grid.json" `
  --threads 4 `
  --out .\runs\positionnement_litterature_source_verifiee
```

Le dossier `--criterion-run` doit contenir `criterion.problem.json` et
`criterion.certificate.json`, issus de `criterion --scheme joint`. Les données
restent celles téléchargées. Le complément vérifie le témoin existant et
recalcule les contraintes depuis les coordonnées rationnelles.

Le certificat polynomial fourni par défaut est **un exemple synthétique
contrôlé**, distinct du dossier Yahoo. Il sert à mesurer la garantie de
raffinement. Pour étudier ton propre certificat polynomial :

```powershell
python -u .\positionnement_litterature\positionner_apport.py `
  --criterion-run .\runs\critere_yahoo `
  --constructive-certificate .\runs\constructive_v012\constructive.certificate.json `
  --threads 4 --out .\runs\positionnement_mon_certificat
```

Le rapport distingue l’origine des données de chaque comparaison. Fournir
un certificat synthétique à côté d’un témoin Yahoo ne démontre pas la
construction polynomiale sur Yahoo. Les comparaisons de marché et celles
du contrôle ne sont pas agrégées en un classement.

## Résultats produits

| Fichier | Contenu |
| --- | --- |
| `rapport.md` | Positionnement, limites et résultats numériques interprétés |
| `matrice_litterature.md` | Propriétés documentées avec versions et localisateurs |
| `references.bib` | Bibliographie BibTeX |
| `claims.json` | Antériorités identifiées, apport candidat et points à examiner |
| `positionnement.json` | Résultats structurés, audits et provenance |
| `polynomial_level_*.witness.json` | Même polynôme échantillonné sur les raffinements |
| `nodal_level_*/joint.*.json` | Problèmes et preuves exactes du LP nodal comparatif |
| `kkt2016_slices.witness.json` | Prix et coefficients par échéance, si certifiés |
| `crw_adapted.witness.json` | Témoin du comparateur à objectif CRW et portée de son audit |
| `manifest.json` | Empreintes des fichiers stables du rapport |

Choisir un nouveau dossier de sortie à chaque recherche, ou omettre `--out`
pour obtenir automatiquement un nom horodaté. Les étapes et les résolutions
sont suivies dans le terminal. Les processus HiGHS sont fermés à la fin.

## Comparateurs réellement exécutés

1. **KKTG2016, par échéance, degré fixé.** Le code reprend l’objectif de
   moindres carrés (24) et les contraintes (18)–(23), dans les unités
   normalisées du projet. La sélection AIC n’est pas exécutée. La formulation
   par tranche n’impose ni calendrier commun, ni bid/ask durs, ni bornes locales.
   Une correction rationnelle d’arrondi est permise à hauteur de `1e-9` au
   plus en prix normalisé sur le domaine, et est enregistrée. L’optimalité
   exacte du QP n’est pas affirmée.
2. **Objectif CRW adapté à F0.** La formule à quatre fonctions affines (9),
   le choix de `delta0` (8) et l’épigraphe LP (10) sont repris. Le système
   d’arbitrage global du papier est remplacé par les contraintes de forme de
   notre fenêtre. Le comparateur conserve des bid/ask souples. Un statut
   numérique admissible et une reconstruction rationnelle échouée sont distingués.
3. **Ablation de Bernstein.** Même famille polynomiale, mêmes observations,
   même plancher de gamma ; retrait des deux inégalités locales et maintien
   du calendrier. Cette ablation n’est pas présentée comme un autre article.
4. **LP nodal du projet.** Même ensemble d’observations et mêmes bornes aux
   différents niveaux. Cette adaptation sur grille commune ne reproduit pas
   les opérateurs de transport complets de Buehler–Ryskin.

Les articles sont identifiés précisément dans `literature/registry.json`.
SANOS, Andreasen–Huge, SSVI, Fengler, Tikhonov et les modèles NN/GP ne sont
pas implémentés comme pricers dans ce complément. Le contrat d’import ci-dessous
permet d’auditer des sorties de leurs implémentations réelles sans les simuler
par une méthode différente portant leur nom.

## Vérification indépendante

```powershell
python -u .\positionnement_litterature\positionner_apport.py `
  --verify .\runs\positionnement_litterature
```

Cette commande vérifie les empreintes, le certificat polynomial, les prix
sur les grilles raffinées, les erreurs réelles, les bornes de raffinement,
les preuves nodales et les audits des comparateurs sauvegardés. Elle ne lance
ni téléchargement ni solveur. Elle ne réévalue pas la lecture humaine des articles.

`--skip-experiments` permet de générer uniquement l’audit bibliographique
et les vérifications des témoins fournis. `--levels 0,1,2,3` ajoute un
niveau ; `--max-nodes` limite la matérialisation, sans invalider le seuil théorique.

## Sources, découverte et accès

La revue ciblée est arrêtée au **26 octobre 2026**. Elle inclut 15 références
primaires et conserve les versions des prépublications. Le journal de recherche
et les critères de sélection figurent dans `literature/search_protocol.json`.
Il s’agit d’une revue ciblée par mécanismes, pas d’une revue systématique exhaustive.

`?` dans la matrice signifie **non évalué**. Le texte intégral du papier
KKT2024 reste notamment à examiner ; son résumé établit une antériorité de
construction de surfaces, sans permettre d’exclure un théorème équivalent.
La régularisation convergente, les bords globaux, les grilles mobiles et les
quotes souples sont comparés comme des hypothèses différentes.

Options réseau, facultatives :

```powershell
python -u .\positionnement_litterature\positionner_apport.py `
  --skip-experiments --fetch-sources `
  --crossref-query "Bernstein local volatility bounded calibration refinement" `
  --out .\runs\positionnement_sources
```

Les téléchargements sont hachés et les échecs d’accès enregistrés. Un
téléchargement réussi ne transforme pas automatiquement une annotation en
lecture intégrale. Les résultats Crossref restent des **candidats non évalués**.
Leur couverture ne remplace pas la recherche dans les prépublications et
la lecture des théorèmes.

## Importer une implémentation externe

Le fichier CSV doit contenir `time,x,price` sur **tous les nœuds exacts** du
problème de référence. Les axes ne sont pas interpolés ou arrondis silencieusement.
`exporter_surface.py` peut préserver les coordonnées du problème tout en
appelant ta fonction de prix :

```powershell
python .\positionnement_litterature\exporter_surface.py `
  --problem .\runs\critere_yahoo\criterion.problem.json `
  --pricer mon_modele_sanos:price --out .\runs\sanos_surface.csv

python -u .\positionnement_litterature\positionner_apport.py `
  --criterion-run .\runs\critere_yahoo `
  --external-surface "SANOS=.\runs\sanos_surface.csv" `
  --out .\runs\positionnement_avec_sanos
```

La fonction `price(T,x)` doit appartenir à ta véritable implémentation.
Le script ne fournit pas de faux pricer SANOS. Il audite les valeurs
exportées ; la provenance de l’implémentation et son temps d’entraînement
restent à documenter séparément. Les prix retournés en flottants sont
interprétés exactement comme les rationnels binary64 correspondants.

## Contrôles

```powershell
python -m pytest .\positionnement_litterature\tests -q
```

Le dossier `validation/` contient le résumé de l’exécution réellement
effectuée et les résultats de contrôle. Lire aussi
`docs/ALIGNEMENT_MATHEMATIQUE.md` pour les obligations de comparaison des énoncés.
