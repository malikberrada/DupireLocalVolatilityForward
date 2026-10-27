# Discrete Dupire: feasibility and reproducible certificates

**Dépôt de recherche d’Abdelmalik Berrada.** Calibration sur une grille irrégulière sous fourchettes bid/ask, contraintes de non-arbitrage et bornes de variance locale discrète. Le critère `joint` impose **une même surface** aux schémas forward et backward.

Ce dépôt contient le moteur Python 0.1.6, les données Yahoo originales du **26 octobre 2026**, le téléchargement des données, leur traitement et la reproduction des résultats. HiGHS fournit le solveur C++ par `pip` ; aucun CMake n’est nécessaire. CUDA est facultatif et ne remplace pas le solveur LP CPU. L’environnement CPU de référence ne nécessite ni PyTorch ni CuPy.

## Démarrage sous Windows / PowerShell

Depuis la racine du dépôt, avec Python **3.12** installé :

```powershell
py -3.12 -m venv .venv312
$PyDupire = (Resolve-Path .\.venv312\Scripts\python.exe).Path
& $PyDupire -m pip install -r requirements-lock.txt
& $PyDupire -m pip install --no-build-isolation --no-deps -e .
& $PyDupire scripts/download_data.py frozen
& $PyDupire scripts/reproduce.py --profile core --out runs/reproduction
```

Chaque commande doit terminer avec un code de sortie nul. Le lanceur complet, qui arrête au premier échec, est également disponible :

```powershell
.\scripts\bootstrap.ps1
```

Le chemin explicite de `.venv312` évite de lancer accidentellement le Python d’Anaconda. Ne réutilise pas un dossier de sortie contenant une ancienne exécution.

## Linux / macOS

```bash
python3.12 -m venv .venv312
.venv312/bin/python -m pip install -r requirements-lock.txt
.venv312/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv312/bin/python scripts/download_data.py frozen
.venv312/bin/python scripts/reproduce.py --profile core --out runs/reproduction
```

Le verrou de dépendances cible Python 3.12. Les tests exécutés lors de la préparation sont consignés dans [VALIDATION.md](VALIDATION.md).

## Téléchargement des données utilisées

Les quatre chaînes brutes sont dans `data/raw/yahoo/2026-10-26/`. `data/manifest.json` contient leurs SHA-256, tailles, heures de collecte, échéances et provenance. Elles arrivent avec `git clone` ou l’archive du dépôt. La commande `frozen` contrôle les octets puis prépare une copie dans `data/downloaded/` : elle fonctionne sans réseau.

Pour **télécharger ces mêmes fichiers depuis GitHub**, une fois ce dépôt publié puis cloné :

```powershell
& $PyDupire scripts/download_data.py frozen --source github
```

Le script déduit `origin` et le SHA complet de `HEAD`. Il télécharge les fichiers sur `raw.githubusercontent.com` à ce commit et refuse toute différence de taille ou d’empreinte. Les arguments `--repo OWNER/REPO --ref SHA_COMPLET` permettent de choisir explicitement un dépôt et un commit. Aucun nom de dépôt distant fictif n’est configuré.

Yahoo fournit des chaînes courantes : **un nouvel appel Yahoo ne restitue pas les anciens bid/ask**. Les données figées assurent la reproduction historique ; le mode suivant crée une nouvelle observation :

```powershell
& $PyDupire scripts/download_data.py live --symbol '^SPX' --root SPXW --out runs/nouvelle_collecte
```

La collecte conserve tous les livres reçus, fixe la grille avant lecture des prix et effectue les contrôles de parité/F0. Elle peut échouer si la séance est fermée, le fournisseur est indisponible ou les livres sont incompatibles. Les tentatives restent enregistrées. Pour une **nouvelle collecte suivie de la validation des deux schémas** :

```powershell
& $PyDupire -u valider_yahoo.py --symbol '^SPX' --root SPXW --threads 4 --out runs/nouveau_marche
```

Détails : [données et provenance](docs/DATA.md), [protocole de reproduction](docs/REPRODUCIBILITY.md).

## Résultats contrôlés

