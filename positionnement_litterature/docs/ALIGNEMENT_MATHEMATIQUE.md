# Aligner les énoncés avant de revendiquer un apport

Le résultat du projet porte sur un rectangle intérieur fini, des calls
normalisés, une grille cartésienne commune et un ensemble fixe de fourchettes.
La contribution doit être comparée sous ces hypothèses, et non à partir
du nom d’une famille de méthodes ou d’un succès numérique.

## 1. Décomposer la revendication

La transformation de contraintes de forme en inégalités sur des coefficients,
les bases de Bernstein, la programmation linéaire, la formule de Dupire et les
estimations de Taylor sont des outils antérieurs. La matrice bibliographique
identifie les versions et les localisateurs pertinents. Le certificat logiciel
ajoute une vérification exacte et reproductible de l’énoncé implémenté.

L’objet candidat à comparer est la chaîne complète :

\[
\text{fourchettes fixes}\ \longrightarrow\
\text{témoin polynomial rationnel}\ \longrightarrow\
(\gamma_0,M_3,M_4,M_{TT})\ \longrightarrow\
\text{seuil dyadique valable pour les deux stencils}.
\]

Le système fini de coefficients reste suffisant à degré fixé. L’échec de la
construction ne décide pas l’existence parmi toutes les surfaces possibles.
La présence d’une preuve correcte ne démontre pas à elle seule que cette
spécialisation n’est pas une conséquence immédiate de résultats connus.

## 2. Aligner les problèmes

Pour chaque résultat antérieur, vérifier séparément :

| Dimension | Question d’alignement |
| --- | --- |
| Inconnue | Prix nodaux, coefficients polynomiaux, densités, variance locale ou réseau ? |
| Domaine | Tranche en strike, rectangle intérieur ou domaine global avec queues ? |
| Observations | Intervalles durs, moindres carrés sur milieux ou pénalités de dépassement ? |
| Géométrie | Grille commune, grilles mobiles, interpolation ou opérateur de transport ? |
| Bornes | Variance implicite, locale continue ou locale discrète ; un ou deux stencils ? |
| Positivité | Gamma strictement positif certifié, gamma non négatif ou simple seuil numérique ? |
| Raffinement | Observations inchangées et mêmes bornes à tous les niveaux suivants ? |
| Preuve numérique | Résidus tolérés, intervalles certifiés ou arithmétique rationnelle exacte ? |

Un problème inverse régularisé et un problème de non-vacuité sous intervalles
durs ne répondent pas à la même question. Une tranche lisse n’établit pas
un calendrier admissible sur toutes les maturités. Une borne sur des variables
de transition n’est pas automatiquement une borne identique sur le quotient
du stencil étudié après lissage.

## 3. Identifier ce que mesure le seuil

Avec une marge intérieure `delta`, la borne du projet s’écrit

\[
e_r=\frac{D_hM_3}{3r}+\frac{H^2M_4}{12r^2},\qquad
|v_h-v|\le\frac{\tau M_{TT}/(r x_a^2)+v_{\max}e_r}{\gamma_0-e_r}.
\]

Elle conduit à `C*r^2-A*r-B>=0`. Ce critère certifie une famille de grilles
issue d’un même témoin ; il ne calcule pas le premier maillage faisable parmi
toutes les calibrations nodales. Le code mesure séparément :

- le premier niveau garanti par cette borne ;
- les niveaux où le même polynôme satisfait effectivement les stencils ;
- les niveaux où un LP nodal trouve un autre témoin admissible.

Sur le contrôle livré, les deux derniers tests passent déjà au niveau 0,
tandis que la borne garantit le niveau 2. L’expérience constate ainsi le
caractère conservateur de la borne. Elle ne démontre pas une amélioration
de précision ou de vitesse par rapport aux articles.

## 4. Portée des comparateurs

`kkt2016.py` implémente une formulation publiée par tranche à degré fixé.
Ses coefficients vérifiés donnent les contraintes de forme sur chaque tranche,
sans y ajouter silencieusement les contraintes du projet. La correction
rationnelle d’arrondi est bornée uniformément sur le domaine par la propriété
de partition de l’unité ; son budget et son effet sont enregistrés. Cette
correction n’est pas une preuve d’optimalité exacte des moindres carrés.

`experiments.py` reprend aussi un objectif publié de réparation. Les
contraintes sont explicitement adaptées à la fenêtre F0 du projet. Un
audit de cet objectif n’est pas la reproduction intégrale du modèle de
marché, du filtrage des données et des expériences du papier.

L’ablation polynomiale conserve toutes les fourchettes, les degrés et le
plancher de gamma, retire seulement les bornes locales et maintient le
calendrier. Si elle satisfait aussi les bornes sur le jeu testé, le rapport
l’indique. Aucun avantage empirique n’est alors attribué à leur imposition.

Un échec de reconstruction rationnelle d’un témoin numérique de comparaison
ne prouve ni l’infaisabilité de son problème, ni l’échec du résultat publié.
Les résidus numériques restent identifiés avec leur échelle.

## 5. Critère de clôture bibliographique

Le statut `not_determined_by_this_tool` exprime la portée de l’outil. Pour
fermer la question de l’originalité, il reste à confronter les énoncés complets
des travaux les plus proches à l’ensemble des obligations ci-dessus et à
vérifier la littérature d’approximation sous contraintes et d’analyse des
différences sur grilles irrégulières. Les textes intégraux non consultés sont
listés comme lacunes d’accès, jamais comme absences de résultats.

Le dossier sépare ainsi trois affirmations : une proposition mathématique
correcte dans sa classe ; un témoin logiciel exact sur des données déclarées ;
une éventuelle priorité scientifique. Les deux premières sont vérifiables
par calcul. La troisième nécessite l’analyse des sources complètes.
