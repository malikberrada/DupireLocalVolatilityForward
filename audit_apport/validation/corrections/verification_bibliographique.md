# Vérification des arguments bibliographiques — 27 octobre 2026

Les 18 comparaisons du cahier v052 disposant d’un texte source ont été réexaminées,
soit 162 lignes d’hypothèses. Les six PDF utilisés ont exactement les SHA-256
déclarés dans le cahier. Les corrections portent sur des **énoncés identifiés** et
des implications précises. Elles ne constituent pas une lecture déclarée par
l’utilisateur de tout le corpus, ni une certification de priorité.

## Corrections apportées au cahier

Les résumés des hypothèses et conclusions décrivent désormais les résultats des
auteurs cités. Plusieurs anciens champs recopiaient les conditions du projet
comme s’il s’agissait de conditions antérieures. Les 18 analyses ont été
réécrites de façon cohérente et les passages ont été rattachés à des résultats
nommés. Les décisions restent `pending` ; aucun nom de lecteur ni aucune lecture
intégrale ne sont inventés.

- **ZHANG2025_C3** : le lemme 2 de `JOINT_SEPARATION.md` appartient au projet.
  Il est supprimé des hypothèses prétendument attribuées à Zhang. Les arguments
  et citations sont remplacés par une comparaison au lemme S0.2 de Zhang.
- **C1** : `Cr²−Ar−B ≥ 0` est une condition suffisante sous les hypothèses
  certifiées du théorème 2. Son échec n’établit pas une infaisabilité. La nécessité
  et suffisance du seuil temporel de **C3**, dans sa classe restreinte, sont
  conservées.
- Les déclarations d’originalité fondées sur une formule absente, une notation
  différente ou un domaine différent sont retirées. Une hypothèse plus forte
  peut autoriser une spécialisation d’un résultat antérieur ; sa présence n’est
  donc pas une preuve de non-dérivabilité.
- Une borne de prix, de pente, de poids ou de coefficient de diffusion n’est
  plus assimilée sans identification à une borne de variance de deux stencils.

## Résultats effectivement confrontés

Les pages indiquées sont les pages physiques des PDF, comptées à partir de 1.
Les interprétations ci-dessous sont des analyses documentaires assistées, à
contrôler avant une déclaration de lecture.

