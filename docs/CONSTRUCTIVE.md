# Condition suffisante constructive et raffinement certifié

Introduit en 0.1.2, actualisé en 0.1.6. Voir aussi
[CRITERE_PROUVE.md](CRITERE_PROUVE.md), qui réunit l'alternative exacte et
le critère constructif avec un seuil quadratique explicite. Périmètre : calls européens normalisés, grille
commune de strikes, fenêtre intérieure finie, bornes constantes de variance
locale. Cette proposition est une condition suffisante conservative. Elle ne
caractérise pas toutes les données calibrables et ne revendique pas une
résolution générale de la question ouverte de Buehler–Ryskin.

## 1. Données et inconnues finies

Les seules données financières sont les observations
`(T_k, x_k, bid_k, ask_k)`, en unités de call normalisé. On utilise la fenêtre

\[
R=[T_a,T_b]\times[x_a,x_b],\qquad T_a>0,\quad x_a>0,
\]

définie par les extrema des coordonnées observées. On prend l'union des
strikes et des échéances ; les nœuds non cotés ne deviennent pas des
observations. S'il n'y a que deux strikes distincts, on ajoute leur milieu au
maillage de base. Il faut au moins deux échéances distinctes.

On prescrit `0 <= v_min < v_max`, une marge de **variance**
`0 < delta < (v_max-v_min)/2` et un plancher de convexité `g>0`.
Les options `--sigma-min` et `--sigma-max` sont des volatilités. Depuis
0.1.6, `construct` interprète ces paramètres décimaux/rationnels exactement
avant de les élever au carré. `--variance-buffer` est directement en unités
de variance ; cette marge et `--gamma-floor` sont aussi lus exactement.
Les observations de ce chemin restent les valeurs binary64 exactes du CSV.

Pour des degrés choisis `m>=1`, `n>=2`, les inconnues sont uniquement les
`(m+1)(n+1)` nombres rationnels `a_pq`. Ils définissent, après calcul,

\[
P_a(T,x)=\sum_{p=0}^m\sum_{q=0}^n a_{pq}B_p^m(u)B_q^n(w),\qquad
u={T-T_a\over T_b-T_a},\quad w={x-x_a\over x_b-x_a}.
\]

Il n'y a aucune surface admissible fournie en entrée, aucune dérivée de
surface inconnue à estimer et aucun prix de référence utilisé par la
calibration. Même `--demo` transmet seulement un CSV de fourchettes au
constructeur.

## 2. Une condition finie reliant fourchettes et bornes locales

Notons `B(f)` la liste des coefficients de Bernstein d'un polynôme `f` sur
`R`, après élévation de degré pour aligner les termes d'une différence.
Exiger `B(f)>=0` est une liste finie d'inégalités linéaires dans `a`.

**Condition de construction C.** Calculer un vecteur rationnel `a` tel que :

\[
\begin{aligned}
&b_k\le P_a(T_k,x_k)\le A_k &&\text{pour chaque observation},\\
&\mathcal B(P_a),\ \mathcal B(P_a-(1-x)),\ \mathcal B(1-P_a)\ge0,\\
&\mathcal B(-P_{a,x}),\ \mathcal B(1+P_{a,x})\ge0,\\
&\mathcal B(P_{a,xx}-g)\ge0,\\
&\mathcal B\big(P_{a,T}-\tfrac12(v_{\min}+\delta)x^2P_{a,xx}\big)\ge0,\\
&\mathcal B\big(\tfrac12(v_{\max}-\delta)x^2P_{a,xx}-P_{a,T}\big)\ge0,\\
&\mathcal B_T\big(1-P_a(T,x_a)+x_aP_{a,x}(T,x_a)\big)\ge0.
\end{aligned}
\tag{C}
\]

Ici `b_k=bid_k`, `A_k=ask_k`. La dernière condition assure la compatibilité
convexe du bord gauche avec le point `(0,1)` en strike. Elle est nécessaire
pour couvrir aussi la contrainte `left_chord` du logiciel existant.

Cette condition se recherche par un **LP de coefficients**, construit à
partir des fourchettes, et se valide ensuite exactement. Ce n'est pas
l'hypothèse qu'une surface admissible inconnue existe : les coefficients
calculés constituent le témoin fini et donnent directement tous les prix.
La recherche porte sur une famille polynomiale suffisante, plus restrictive
que l'ensemble des calibrations discrètes du LP initial. Elle ne fournit pas
un critère nécessaire simple sur les seules largeurs des fourchettes.