| Parcours | Résultat de référence |
|---|---|
| Yahoo `attempt_03` → courbes → grille | 5 échéances, 59 calls, 62 puts, 121 observations, 375 nœuds |
| Critère conjoint Yahoo, bornes de volatilité 5 %–100 % | Un témoin rationnel commun satisfait les deux schémas |
| Exemple rationnel de séparation | Forward et backward séparément faisables ; intersection grossière vide ; intersection raffinée faisable avec les mêmes fourchettes |
| Conservation du prix terminal grossier vs raffinement conjoint | Écart strict `1153/128000000` |
| Nouveau certificat dual | 10 termes ; marge `4739/384000000` |
| C1 constructif | Certificat polynomial, borne suffisante de raffinement et vérification exacte |

`--profile core` reconstruit les preuves, vérifie puis recalcule le témoin constructif, rejoue `attempt_03`, résout le critère conjoint, reconstruit la traçabilité et revérifie les preuves de l’étude archivée. Il produit `summary.json`, `environment.json`, les commandes, les journaux et les empreintes des sorties.

```powershell
# Les quatre instantanés et les 12 cas d’étude recalculés : plus long
& $PyDupire scripts/reproduce.py --profile all --out runs/reproduction_complete

# Preuves rationnelles uniquement : bibliothèque standard, sans installation pip
& $PyDupire -I -S analyse_dependances/generer_dependances.py --out runs/preuves
& $PyDupire -I -S runs/preuves/verifier_dependances.py --verify-json runs/preuves/preuves_dependances.json

# Tests du moteur, du collecteur, des téléchargements et des audits
& $PyDupire -m pytest -q
```

Les originaux et les nouvelles sorties restent distincts. Les temps, les bases LP et les témoins optimaux ne sont pas garantis identiques octet par octet ; les contraintes, empreintes d’entrée et conclusions précises sont contrôlées. Les résultats numériques `indeterminate` de l’étude archivée restent explicitement tels quels.

## Organisation

| Chemin | Contenu |
|---|---|
| `src/dupire_joint/` | Une seule version du moteur : 0.1.6 |
| `collect_coherent_yahoo.py`, `valider_yahoo.py` | Collecte/traitement et validation avec processus bornés |
| `scripts/` | Téléchargement, reproduction, vérification et installation Windows |
| `data/` | Données brutes figées et manifestes de provenance |
| `reference/` | Résultats, observations et certificats d’origine |
| `analyse_dependances/` | Générateur des preuves et nouveau dual exact, note PDF/LaTeX |
| `audit_apport/` | Audit des arguments et exemples rationnels ; annotations bibliographiques |
| `positionnement_litterature/` | Comparaisons et export de surfaces |
| `tests/`, `.github/workflows/` | Vérifications automatiques et CI Ubuntu/Windows |

## Portée scientifique

C1 est une condition **suffisante**, conditionnelle à un témoin polynomial certifié. La faisabilité individuelle des deux schémas n’implique pas leur faisabilité conjointe. Les garanties Yahoo concernent la grille retenue et la normalisation nominale ; elles ne certifient ni toute la chaîne brute, ni la synchronisation des bid/ask, ni une extension continue.

Les contrôles rationnels vérifient les identités et certificats décrits, pas des preuves générales dans un assistant formel. Le dossier de dépendances documente des dérivations classiques et une séparation ciblée ; il ne certifie pas la priorité bibliographique générale. Les 18 lectures corrigées sont conservées dans `reference/readings/` avec leur statut de validation. Les PDF tiers peuvent être téléchargés avec `scripts/download_data.py papers` et leurs empreintes sont contrôlées ; leur disponibilité future n’est pas garantie.

## CUDA et publication GitHub

La reproduction principale utilise le CPU. Pour CUDA, installe une version de PyTorch compatible avec ta machine puis utilise `--device cuda`. Cette option concerne la génération/évaluation des surfaces ; les LP restent résolus par HiGHS sur CPU.

Le dépôt ne contient ni environnement virtuel, ni roue vendue, ni sauvegardes de correctifs. Pour créer un **nouveau dépôt privé** avec Git et GitHub CLI, après validation locale et authentification `gh` :

```powershell
git init -b main
git add .
git commit -m 'Add reproducible discrete Dupire research pipeline'
gh repo create dupire-local-volatility --private --source . --remote origin --push
```

Remplace `--private` par `--public` si tu souhaites une publication publique. Le code est sous [licence MIT](LICENSE). Les données et articles tiers conservent les conditions de leurs fournisseurs, décrites dans [DATA.md](docs/DATA.md).