| Travail et version examinée | Passages ciblés | Conséquence pour la comparaison |
|---|---|---|
| [Buehler–Ryskin, version extensive](https://quantitative-research.de/dl/Discrete%20Local%20Volatility%20-%20Extensive.pdf) | §2.2, pp.12–13 ; résultats 3.2–3.3, pp.17–18 ; §4.4, pp.33–34 | Les deux familles discrètes et les difficultés de non-vacuité sont antérieures. Le seuil de l’étape C3 se retrouve par la spécialisation calculée ci-dessous. Les petits pas de noyaux ne sont pas automatiquement la conservation des deux bornes de notre famille. |
| [SANOS, arXiv v4](https://arxiv.org/html/2601.11209v4) | Théorème 3.7 et proposition 3.8, p.17 | La reproduction discrète et le lissage conservant les fourchettes sous leurs hypothèses sont antérieurs. Leur rapport aux deux stencils du projet reste à démontrer. |
| [Chataigner–Crépey–Dixon, arXiv v1](https://arxiv.org/html/2007.10462v1) | §2–4, pp.3–6 ; §6, p.11 | Les garanties de forme de l’architecture hard sont distinguées des pénalités soft et de demi-variance. Ces dernières ne sont pas des contraintes dures uniformes sur tous les points. |
| [Zhang, arXiv v1](https://arxiv.org/html/2511.09175v1) | §3.2–3.4, pp.4–5 ; §7.1, p.13 | La positivité uniforme du dénominateur sur la grille et les erreurs de Dupire sont déjà étudiées. La norme, les opérateurs, A5 et le clipping doivent être comparés explicitement à C1. |
| [Carr–Nadtochiy, arXiv v2](https://arxiv.org/pdf/1308.2326v2) | Hypothèse 2, définition 14, remarque 15 et théorème 16, pp.27–30 | La calibration exacte de prix sélectionnés strictement admissibles est antérieure. Son coefficient LVG n’est pas identifié aux deux quotients discrets bruts du projet. |
| [Fengler–Hin, document de travail étiqueté mai 2013](https://ux-tauri.unisg.ch/RePEc/usg/econwp/EWP-1136.pdf) | Proposition 3.1, p.16 ; propositions 4.1–4.2, pp.19–20 ; corollaire 4.5, p.22 ; (33), p.31 | Les garanties de forme par coefficients et les taux statistiques sont distingués. Les bornes de prix et de pente ne sont pas des bornes de variance. La version du journal n’est pas réputée lue. |

Le papier [Kundu et al., 2016](https://link.springer.com/article/10.1186/s13660-016-1097-x),
§3.2–3.3, (18)–(25), PDF pp.6–8, a aussi été consulté comme contrôle
complémentaire : l’utilisation de coefficients de Bernstein pour des conditions
suffisantes de forme et un problème quadratique est antérieure. Ce composant ne
doit pas être revendiqué seul comme nouveau. Ses trois cases restent hors de la
correction du cahier initial, qui ne contient pas son PDF lié à une source.

## C3 : dérivation d’une composante à partir des contraintes BR

Il s’agit d’une **inférence algébrique à partir de (9)–(12), (18) et (21)**,
pas de l’affirmation que BR imprimerait déjà notre formule ou toute notre
construction de raffinement.

Fixons trois strikes, des voisins constants et un centre `x>0`. Posons

\[
\kappa=\frac{2}{h_-h_+},\qquad a=\frac{x^2\Delta T}{2},\qquad
d=c_1-c_0,\qquad g_1=g_0-\kappa d,\qquad g_0>0.
\]

Les coefficients de gamma de BR (9)–(10) donnent bien la même constante
`kappa`. Sur une grille commune, les deux incréments theta définis après (13) sont `d`.
En identifiant les variances `sigma_minus²=l` et `sigma_plus²=u`, `0<l<u`,
les contraintes forward/backward deviennent

\[
alg_0\le d\le aug_0,\qquad alg_1\le d\le aug_1.
\]

La première borne inférieure implique `d>0`, donc `g1<g0`. La borne inférieure
backward est alors moins forte et la borne supérieure backward est plus forte.
Les quatre contraintes équivalent à

\[
alg_0\le d\le\frac{aug_0}{1+au\kappa}.
\]

Cet intervalle est non vide si et seulement si

\[
l(1+au\kappa)\le u
\quad\Longleftrightarrow\quad
\Delta T\le\frac{2(u-l)}{x^2\kappa lu}.
\]

Pour la suffisance, prendre `d=alg0`. Le seuil implique
`a*kappa*l <= (u-l)/u < 1`, donc `g1>0` et les quatre contraintes sont
satisfaites. Des fourchettes imposées au centre terminal ajoutent leur propre
intersection. Cette dérivation identifie une composante antérieure de C3 ; elle
ne tranche pas la portée de la récurrence harmonique ni la conservation des mêmes
spreads à tous les niveaux. Le statut global BR/C3 est donc `component_only`.

## C1 et Zhang : un rapprochement réel, avec deux obstacles précis

Il est incorrect d’écrire que Zhang ne suppose pas de gamma éloigné de zéro :
le lemme S0.2 le suppose explicitement sur la grille. Il annonce aussi un
contrôle d’erreur du quotient Dupire en `L2(W)`, pour des opérateurs locaux et
un quotient clippé. Les ressemblances avec l’argument de consistance de C1 sont
donc substantielles.

**La borne L2 seule n’est pas une marge ponctuelle.** Dans un analogue discret
à poids `1/N`, une erreur `2*delta` en un seul nœud a une norme L2 égale à
`2*delta/sqrt(N)`, inférieure à `delta` pour `N>4`, alors que la borne ponctuelle
est violée. Une conversion uniforme nécessiterait des hypothèses ou constantes
supplémentaires, suivies sur les grilles raffinées. Cette observation ne suffit
pas, à elle seule, à exclure toute adaptation du lemme.

**A5 empêche une application littérale à toute la classe C1.** Considérons

\[
P(T,x)=\frac45-x+\frac{x^2}{4}\left(1+\frac{T}{50}\right),\qquad
(T,x)\in[1/4,7/20]\times[9/10,27/25].
\]

Prendre `v_min=19/1000`, `v_max=21/1000`, `delta=1/2000` et `gamma0=1/2`.
Les contrôles rationnels établissent les formes, le raccord, `P_xx>=gamma0`,
les bornes intérieures de variance et `M3=M4=Mtt=0`. La variance continue est
`1/(50+T)`, comprise entre `20/1007` et `4/201`. Des observations centrées sur
ce polynôme, avec une demi-fourchette positive, satisfont les contraintes de prix.

Le polynôme est affine en temps. Un ajustement quadratique exact sur trois temps
distincts a donc une courbure temporelle nulle. Avec cette enveloppe exacte,
l’inégalité temporelle A5 affichée par Zhang demande un pas strictement positif
inférieur ou égal à zéro. Elle ne peut être satisfaite. Ce cas bloque
l’identification directe `C=P` avec cette A5 pour toute la classe C1.

Il ne réfute ni le lemme S0.2 ni une autre dérivation possible de C1. La
consistance de différences finies peut être réétablie pour ce cas. Le statut
`not_a_direct_corollary` de Zhang/C1 est limité à **cette application littérale**,
et ne signifie ni indépendance logique ni originalité scientifique acquise.

## Traçabilité et limites de la vérification

Le script `rectifier_lectures.py` contrôle les octets des six PDF, cherche les
ancrages des énoncés dans l’index de la campagne fournie et reconstruit les IDs de
passages. Il n’utilise pas un simple remplacement du dernier numéro de ligne.
Les extractions locales de ces mêmes PDF diffèrent sur onze anciens IDs de blocs
du cahier initial ; ce constat ne prouve pas que l’index initial de l’utilisateur
était erroné. Le réancrage dans **sa propre campagne** évite de présumer l’identité
des découpages entre versions d’extracteur.

Le dossier conserve l’entrée originale, les SHA-256 des analyses avant/après,
les ancrages et l’index utilisés, les changements par champ et les deux arguments
mathématiques. La relecture du dossier vérifie ces liens ; avec `--campaign`, elle
revérifie aussi les PDF et les passages. Elle ne transforme pas une interprétation
bibliographique en théorème automatiquement vérifié.

Les **19 comparaisons non renseignées** du cahier initial restent inchangées.
Le texte principal KKT2024, la thèse de Kundu et plusieurs autres textes restent
à examiner ou à rattacher à la campagne. Les analyses ciblées ne constituent pas
une exclusion du contenu entier des six articles examinés. La date et
l’identifiant d’une version publique du projet restent à fournir pour l’argument
de priorité. Le mois imprimé sur un document de travail ne vaut pas, à lui seul,
preuve de sa date de diffusion publique.

L’apport potentiel doit donc être discuté au niveau du témoin commun, des
contraintes exactes, de la certification et de la construction de raffinement.
Les composants déjà identifiés et la dérivation du seuil C3 doivent être crédités.
La recherche de dérivations classiques ou d’antécédents supplémentaires reste
ouverte ; `scientific_priority_certified` demeure `false`.