Pour rendre explicite le rôle des fourchettes, la première ligne s'écrit
également, pour chaque quote, avec son milieu `m_k` et sa demi-largeur `s_k` :

\[
|E_ka-m_k|\le s_k,\qquad
(E_k)_{pq}=B_p^m(u_k)B_q^n(w_k).
\]

Les autres lignes sont des contraintes de forme `L_r a+d_r>=0`, dont les
coefficients sont calculables à partir du rectangle, des degrés et des
bornes locales. Avec (G) ci-dessous, on obtient donc une condition finie
**fourchettes + bornes locales + géométrie**.

HiGHS maximise une marge commune `rho>=0`, en remplaçant chaque contrainte
`r.a+d>=0` par `r.a+d>=s_r rho`, où
`s_r=max(1,|d|,sum|r_i|)`. Cela favorise un candidat intérieur et une
reconstruction rationnelle stable. Une marge numérique positive n'est
jamais acceptée comme preuve. Après reconstruction, toutes les lignes de
(C) et toutes les fourchettes sont recalculées sans tolérance. Une solution
exacte sur certaines frontières peut aussi être acceptée si ce contrôle
réussit. La découverte numérique n'est pas une méthode complète de
résolution exacte des LP dégénérés.

## 3. Constantes calculées sur le témoin construit

Sur ce même polynôme, on calcule exactement :

\[
\gamma_0=\min\mathcal B(P_{a,xx})\ge g>0,\qquad
M_3=\max|\mathcal B(P_{a,xxx})|,\quad
M_4=\max|\mathcal B(P_{a,xxxx})|,\quad
M_{TT}=\max|\mathcal B(P_{a,TT})|.
\]

Ces nombres sont des bornes globales certifiées sur `R`, par positivité et
partition de l'unité de la base de Bernstein. Une dérivée identiquement
nulle donne la constante zéro. Les constantes ne sont pas supposées connues
avant la construction.

## 4. Théorème de faisabilité sur un maillage donné

Sur tout maillage commun dans `R` conservant les coordonnées de toutes les
observations, poser, à chaque strike intérieur,

\[
h_i^-=x_i-x_{i-1},\quad h_i^+=x_{i+1}-x_i,\quad
E_{\gamma,i}={|h_i^+-h_i^-|M_3\over3}
+{((h_i^+)^3+(h_i^-)^3)M_4\over12(h_i^++h_i^-)}.
\]

**Condition géométrique G.** Pour toute cellule temporelle et tout strike
intérieur, demander

\[
E_{\gamma,i}<\gamma_0,\qquad
{\Delta T_j M_{TT}/x_a^2+v_{\max}E_{\gamma,i}
 \over\gamma_0-E_{\gamma,i}}\le\delta.
\tag{G}
\]

**Conclusion.** Si (C) est validée exactement et si (G) est satisfaite, les
prix **construits** `c_ji=P_a(T_j,x_i)` sont une calibration admissible pour
les contraintes du logiciel sur cette fenêtre : fourchettes, bornes de
prix, pentes entre `-1` et `0`, convexité, calendriers, raccord gauche et
bornes locales discrètes **forward et backward simultanément**. Les
gammas intérieurs sont strictement positifs ; aucun quotient `0/0` n'est
utilisé.

### Preuve

La base de Bernstein est positive et sa somme vaut un. Les inégalités de
coefficients dans (C) impliquent donc, partout dans `R`,

\[
(1-x)^+\le P_a\le1,\quad -1\le P_{a,x}\le0,\quad
P_{a,xx}\ge\gamma_0>0,
\quad v={2P_{a,T}\over x^2P_{a,xx}}
\in[v_{\min}+\delta,v_{\max}-\delta].
\]

En particulier `P_{a,T}>0`. Les pentes discrètes sont des moyennes de
`P_{a,x}` ; leur croissance vient de la convexité. Les prix sont croissants
en temps. Au bord gauche, la dernière ligne de (C) donne
`(P_a(T,x_a)-1)/x_a <= P_{a,x}(T,x_a)`, puis la convexité donne
`P_{a,x}(T,x_a) <= (P_a(T,x_1)-P_a(T,x_a))/(x_1-x_a)`.
Les fourchettes sont respectées exactement aux coordonnées conservées.

À un nœud spatial, le développement de Taylor de chaque pente jusqu'à
l'ordre trois, avec reste borné par `M_4`, donne

