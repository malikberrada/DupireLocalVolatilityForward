> Intégration dans le dépôt : installer depuis la racine selon [le README principal](../README.md). Le parcours autonome testé est `scripts/reproduce.py --profile core`. Les commandes historiques ci-dessous qui nomment une campagne personnelle nécessitent les fichiers de cette campagne ; ils ne sont pas recréés par une lecture automatique.

# Audit et corrections bibliographiques — 0.5.3

Cette version corrige les **18 analyses / 162 lignes d’hypothèses** du cahier
v052 fourni. Elle réécrit les attributions, distingue la condition suffisante
C1 du seuil exact C3 et retire les déclarations d’originalité non démontrées.
Les six PDF sources ont été confrontés à des énoncés nommés et leurs empreintes
correspondent à celles du cahier. Aucun modèle local n’est nécessaire pour
appliquer ces corrections.

Deux arguments supplémentaires sont fournis :

- le seuil temporel de l’étape C3 se déduit algébriquement des contraintes
  (18),(21) de Buehler–Ryskin dans la classe restreinte ; le reste de la
  construction n’est pas réputé antérieur sur cette seule base ;
- un polynôme affine en temps satisfait les hypothèses continues C1 et bloque
  l’identification littérale à l’hypothèse A5 affichée dans Zhang. Cela ne réfute
  ni son lemme ni une autre dérivation de C1.

Le rapport détaillé se trouve dans
[bibliography/verification_v053.md](bibliography/verification_v053.md).
Le cahier déjà corrigé est livré dans
`validation/corrections/lectures_corrigees.json`. Il reste en attente d’une
déclaration de lecture ; les 19 cases non renseignées sont conservées.

Pour refaire la correction dans **ta propre campagne**, ce qui rattache les
passages à son découpage exact, extraire le dossier `audit_apport` à la racine
puis exécuter :

```powershell
python -u .\audit_apport\rectifier_lectures.py `
  --workbook .\runs\analyses_bibliographiques_v052\lectures_a_valider.json `
  --campaign .\runs\lectures_bibliographiques_v050 `
  --out .\runs\lectures_rectifiees_v053

python -u .\audit_apport\rectifier_lectures.py `
  --verify .\runs\lectures_rectifiees_v053 `
  --campaign .\runs\lectures_bibliographiques_v050
```

Le script vérifie les six sources, retrouve les titres d’énoncés sur leurs pages,
reconstruit les IDs dans l’index de la campagne et journalise les changements.
Il refuse de remplacer une analyse déjà modifiée ou acceptée. Il écrit dans un
nouveau dossier et préserve les anciens dossiers scellés. La vérification sans
`--campaign` contrôle le dossier conservé, sans prétendre relire les PDF absents.

Le contrôle arithmétique des deux arguments est autonome :

```powershell
python -I -S .\audit_apport\verifier_arguments.py
```

Les anciens brouillons du modèle peuvent encore être repris avec `--resume`.
Le prompt et le diagnostic ont été complétés pour signaler les erreurs de rôle,
les déclarations d’originalité et la confusion nécessité/suffisance C1. Ces
signaux restent des invitations à vérifier, pas une certification sémantique.
La sélection reconnaît aussi les localisateurs français et les identifiants
alphanumériques tels que `S0.2`. Le registre par défaut reprend les 18 analyses
révisées, avec leur attribution explicite à une lecture assistée ciblée.

## Parcours de lecture 0.5 conservé

La version 0.5 ajoute **`completer_lectures.py`** : récupération des textes publics,
extraction par page/ligne, 37 tâches d’analyse, brouillons facultatifs via Ollama
local, déclarations du lecteur et export vers l’audit bibliographique existant.

Le guide complet, avec les commandes Windows, est dans **[LECTURES.md](LECTURES.md)**.
Il reprend directement ton dossier `runs/priorite_bibliographique_v040`.
Installer l’extracteur PDF puis préparer les lectures :

```powershell
python -m pip install -r .\audit_apport\requirements_lectures.txt
python -u .\audit_apport\completer_lectures.py preparer `
  --priority-dir .\runs\priorite_bibliographique_v040 `
  --telecharger --decouvrir `
  --out .\runs\lectures_bibliographiques_v050
```

