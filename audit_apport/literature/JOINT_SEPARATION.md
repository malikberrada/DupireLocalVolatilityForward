# Faisabilité séparée, intersection et raffinement temporel

Complément mathématique 0.3.0 — 27 octobre 2026.

Les lemmes portent sur le système fini du projet 0.1.6. Ils apportent des
preuves supplémentaires par rapport au premier exemple. Leur priorité
bibliographique n'est pas affirmée. Le point milieu, les différences finies,
les intersections d'intervalles et les séparateurs de Farkas sont classiques.

## 1. Compatibilité des deux contraintes locales

Dans une cellule, écrire d=c[j+1,i]-c[j,i], a=x_i^2*DeltaT/2>0,
g0=Gamma[j,i] et g1=Gamma[j+1,i], avec g0,g1>=0 et 0<=l<=u,
les mêmes bornes de **variance** pour les deux schémas.

**Lemme 1.** Les quatre contraintes locales sont équivalentes à

\[
a l\max(g_0,g_1)\le d\le a u\min(g_0,g_1).
\]

**Preuve.** Prendre le maximum des deux bornes inférieures et le minimum des
deux bornes supérieures. L'équivalence reste valable si un gamma est nul.
Si l>0 et les gammas sont positifs, l'existence d'un d admissible exige
max(g0,g1)/min(g0,g1)<=u/l. Cette condition sur les gammas ne suffit pas à
assurer que le d déjà fixé par un vecteur de prix est dans l'intervalle. □

Deux vecteurs différents, chacun admissible pour un schéma, ne fournissent
donc pas un témoin de l'intersection. La section 4 en donne un contre-exemple
dans le système exact du projet, avec spreads positifs et strikes irréguliers.

## 2. Seuil exact : trois strikes et voisins constants

Considérons x0<x1<x2, h-=x1-x0, h+=x2-x1,
kappa=2/(h-*h+)>0. Les prix aux deux strikes voisins restent constants.
Le gamma initial central est g0>0 ; son incrément de prix d détermine

\[
g_1=g_0-\kappa d.
\]

**Lemme 2.** Pour 0<l<u, une extrémité centrale libre peut satisfaire les
deux schémas sous les mêmes bornes si et seulement si

\[
\Delta T\le \frac{2(u-l)}{x_1^2\kappa l u}. \tag{T}
\]

Si la tranche initiale respecte F0, la construction ci-dessous conserve
aussi la forme. Une fourchette supplémentaire au centre final doit encore
être contrôlée : le lemme ne caractérise pas des observations arbitraires.

**Preuve.** Poser a=x1^2*DeltaT/2. Forward-lower impose d>=a*l*g0.
Backward-upper impose d<=a*u*(g0-kappa*d), soit
d<=a*u*g0/(1+a*u*kappa). Les deux autres bornes sont alors plus faibles
car 0<g1<=g0. Cet intervalle est non vide exactement lorsque
l*(1+a*u*kappa)<=u, soit (T).

Une construction utilise la moyenne harmonique v*=2*l*u/(l+u).
Avec z=kappa*x1^2*DeltaT*v*/4, poser

\[
\rho=\frac{1-z}{1+z},\qquad g_1=\rho g_0,\qquad
d=\frac{g_0-g_1}{\kappa}.
\]

Sous (T), z<1 et les variances discrètes sont

\[
v_f=\frac{v_*}{1+z},\qquad v_b=\frac{v_*}{1-z}\in[l,u].
\]

Le gamma final est positif. Le centre augmente mais reste sous la corde
des voisins. Les nouvelles pentes restent entre les deux pentes initiales,
donc dans [-1,0], en conservant leur ordre. Les bornes de prix et le raccord
convexe à (0,1) sont conservés. □

**Voisins variables.** Définir

\[
q=\frac{2}{h_-+h_+}
 \left(\frac{\Delta c_0}{h_-}+\frac{\Delta c_2}{h_+}\right).
\]

Alors g1=g0+q-kappa*d. Combiner forward-lower avec multiplicateur
1+a*kappa*u et backward-upper avec multiplicateur 1 donne

\[
a\{l(1+a\kappa u)-u\}g_0-a u q\le0. \tag{O}
\]

Un minimum strictement positif de ce membre gauche sur les fourchettes
prouve l'impossibilité de toute sélection conjointe. Des contraintes bid/ask
avec multiplicateurs positifs complètent alors un séparateur rationnel.
C'est cette version robuste aux spreads positifs qui est certifiée : tous
les prix voisins autorisés ne sont pas supposés constants.

## 3. Construction à tous les niveaux temporels ultérieurs

Fixer la durée totale D, les trois strikes et des prix voisins constants.
Subdiviser le temps en r parties. Appliquer la récurrence précédente avec
v* constant, z_r=kappa*x1^2*D*v*/(4r) et rho_r=(1-z_r)/(1+z_r).
Les gammas sont g_j=g0*rho_r^j.