\[
|\Gamma_h(T,x_i)-P_{a,xx}(T,x_i)|\le E_{\gamma,i}.
\]

Le terme cubique vaut `(h_i^+-h_i^-)P_{a,xxx}/3`. Le reste est borné par
`((h_i^+)^3+(h_i^-)^3)M_4/[12(h_i^++h_i^-)]`. Ainsi
`Gamma_h>=gamma0-E_gamma>0`.

La différence temporelle est une moyenne de `P_{a,T}`. Pour **chacun** des
deux bords `T_*` de la cellule temporelle,

\[
|\Theta_h-P_{a,T}(T_*,x_i)|\le\tfrac12\Delta T_j M_{TT}.
\]

En soustrayant les deux quotients, avec `Gamma_h` et `P_{a,xx}` pris au
même bord temporel `T_*`, on obtient

\[
\left|{2\Theta_h\over x_i^2\Gamma_h(T_*,x_i)}
      -{2P_{a,T}(T_*,x_i)\over x_i^2P_{a,xx}(T_*,x_i)}\right|
\le {\Delta T_jM_{TT}/x_a^2+v_{\max}E_{\gamma,i}
       \over\gamma_0-E_{\gamma,i}}.
\]

La marge `delta` absorbe cette erreur. Le bord gauche fournit la variante
forward ; le bord droit fournit la variante backward. Cela démontre (G)
et toutes les conclusions annoncées.

## 5. Règle de raffinement et terminaison

Conserver **le même polynôme certifié** et toutes les quotes d'origine.
Diviser chaque intervalle spatial et chaque intervalle temporel de base
en `2^ell` morceaux égaux. Poser

\[
H=\max_i h_i,\quad D=\max_i|h_{i+1}-h_i|,\quad
\tau=\max_j\Delta T_j,
\quad e_\ell={DM_3\over3\,2^\ell}+{H^2M_4\over12\,4^\ell}.
\]

À un ancien nœud, l'asymétrie est divisée par `2^ell` ; à un nouveau nœud
intérieur à un intervalle original, elle est nulle. Par ailleurs
`(a^3+b^3)/(a+b)=a^2-ab+b^2<=max(a,b)^2`. Donc tous les
`E_gamma` sont majorés par `e_ell`.

Le programme cherche le premier entier satisfaisant, **en rationnels**,

\[
e_\ell<\gamma_0,\qquad
{\tau M_{TT}/(2^\ell x_a^2)+v_{\max}e_\ell
 \over\gamma_0-e_\ell}\le\delta.
\tag{R}
\]

Depuis 0.1.6, le même test s'écrit exactement `C*r^2-A*r-B>=0`, avec
`r=2^ell`, `a=D*M3/3`, `b=H^2*M4/12`, `d=tau*Mtt/x_a^2`,
`A=d+(v_max+delta)*a`, `B=(v_max+delta)*b`, `C=delta*gamma0`.
Le rapport fournit ces constantes, la marge quadratique et une borne
entière finie du niveau requis ; la preuve figure dans `CRITERE_PROUVE.md`.

Les constantes sont finies, `gamma0>0`, `delta>0`, `x_a>0` : le membre de
gauche tend vers zéro. Un seuil fini existe. Au-delà, le numérateur
décroît et le dénominateur croît : **tous les niveaux dyadiques suivants
sont admissibles**, pour les deux schémas. Aucun LP n'est relancé sur les
maillages raffinés. Les valeurs aux anciens nœuds restent identiques et
les fourchettes ne sont jamais élargies.

L'algorithme borne sa recherche par `--max-level` ; atteindre ce plafond
sans seuil conserve le certificat continu sur la fenêtre, mais n'annonce
pas de niveau calculé. `--max-nodes` limite seulement la matérialisation des
échantillons ; le seuil théorique peut être certifié sans allouer la grille.
La preuve concerne les grilles rationnelles exactes. Des niveaux extrêmes
peuvent dépasser la résolution ou la mémoire de l'export binary64.

La même conclusion vaut pour une autre famille de grilles si ses maxima
d'erreurs dans (G) tendent vers zéro en conservant les observations. Le
raffinement dyadique couplé est la règle implémentée. Un raffinement
arbitraire ne suffit pas : le pas de temps et l'erreur spatiale doivent
tous deux devenir assez petits. Raffiner seulement le temps ne supprime
pas l'erreur spatiale, sauf cas particulier où celle-ci est déjà absorbée
ou nulle ; réciproquement pour le temps.

## 6. Certification, calcul natif et résultats