Le téléchargement conserve ses échecs ; les textes manquants peuvent être joints
par `--source WORK_ID=chemin.pdf`. Un résumé, un CV ou une réponse HTTP 200 ne
certifient pas l’accès à un article entier. Les brouillons du modèle restent
en attente de lecture et de contrôle. Les audits 0.2, 0.3 et 0.4 sont conservés.

## Dossier bibliographique 0.4 conservé

La version 0.4 ajoute un **dossier bibliographique daté et vérifiable** :
13 travaux, 3 revendications séparées, 37 comparaisons annotées, 7 captures de
métadonnées Crossref et un journal des recherches réellement exécutées.
Elle conserve les certificats mathématiques et les 128 comparaisons d’hypothèses
de la version précédente.

Après extraction à la racine du projet, réutiliser ton audit 0.3 déjà calculé :

```powershell
python -u .\audit_apport\priorite_bibliographique.py `
  --audit-dir .\runs\audit_apport_v030 `
  --out .\runs\priorite_bibliographique_v040

python -u .\audit_apport\priorite_bibliographique.py `
  --verify .\runs\priorite_bibliographique_v040
```

La première commande copie et revérifie l’audit existant, sans nouvelle collecte
Yahoo ni solveur. La seconde recalcule la chronologie, les liens aux sources et
les conclusions hors ligne. Sans `--audit-dir`, le dossier bibliographique peut
être produit avec la seule bibliothèque standard Python ; les preuves sont alors
signalées comme non fournies. Ne pas mettre `--out` à l’intérieur de l’audit source.

**Les nouveaux éléments sont des éléments de preuve, pas une priorité acquise.**
La lecture ciblée du PDF Carr–Nadtochiy et du document de travail Fengler–Hin
ajoute des comparaisons de résultats nommés. Le registre corrige les dates de
première diffusion et sépare la date du travail de celle du texte effectivement
lu. Les résumés récents de Yoo et al. et Nam et al. sont ajoutés avec leur portée
limitée. Les PDF complets de tiers ne sont pas redistribués ; leurs URLs et
empreintes figurent dans `bibliography/registry.json`.

Les trois revendications suivies sont :

- **C1** : condition suffisante quantifiée de raffinement, observations conservées ;
- **C2** : exemple rationnel de faisabilités séparées avec intersection vide ;
- **C3** : seuil temporel exact dans la classe à trois strikes et voisins constants.

Le rapport `rapport_priorite.md` expose les passages comparés, les hypothèses,
les conclusions, l’analyse de spécialisation directe et les lacunes par revendication.
`priority.json` en donne la version exploitable par programme.

### Compléter le dossier après lecture

Le texte principal KKT2024, la thèse de Kundu et plusieurs textes récents restent
à examiner. La date et l’identifiant d’une **version publique du projet** n’ont pas
été fournis. Ces manques ne sont pas remplacés par des empreintes locales.

1. Copier `bibliography/review.template.json`, renseigner le lecteur, la date,
   les pages, les hypothèses, la conclusion, la version et le SHA-256 exact du texte lu.
   Renseigner `relation` et `derivability` après analyse. Le modèle incomplet est refusé.
2. Joindre le même texte par `--source WORK_ID=chemin`. Une pièce jointe seule
   ne change jamais une lecture ciblée en lecture de l’article entier.
3. Si une version publique datée du projet existe déjà, compléter
   `bibliography/project_record.template.json` et joindre cette version par
   `--source PROJECT=chemin`. Localiser C1, C2 et C3 séparément ; n’inclure que les
   revendications effectivement présentes dans la version datée.

```powershell
python -u .\audit_apport\priorite_bibliographique.py `
  --audit-dir .\runs\audit_apport_v030 `
  --reviews .\mes_lectures.json `
  --source 'KKT2024=C:\Articles\KKT2024.pdf' `
  --project-record .\depot_public_projet.json `
  --source 'PROJECT=C:\Articles\version_publique_projet.pdf' `
  --out .\runs\priorite_bibliographique_completee