**Lemme 3.** Les deux schémas sont admissibles dans chaque cellule dès que

\[
r\ge R_*:=\frac{\kappa x_1^2Dlu}{2(u-l)}.
\]

Pour la famille certifiée, lambda=kappa*x1^2*D*v*/2 appartient à (0,1).
Uniformément en r, l'incrément central final satisfait

\[
\frac{g_0}{\kappa}\frac{\lambda}{1+\lambda}
 \le c_r-c_0\le \frac{g_0}{\kappa}\lambda. \tag{I}
\]

**Preuve.** Le seuil est (T) pour chaque pas D/r. Comme 2*r*z_r=lambda,
les inégalités de Bernoulli donnent

\[
\rho_r^r\ge 1-\frac{2rz_r}{1+z_r}\ge 1-\lambda,
\qquad
\rho_r^{-r}=\left(1+\frac{2z_r}{1-z_r}\right)^r\ge 1+\lambda.
\]

Ainsi 1-lambda<=rho_r^r<=1/(1+lambda), d'où (I).
Les centres intermédiaires restent entre le centre initial et le plus
grand incrément final. La forme est conservée par le lemme 2.
Il suffit que la fourchette centrale finale contienne (I) et que les voisins
constants soient dans leurs fourchettes aux dates observées. Ces conditions
sont contrôlées exactement pour chaque candidat accepté. □

Ce résultat raffine **le temps seulement**, avec un témoin nodal à point
milieu. Il est distinct du théorème 2 de 0.1.6, de son polynôme continu et de
son raffinement espace-temps. Aucune application de ses hypothèses continues
au nouveau témoin nodal n'est revendiquée.

## 4. Instance certifiée

Dates : [1/4,7/20]. Strikes : [9/10,1,27/25].
Bornes de variance : l=3/100 et u=1/25.
Prix initiaux : [41/400,1/20,29/2500].

Les observations sont les prix initiaux ±1/1000000 aux trois strikes,
puis les mêmes fourchettes aux voisins à la seconde date et
[1/20+1/2000,1/20+11/10000] au centre. Les six largeurs sont strictement
positives. Aucun intervalle n'est retiré ou élargi entre les systèmes.

| Système | Incrément central / preuve |
| --- | --- |
| Forward seul | d=3/3500 ; variance forward 6/175, backward 3/50 hors borne |
| Backward seul | d=3/5000 ; variance backward 6/175, forward 3/125 hors borne |
| Intersection | Dual de 7 lignes ; écart 991/8000000>0 |
| Après une subdivision temporelle | Grille 3x3, mêmes six observations, primal conjoint exact |

Le dual combine forward-lower avec multiplicateur 3/2,
backward-upper avec multiplicateur 1 et cinq contraintes de cotations.
Il exclut **tout** vecteur dans les fourchettes, pas seulement les deux
témoins proposés.

Ici kappa=250, v*=6/175, lambda=3/7. Le seuil (T) vaut 1/15.
Le pas initial 1/10 est supérieur ; après subdivision, 1/20 est inférieur.
R*=3/2 ; le premier facteur dyadique admissible est 2.
Le témoin raffiné a z=3/28, rho=25/31 et incrément final 84/120125.

L'intervalle uniforme (I), [3/5000,3/3500], est inclus dans la fourchette
centrale [1/2000,11/10000]. La construction conserve donc les observations
à tous les niveaux temporels dyadiques ell>=1.

Le niveau dyadique minimal de faisabilité est établi pour cette instance :
ell=0 est impossible par le dual ; ell=1 est faisable par le primal.
La taille 2 dates x 3 strikes est minimale pour les stencils theta à deux
dates et gamma à trois strikes déclarés ici. Aucune minimalité dans d'autres
classes de modèles ou de certificats n'est revendiquée.

## 5. Interprétation scientifique

Ce résultat ajoute un élément auparavant manquant : des témoins séparés ne
remplacent pas le contrôle de l'intersection, même sur la plus petite grille
permettant ces stencils. Une subdivision temporelle rétablit la compatibilité
avec les mêmes cotations. Cela précise une contribution candidate.

Le registre compare notamment les passages sélectionnés de
[Buehler–Ryskin](https://quantitative-research.de/dl/Discrete%20Local%20Volatility%20-%20Extensive.pdf),
[Kundu–Kumar–Tomar](https://link.springer.com/article/10.1007/s10614-023-10368-5),
[Zhang 2025](https://arxiv.org/html/2511.09175v1) et
[Austing 2020](https://www.risk.net/media/download/1053071/download).
La recherche ciblée n'a pas établi la priorité de ces lemmes ou de cet exemple.
Leur caractère algébrique et leurs outils classiques doivent être pris en
compte dans l'évaluation de leur portée scientifique.

Le vérificateur indépendant reconstruit les inégalités et contrôle les
quatre preuves avec la bibliothèque standard Python. Il ne lit pas les
publications à la place du chercheur.