Le LP de recherche est exécuté par HiGHS C++ en wheel pip. L'évaluation des
échantillons utilise NumPy/BLAS ou les produits matriciels PyTorch CUDA en
float64 avec `--device cuda`. Aucun compilateur, CMake, nvcc ou compilation
JIT n'est requis. La vérification exacte utilise `fractions.Fraction` sur
CPU : elle ne prétend pas être un noyau CUDA. Les phases longues, le
solveur, la reconstruction et les audits ont les compteurs, barres et
heartbeats du superviseur existant.

Le certificat JSON contient les observations binary64 interprétées comme
rationnels exacts, leurs empreintes, les paramètres et les coefficients
rationnels. `verify-construct` recalcule toutes les contraintes et les
constantes ; il ne fait confiance ni aux minima stockés dans le rapport,
ni à un statut HiGHS, ni à une tolérance. Le hash relie le certificat aux
données ; ce n'est pas une signature d'authenticité externe.

Les NPZ sont des exports arrondis : ils passent séparément l'audit du LP
binary64 et l'audit direct de chaque schéma à `--audit-tol`. La preuve
mathématique concerne les prix rationnels `P_a(T_j,x_i)` ; elle ne certifie
pas que chaque arrondi matériel appartient exactement au LP binary64.
`mesh.exact.json` décrit les axes rationnels et les coefficients du
certificat suffisent à reconstruire tous les prix exacts.

Résultats possibles :

| Conclusion | Sens |
| --- | --- |
| `feasible_from_guaranteed_level` | Certificat exact et seuil (R) calculé ; éventuel export audité séparément |
| `continuous_window_certified` | (C) démontrée, seuil non atteint dans la recherche bornée |
| `not_certified` | Aucun candidat validé exactement ; aucune impossibilité générale déduite |

Le code retour 3 signifie `not_certified`, 2 une erreur d'exécution ou
d'hypothèses, 0 une certification réussie. Pour chaque tentative, lire
`construction.json` ; le statut du solveur seul n'est pas une conclusion.

## 7. Portée et limites à conserver dans un article

Les hypothèses utiles à la garantie sont établies sur le **témoin construit**,
et non supposées pour une surface continue inconnue. En revanche, l'obtention
d'un témoin dans cette famille n'est pas universellement garantie. Des
fourchettes trop serrées, une faible densité dans les ailes, un degré trop
petit ou un plancher de gamma trop élevé peuvent faire échouer (C), alors
que le problème discret ou un autre modèle continu est faisable. Diminuer
un paramètre ou augmenter les degrés constitue une nouvelle recherche,
qui doit être certifiée à nouveau. Le programme n'ajuste pas les hypothèses
silencieusement.

Le résultat est intérieur : il ne traite pas le payoff en `T=0`, les queues
à l'infini, un ancrage zéro de support fini, une extension globale en temps
ou une construction de diffusion martingale. Il ne traite pas non plus
les bornes de variance variables par cellule ni des maillages spatiaux
changeant avec l'échéance. Une union commune des strikes évite ici le terme
d'interpolation temporelle de type `h_interp^2/DeltaT`. L'absence de ce
terme dépend de ce choix ; elle ne s'étend pas automatiquement aux grilles
mobiles.

La garantie de tous les niveaux suivants vient de l'échantillonnage du
même témoin et de (R), pas d'une inclusion générale des ensembles de
solutions des LP discrets. Elle est compatible avec les contre-exemples
de faisabilité non monotone observés dans la campagne précédente.

La positivité en base de Bernstein et l'analyse de Taylor sont des outils
classiques. Cette note fournit une construction certifiable dans une
classe précisée et un lien explicite aux fourchettes et au maillage ; la
nouveauté scientifique éventuelle nécessite une étude bibliographique
distincte et n'est pas établie par les tests du logiciel.

Références primaires :

- N. M. Patrikalakis, T. Maekawa, W. Cho, *Shape Interrogation for Computer
  Aided Design and Manufacturing*, §1.3.1–1.3.2 : propriétés, dérivation,
  élévation et arithmétique de la base de Bernstein.
  <https://web.mit.edu/hyperbook/Patrikalakis-Maekawa-Cho/node9.html>
- H. Buehler, E. Ryskin, *Discrete Local Volatility for Large Time Steps*,
  version extensive, §3.3 : question de faisabilité sous bornes forward.
  <https://quantitative-research.de/dl/Discrete%20Local%20Volatility%20-%20Extensive.pdf>