```

Valeurs de `relation` : `component_prior`, `different_statement`,
`equivalent_or_stronger`, `unresolved`. Valeurs de `derivability` :
`component_only`, `not_a_direct_corollary`, `direct_specialization`, `unresolved`.
La portée `full_work` déclare une analyse du texte entier ; `selected_statement`
reste limitée aux passages cités. Le programme contrôle la cohérence et les
liaisons aux octets, pas la vérité de cette interprétation.

Si la version lue n’est pas datée dans le registre, fournir avec `--registry`
une copie complétée de `bibliography/registry.json` et conserver le dossier
`snapshots` voisin. Ajouter un événement public sourcé **pour cette version exacte** ;
ne pas dater un PDF auteur actuel par le premier dépôt d’un autre fichier.
Les événements arXiv/SSRN sont des annotations sourcées à revoir explicitement.

Le statut `priority_argument_documented_in_declared_corpus` exige les lectures,
les sources exactes, une datation de la version comparée et l’analyse de
dérivabilité pour tous les travaux requis, ainsi qu’une version publique localisant
la revendication. Il reste un argument **limité au corpus déclaré**.
`scientific_priority_certified` reste `false` : aucune recherche sans résultat
ne démontre l’absence universelle d’antécédent. Les cas positifs des tests sont
des données synthétiques explicitement désignées comme telles.

### Actualiser les métadonnées

```powershell
python -u .\audit_apport\priorite_bibliographique.py `
  --refresh-metadata --out .\runs\priorite_bibliographique_actualisee
```

Seule cette option contacte Crossref. Les champs `created`, `indexed` et
`deposited` ne servent jamais de dates de publication. Les dates au mois ou à
l’année gardent leur précision. En cas d’échec réseau, la capture antérieure
est conservée et l’échec apparaît dans `refresh_log.json`. Une actualisation ne
change pas le statut de lecture des sources. L’arrêté bibliographique reste
celui du registre, par défaut le 27 octobre 2026 ; les événements postérieurs
ne deviennent pas des antécédents à cette date.

Un exemple complet des deux audits et leurs vérifications est inclus dans
`validation`. Les audits 0.2 et 0.3 existants restent relisibles.

## Certificats mathématiques et traçabilité conservés

L’extension mathématique de la version 0.3 ajoute un exemple exact où **forward et backward sont chacun
faisables, mais leur intersection est vide**, puis une subdivision temporelle
qui rétablit la faisabilité conjointe avec les mêmes six fourchettes. Elle ajoute
un seuil de compatibilité dans une classe à trois strikes, sa preuve et un
vérificateur indépendant. Ces nouveaux éléments étayent la contribution proposée ;
ils ne constituent pas une preuve automatique de priorité bibliographique.

## Produire les nouveaux éléments sans recommencer Yahoo

```powershell
python -u .\audit_apport\auditer_apport.py --evidence-only --out .\runs\audit_apport_v040
python -u .\audit_apport\auditer_apport.py --verify .\runs\audit_apport_v040
python -u .\audit_apport\verifier_joint_independant.py .\runs\audit_apport_v040\joint_discriminant
```

La troisième commande ne nécessite que la bibliothèque standard Python.
Les deux premières utilisent toujours `dupire-joint 0.1.6`. Le code conserve
la relecture des dossiers 0.2.0 déjà créés.

À extraire **dans le dossier du projet** : le sous-dossier `audit_apport` est ajouté.
Le collecteur et les sources existantes ne sont pas remplacés. Python >=3.10,
avec le paquet **dupire-joint 0.1.6** de ton projet. Windows : `tzdata` doit être disponible.

## Exécuter sur tes fichiers déjà téléchargés

Dans `.venv312`, depuis le dossier de ton projet :

```powershell
python -u .\audit_apport\auditer_apport.py `
  --criterion-run .\runs\critere_yahoo `
  --accepted-dir .\runs\yahoo_valide_20261026T203526_495751Z\collecte\accepted `
  --out .\runs\audit_apport_v040
```

Le dossier `--accepted-dir` doit contenir les vrais fichiers originaux :
`raw_snapshot.json`, `snapshot.json`, `selection.json`, `curves_estimees.csv`,
`curves_estimees.csv.uncertainty.json`, `F0.exact_grid.json`. Les fichiers
`criterion.problem.json` et `criterion.certificate.json` viennent de `--criterion-run`.
Le chemin `--logical-grid` est optionnel : par défaut la grille est lue dans le dossier accepté.
Une entrée manquante ou incohérente provoque une erreur explicite ; aucune provenance complète n’est inventée.

Depuis la racine, installer le moteur source et les dépendances verrouillées :

```powershell
python -m pip install -r requirements-lock.txt
python -m pip install --no-build-isolation --no-deps -e .
```

La commande ne télécharge **aucune nouvelle chaîne Yahoo**. Elle vérifie :

1. la sélection v0.2.0, rejouée depuis toutes les lignes brutes ;
2. le certificat des courbes nominales, recalculé par intersection rationnelle de parité ;
3. les calls et puts normalisés, avec leurs bid/ask inchangés ;
4. le hash du fichier source, les axes et les 121 contraintes observées du certificat joint ;
5. le témoin rationnel, puis toutes les contraintes recalculées directement.

Le contrôle de provenance ne certifie pas l’authenticité de Yahoo, les temps bid/ask,
la robustesse aux courbes incertaines, ni le choix de la sélection avant observation des prix.
La sélection initiale au pas de 50 demeure une restriction des observations.

## Exemple complet inclus

```powershell
python -u .\audit_apport\auditer_apport.py --demo --out .\runs\audit_apport_demo
```

L’archive brute est ton ancien `attempt_03`. Sa grille exacte et son certificat joint
sont ceux du projet 0.1.6. Les fichiers de sélection et de courbes du **demo** ont été
reconstruits rétrospectivement depuis cette archive ; ils retrouvent exactement la grille
originale. `REPLAY_ORIGIN.json` l’indique. Ce n’est pas une nouvelle observation de marché.

## Relecture sans solveur ni réseau

```powershell
python -u .\audit_apport\auditer_apport.py --verify .\runs\audit_apport_v040
```

Les fichiers d’entrée sont copiés octet pour octet dans le dossier d’audit. La relecture
recalcule la normalisation, les preuves et les liens de chaque observation ; elle ne se
limite pas aux hash. Le dossier de sortie doit être nouveau à chaque exécution.

## Comparer les hypothèses des énoncés

`literature/theoremes.json` contient **16 axes et 8 résultats/formulations**, avec des
relations explicites, versions, localisateurs et sources primaires :
Buehler–Ryskin résultats 3.2–3.3 ; Kundu et al. (2016), (18)–(25) ;
Kundu–Kumar–Tomar (2024), résumé et annexe technique publique ; SANOS proposition 3.8 et théorème 3.7 ;
Chataigner–Crépey–Dixon, comparaison méthodologique ; Zhang (2025), lemme S0.2 ;
Austing (2020), reproduction exacte de prix. Les deux axes supplémentaires portent
sur les nouveaux lemmes ; ils ne sont pas des hypothèses du théorème 2.

Le résultat généré `literature/matrice_hypotheses.md` compare chaque axe à l’hypothèse
du théorème 2 du projet. Les annotations résultent de lectures et d’inférences de portée
signalées ; le programme ne démontre pas automatiquement l’équivalence d’articles.
Le texte principal KKT2024 reste **non évalué**, son annexe publique est comparée.
La thèse de Kundu (2017) reste également à consulter. Aucune priorité scientifique n’est attribuée.

Pour joindre un PDF obtenu légitimement et conserver son empreinte :

```powershell
python -u .\audit_apport\auditer_apport.py --demo `
  --source 'KKT2024=C:\Articles\KKT2024.pdf' `
  --out .\runs\audit_avec_source
```

Joindre un document ne change pas son statut de lecture. `a_completer_KKT2024.json`
donne les axes à documenter. Après lecture, tu peux modifier une **copie** du registre,
avec pages et équations précises, et la fournir par `--comparisons chemin\theoremes.json`.
Pour faire passer KKT2024 à `full_text_sections_reviewed`, ajouter au résultat
`full_text_review` avec `reviewer`, `review_date` et `source_sha256` (SHA-256 du fichier lu),
puis joindre ce même fichier par `--source KKT2024=...`. Cette liaison documente la lecture
déclarée ; elle ne vérifie pas automatiquement son interprétation.
La validation structurale conserve la distinction entre preuve vérifiée, annotation
sémantique et résultat encore inconnu.

## Recherche de l’exemple discriminant

La recherche parcourt un catalogue déclaré de polynômes rationnels sur
`T in [1/4,5/4]`, avec l’axe spatial irrégulier `[9/10,1,27/25]`.
Pour chaque candidat, les six observations initiales ont des spreads strictement positifs.
Elles restent **identiques** à chaque niveau : les nouveaux nœuds sont des inconnues,
pas de nouvelles observations.

La première famille sélectionnée utilise :

\[
P(T,x)=\frac45-x+\frac{x^2}{4}\left(1+\frac{T-1/4}{50}\right)^2.
\]

Les bornes de **variance** sont `391/10000` et `803/20000`, soit approximativement
des volatilités de 19,77 % à 20,04 %. Ces paramètres synthétiques ne modifient pas Yahoo.
Les preuves produites sont :

- F0 faisable sur 2 dates × 3 strikes ;
- mêmes observations avec contraintes locales conjointes : infaisabilité rationnelle ;
- raffinement dyadique de niveau 2 : faisabilité commune sur 5 × 9, mêmes observations ;
- polynôme de Bernstein vérifié sur tout le rectangle, avec garantie théorique à partir du niveau 6.

Le séparateur négatif combine une inégalité locale et les contraintes de fourchettes.
Un résultat numérique défavorable n’est jamais une preuve d’impossibilité.
L’échec du polynôme à un niveau intermédiaire ne prouve pas l’échec de tous les LP à ce niveau.
L’outil cherche des témoins dans une famille finie : aucun cas trouvé ne veut pas dire aucun cas existant.
`--max-candidates 1..3` et `--max-level 0..6` règlent ce budget.

Cet exemple établit un effet de discrétisation dans notre formulation. Il ne revendique
ni nouveauté de cet effet, ni reproduction complète de BR/SANOS, ni supériorité expérimentale.
Les preuves du théorème utilisé figurent dans `literature/CRITERE_PROUVE_0.1.6.md`.

## Nouvel exemple : faisabilité séparée et intersection vide

Le dossier `joint_discriminant` contient quatre preuves : forward seul faisable,
backward seul faisable, intersection impossible, puis intersection faisable après
subdivision du temps. La grille passe de **2x3 à 3x3** ; les strikes irréguliers,
les six fourchettes et les bornes de variance **[3/100,1/25]** sont conservés.
Le séparateur combine les deux familles locales et a un écart exact de
**991/8000000**. Le premier niveau dyadique faisable est prouvé égal à 1.

`literature/JOINT_SEPARATION.md` démontre l’obstruction et le seuil de pas 1/15
dans la classe à voisins constants. La construction à point milieu reste dans
les mêmes observations à tous les niveaux temporels ultérieurs au seuil.
Ce résultat est distinct du raffinement espace-temps du polynôme précédent.

`--joint-max-level 0..6` et `--joint-candidates 1..3` limitent la recherche déclarée.
Un budget temporel nul conserve les trois preuves de séparation mais ne
matérialise pas le quatrième certificat de raffinement.

## Sorties

- `rapport.md`, `audit.json` : conclusions et limites ;
- `literature/matrice_hypotheses.md` : 128 comparaisons et points à compléter ;
- `claims.json` : nouvelles revendications reliées aux preuves et aux limites bibliographiques ;
- `joint_discriminant/*.problem.json`, `*.certificate.json` : quatre nouvelles preuves ;
- `joint_discriminant/theory.json` : seuil temporel et bornes uniformes préservant les fourchettes ;
- `yahoo/lineage.json`, `yahoo/observation_links.json` : provenance par contrat ;
- `discriminant/*.problem.json`, `*.certificate.json` : trois preuves rationnelles ;
- `discriminant/polynomial.json`, `search_protocol.json` : construction, marge et borne de raffinement ;
- `manifest.json` : empreintes des fichiers sauvegardés.

Tests : `python -m pytest .\audit_apport\tests -q`.

Un dossier d’audit déjà exécuté est livré dans `validation/demo`. Pour le relire :

```powershell
python -u .\audit_apport\auditer_apport.py --verify .\audit_apport\validation\demo
```
