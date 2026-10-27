# Critères prouvés de faisabilité et de raffinement — version 0.1.6

Cette note donne deux résultats : un critère **nécessaire et suffisant sur une
grille finie fixée**, puis un critère **suffisant constructif**, accompagné
d'un seuil de raffinement conservant toutes les observations. Les preuves
portent sur les contraintes écrites ci-dessous. La recherche de certificats
par un solveur flottant reste une procédure incomplète ; chaque certificat
accepté est vérifié en arithmétique rationnelle exacte.

## 1. Hypothèses : observations, normalisation et domaine

**O1 — Normalisation fixée.** Les observations sont des fourchettes de calls
européens, ou de puts traduits en calls par parité. Pour chaque maturité,
les valeurs de règlement, le temps annuel `T`, le forward `F(T)>0` et
l'actualisation `D(T)>0` sont fixés. On utilise

\[
x=K/F(T),\qquad [b,a]=[\mathrm{bid},\mathrm{ask}]/(D(T)F(T)).
\]

Un put normalisé contraint le **même** call via l'intervalle
`[put_bid/(DF)+1-x, put_ask/(DF)+1-x]`. Les observations calls et puts
ne sont pas fusionnées en un milieu. Le résultat est conditionnel à cette
normalisation ; il ne quantifie pas l'erreur sur `F,D,T`, et ne démontre pas
la synchronisation des livres.

**O2 — Observations finies.** On dispose de `N>=1` quadruplets
`(t_k,x_k,b_k,a_k)` de nombres finis. Les doublons sont conservés comme
contraintes distinctes. Pour l'alternative du théorème 1, un livre croisé
`b_k>a_k`, ou une borne de prix négative, est conservé : il peut donner un
certificat d'impossibilité. Le théorème 2 exige que le témoin respecte
effectivement chacun des intervalles, ce qui exclut ces contradictions.

**G1 — Grille commune.** Les nœuds de calcul forment le produit cartésien

\[
\mathcal G=\{T_0<\cdots<T_m\}\times\{0<x_0<\cdots<x_n\},
\quad m\ge1,\ n\ge2,\ T_0\ge0.
\]

Chaque observation est exactement un nœud de cette grille. Des strikes
observés différents selon l'échéance sont permis : on prend leur union et
les prix aux nœuds non observés deviennent des inconnues. Aucune quote n'est
interpolée. Les pas sont strictement positifs, sans hypothèse de régularité
de leur rapport. Une grille spatiale mobile avec un opérateur de transport
entre échéances sort du présent cadre.

**G2 — Fenêtre finie.** La grille couvre une fenêtre finie en temps et en
strike. Le raccord gauche au point `(x,c)=(0,1)` est imposé. Le dernier
prix n'est pas fixé à zéro. Une hypothèse de support borné ou d'extension
globale des queues doit faire l'objet d'un autre problème.

**B1 — Bornes fixées.** Pour le théorème 1, des bornes de **variance**
`0<=v_min[j,i]<=v_max[j,i]<infinity` sont prescrites par cellule intérieure.
Les bornes peuvent être égales. La CLI demande des volatilités :
`v_min=sigma_min^2`, `v_max=sigma_max^2`. Le théorème 2 utilise des bornes
constantes strictement distinctes et une marge intérieure explicite.
L'API `finite_criterion.Problem` accepte les tableaux par cellule ; la
commande de recherche `criterion` utilise les bornes scalaires passées
sur sa ligne de commande. `verify-criterion` respecte les tableaux du
problème sauvegardé qu'il vérifie.

Ces hypothèses définissent un problème mathématique sur des données
déclarées. Elles n'affirment pas que des valeurs téléchargées sont les prix
exacts d'un marché sans arbitrage.

## 2. Contraintes sur la grille fixée

Les inconnues sont les calls normalisés `c[j,i]`. Posons

\[
h_i^-=x_i-x_{i-1},\quad h_i^+=x_{i+1}-x_i,\quad
s_{j,i}={c_{j,i+1}-c_{j,i}\over x_{i+1}-x_i},
\]

\[
\Gamma_{j,i}={2\over h_i^-+h_i^+}
 \left({c_{j,i+1}-c_{j,i}\over h_i^+}
       -{c_{j,i}-c_{j,i-1}\over h_i^-}\right),\qquad
\Theta_{j,i}={c_{j+1,i}-c_{j,i}\over\Delta T_j}.
\]

L'ensemble `F0` impose exactement :

1. `(1-x_i)^+ <= c[j,i] <= 1` ; si `T_0=0`, la première ligne est le payoff ;
2. `-1 <= s[j,i] <= 0` et `Gamma[j,i]>=0` ;
3. `c[j+1,i]>=c[j,i]` à tous les strikes ;
4. `(c[j,0]-1)/x_0 <= s[j,0]`, raccord convexe au point d'origine ;
5. `b_k <= c[j(k),i(k)] <= a_k` pour **chaque** observation.

Pour un schéma `s`, l'ensemble `F_s` ajoute

\[
\tfrac12\underline v_{j,i}x_i^2\Delta T_j\Gamma^s_{j,i}
\le c_{j+1,i}-c_{j,i}
\le\tfrac12\overline v_{j,i}x_i^2\Delta T_j\Gamma^s_{j,i},
\tag{L}
\]

avec `Gamma^forward[j,i]=Gamma[j,i]` et
`Gamma^backward[j,i]=Gamma[j+1,i]`. L'ensemble `F_joint` impose les deux
sur **un même vecteur de prix**. Deux témoins obtenus séparément établissent
`F_forward` et `F_backward` non vides, sans établir que leur intersection
est non vide.

La formulation (L) reste définie si `Gamma=0` : elle impose alors une
différence temporelle nulle. Elle ne définit aucune variance par quotient
dans cette cellule. Si l'on veut une variance partout identifiable, il
faut une hypothèse supplémentaire de gamma strictement positif ; le
théorème 2 l'établit sur son témoin.

## 3. Théorème 1 — Alternative exacte sur grille fixée

Sous O1–O2, G1–G2 et B1, choisir `F0`, `F_forward`, `F_backward` ou
`F_joint`. Toutes ses contraintes hors boîte s'écrivent

\[
A c\le b,\qquad l\le c\le u,
\tag{P}
\]

où `l[j,i]=(1-x_i)^+`, `u[j,i]=1`, avec `u[0,i]=l[0,i]` si `T_0=0`.
Les coefficients de `A,b,l,u` sont explicitement calculables à partir
des pas, des observations et des bornes. La boîte est non vide et compacte.

**Énoncé.** Exactement une des deux situations suivantes se produit :

- il existe un vecteur de prix `c` satisfaisant (P) ;
- il existe un vecteur `lambda>=0` tel que

\[
\boxed{\quad
\sum_{q}\min\{r_q l_q,r_q u_q\}>\lambda^T b,
\qquad r=A^T\lambda.\quad}
\tag{S}
\]

En particulier, l'absence de tout séparateur (S) est un critère nécessaire
et suffisant de non-vacuité de l'ensemble choisi. Pour des données
rationnelles, un témoin rationnel existe dans l'une ou l'autre situation.
Le membre gauche de (S) corrige exactement le résidu dual `A^T lambda` :
il n'est pas nécessaire que ce résidu soit nul.

### Preuve

Si `c` est admissible et `lambda>=0`, alors

\[
\sum_q\min\{r_ql_q,r_qu_q\}\le r^Tc
 =\lambda^TAc\le\lambda^Tb.
\]

Un séparateur (S) est donc incompatible avec tout témoin admissible.

Réciproquement, soit `B=[l,u]` et
`K={Ac+s : c in B, s>=0}`. Cet ensemble est convexe, non vide et fermé :
`AB` est compact et sa somme avec l'orthant fermé est fermée. La faisabilité
de (P) équivaut à `b in K`. Si elle échoue, soit `z` le point de `K` le plus
proche de `b`, et `lambda=z-b`. La condition de projection sur un convexe
donne `lambda^T(k-z)>=0` pour tout `k in K`.

Comme `z+t e_i in K` pour `t>=0`, on obtient `lambda_i>=0`. Par ailleurs

\[
\min_{k\in K}\lambda^Tk=\lambda^Tz
 =\lambda^Tb+\|z-b\|^2>\lambda^Tb.
\]

Pour `lambda>=0`, ce minimum est
`min_{c in B} lambda^T A c`, soit précisément
`sum_q min(r_q l_q,r_q u_q)`. C'est (S).

Si les coefficients sont rationnels, une boîte intersectée avec des
demi-espaces rationnels est un polytope rationnel compact. Lorsqu'il est
non vide, il possède un sommet rationnel, obtenu par résolution d'un
système linéaire rationnel de contraintes actives. Lorsqu'il est vide,
l'écart strict de (S), fonction continue de `lambda`, reste positif après
une approximation rationnelle suffisamment précise de `lambda` dans
l'orthant positif. Les deux types de preuves peuvent ainsi être finis
et rationnels. Ce résultat est une forme de l'alternative de Farkas. □

### Vérification et diagnostic

`finite_criterion.py` construit les coefficients **directement en
rationnels**. La matrice flottante n'est qu'un outil de recherche. Un
témoin positif est contrôlé sur toutes les lignes exactes et la boîte ;
un témoin négatif est contrôlé par (S), sur ces mêmes coefficients exacts.

Les données CSV du nouveau chemin `criterion` sont interprétées comme
des décimaux exacts. `--logical-grid` accepte les coordonnées rationnelles
avant arrondi, notamment `F0.exact_grid.json` du collecteur Yahoo. Le
certificat est lié par SHA-256 à l'ensemble du problème déclaré : grille,
observations, bornes, schéma et provenance. Un hash établit une liaison
entre fichiers ; il n'authentifie pas un fournisseur externe.

| Résultat vérifié | Conclusion justifiée |
| --- | --- |
| `F0` impossible | Observations et contraintes de forme incompatibles sous la normalisation fixée |
| `F0` faisable, `F_s` impossible | Bornes et grille choisies incompatibles avec ces observations |
| `F_joint` faisable | Un même témoin satisfait les deux schémas sur cette grille |
| Aucun témoin exact trouvé | `not_certified`, aucune conclusion de faisabilité ou d'impossibilité |

La deuxième ligne n'isole pas à elle seule une faute des bornes ou de la
grille. Une nouvelle grille, avec **les mêmes observations**, peut établir
un effet du maillage. Écarter des observations ou élargir des fourchettes
définit un autre problème.

Le théorème est une alternative complète ; le chercheur numérique de
certificats n'est pas un algorithme exact complet. Une limite de temps,
un LP dégénéré ou une reconstruction rationnelle manquée peut produire
`not_certified` malgré l'existence mathématique d'un des témoins.

## 4. Théorème 2 — Condition suffisante et raffinement explicite

Considérons un rectangle intérieur
`R=[T_a,T_b] x [x_a,x_b]`, avec `T_a>0`, `x_a>0`, contenant toutes les
observations et la grille de base. Les grilles ont les mêmes extrémités
que le rectangle. Outre O1–O2 et G1–G2, supposons que l'on ait
**construit et certifié** un polynôme rationnel `P(T,x)` tel que, sur `R` :

\[
\begin{gathered}
(1-x)^+\le P\le1,\quad -1\le P_x\le0,\quad
P_{xx}\ge\gamma_0>0,\quad
1-P(T,x_a)+x_aP_x(T,x_a)\ge0,\\
b_k\le P(t_k,x_k)\le a_k\quad\text{pour toute observation},\\
0\le v_{\min}<v_{\max}<\infty,\quad
0<2\delta<v_{\max}-v_{\min},\quad
v_{\min}+\delta\le {2P_T\over x^2P_{xx}}\le v_{\max}-\delta.
\end{gathered}
\tag{C}
\]

On certifie également les constantes globales
`|P_xxx|<=M3`, `|P_xxxx|<=M4`, `|P_TT|<=Mtt`. Les maxima d'un
échantillon numérique de dérivées ne suffisent pas à cette hypothèse.
La section 5 donne un système fini calculable établissant (C) et ces bornes.

Sur les axes de base, poser

\[
H=\max_i(x_{i+1}-x_i),\quad
D_h=\max_i|(x_{i+1}-x_i)-(x_i-x_{i-1})|,\quad
\tau=\max_j\Delta T_j.
\]

Au niveau `ell`, diviser **chaque** intervalle spatial et temporel de base
en `r=2^ell` intervalles égaux. Définir

\[
a={D_h M_3\over3},\quad b={H^2M_4\over12},\quad
d={\tau M_{TT}\over x_a^2},\qquad
A=d+(v_{\max}+\delta)a,\quad
B=(v_{\max}+\delta)b,\quad C=\delta\gamma_0>0.
\]

**Énoncé.** Si (C) est certifiée, la condition finie

\[
\boxed{\quad C r^2-A r-B\ge0,\qquad r=2^\ell\quad}
\tag{Q}
\]

garantit que les prix `c[j,i]=P(T_j,x_i)` sont dans `F_joint` sur le
maillage raffiné. Ils satisfont donc simultanément toutes les observations,
les contraintes de forme et les deux bornes locales discrètes. Tous les
gammas intérieurs sont strictement positifs. Le même résultat vaut à tous
les niveaux dyadiques ultérieurs, avec le **même polynôme**, les **mêmes
observations** et les **mêmes bornes**.

Un seuil fini est explicite :

\[
r_*={A+\sqrt{A^2+4BC}\over2C},\qquad
\ell_* = \min\{\ell\in\mathbb N_0:2^\ell\ge\max(1,r_*)\}.
\]

Une borne entière, moins précise mais sans racine carrée, est

\[
R_0=\max\left(1,\left\lceil{A+B\over C}\right\rceil\right),
\qquad \ell_*\le\left\lceil\log_2 R_0\right\rceil.
\tag{U}
\]

Le programme teste (Q) en rationnels et fournit aussi (U), même lorsqu'un
plafond de recherche empêche de parcourir tous les niveaux. Le seuil est
celui de cette **borne suffisante**, pas le premier niveau nécessairement
faisable parmi toutes les calibrations possibles.

### Preuve

Pour un nœud intérieur, Taylor appliqué aux deux pentes spatiales donne

\[
\left|\Gamma_h(T,x_i)-P_{xx}(T,x_i)\right|
\le {|h_i^+-h_i^-|M_3\over3}
 +{(h_i^+)^3+(h_i^-)^3\over12(h_i^++h_i^-)}M_4.
\tag{E1}
\]

En effet, les termes constants et linéaires de chaque développement se
compensent dans la seconde différence. Le terme cubique restant est
`(h_i^+-h_i^-) P_xxx/3`. Le reste d'ordre quatre dans chaque prix est
majoré par `M4*h^4/24` ; la division par le pas puis par
`(h_i^++h_i^-)/2` donne le second terme de (E1).

Après subdivision dyadique, à un ancien nœud les deux pas adjacents sont
divisés par `r` ; à un nouveau nœud situé dans un intervalle de base ils
sont égaux. Comme `(p^3+q^3)/(p+q)=p^2-pq+q^2<=max(p,q)^2` pour
`p,q>0`, l'erreur spatiale est uniformément majorée par

\[
e_r={a\over r}+{b\over r^2}.
\]

Au bord gauche **ou** au bord droit `T_*` d'une cellule temporelle,
la différence temporelle est la moyenne de `P_T` ; le théorème fondamental
de l'analyse donne

\[
|\Theta_h-P_T(T_*,x_i)|\le {\tau M_{TT}\over2r}.
\tag{E2}
\]

Si `e_r<gamma0`, alors `Gamma_h>=gamma0-e_r>0`. Avec
`v=2 P_T/(x_i^2 P_xx)` et les deux dérivées au même bord `T_*`,

\[
{2\Theta_h\over x_i^2\Gamma_h}-v
={2(\Theta_h-P_T)/x_i^2-v(\Gamma_h-P_{xx})\over\Gamma_h}.
\]

Par (E1), (E2), `x_i>=x_a` et `0<=v<=v_max`,

\[
|v_h-v|\le
 {d/r+v_{\max}e_r\over\gamma_0-e_r}.
\tag{E3}
\]

La condition (Q) équivaut à
`d/r+(v_max+delta)e_r<=delta*gamma0`. Elle implique
`e_r<=delta*gamma0/(v_max+delta)<gamma0`, car `v_max>0`.
Elle implique donc aussi que (E3) est au plus `delta`. La marge de (C)
donne `v_min<=v_h<=v_max`, au bord gauche pour forward et au bord droit
pour backward, avec les **mêmes valeurs** `P(T_j,x_i)`.

Les pentes discrètes de `P` sont des moyennes de `P_x` : elles appartiennent
à `[-1,0]`. Leur croissance résulte de `P_xx>0`. La condition locale
continue donne `P_T>0`, donc les calendriers. Le raccord gauche découle de

\[
{P(T,x_a)-1\over x_a}\le P_x(T,x_a)
\le {P(T,x_1)-P(T,x_a)\over x_1-x_a}.
\]

Les autres bornes et les observations sont conservées par évaluation de
`P` aux nœuds d'origine, qui restent des nœuds de chaque raffinement.

Enfin, `A,B>=0` et `C>0`. Le polynôme `C r^2-A r-B` est non négatif pour
`r>=r_*`; il le reste aux niveaux suivants. Pour `r>=1`,
`Ar+B<=(A+B)r`, d'où la borne (U). Le cas `A=B=0` donne immédiatement
`ell_*=0`. Cela prouve la terminaison mathématique et toutes les assertions. □

## 5. Condition finie calculable sur les observations et les bornes

Le théorème 2 n'est pas utilisé avec l'hypothèse invérifiée d'une surface
inconnue. Pour des degrés `p>=1`, `q>=2`, on cherche les coefficients
rationnels `alpha_ab` du polynôme de Bernstein tensoriel

\[
P_\alpha(T,x)=\sum_{a=0}^p\sum_{b=0}^q
\alpha_{ab}B_a^p\left({T-T_a\over T_b-T_a}\right)
B_b^q\left({x-x_a\over x_b-x_a}\right).
\]

Notons `mathcal B(f)` les coefficients de Bernstein d'un polynôme `f`,
après élévation de degré lorsque nécessaire. Les conditions suivantes
forment un **système fini d'inégalités linéaires en alpha** :

\[
\begin{aligned}
&b_k\le P_\alpha(t_k,x_k)\le a_k\quad(1\le k\le N),\\
&\mathcal B(P_\alpha),\ \mathcal B(P_\alpha-1+x),\ \mathcal B(1-P_\alpha)\ge0,\\
&\mathcal B(-P_{\alpha,x}),\ \mathcal B(1+P_{\alpha,x})\ge0,\\
&\mathcal B(P_{\alpha,xx}-g)\ge0\quad\text{pour }g>0,\\
&\mathcal B(P_{\alpha,T}-\tfrac12(v_{\min}+\delta)x^2P_{\alpha,xx})\ge0,\\
&\mathcal B(\tfrac12(v_{\max}-\delta)x^2P_{\alpha,xx}-P_{\alpha,T})\ge0,\\
&\mathcal B_T(1-P_\alpha(T,x_a)+x_aP_{\alpha,x}(T,x_a))\ge0.
\end{aligned}
\tag{BC}
\]

Les degrés actuellement pris en charge par `construct` sont
`1<=p<=8`, `2<=q<=20` ; cette limite de calcul ne restreint pas l'énoncé
mathématique pour un polynôme de degré fini arbitraire.

**Corollaire constructif.** Un vecteur rationnel `alpha` satisfaisant (BC)
et une grille satisfaisant (Q) constituent un critère fini suffisant de
faisabilité conjointe, directement relié aux fourchettes et aux bornes.

**Preuve.** Les polynômes de base de Bernstein sont non négatifs et leur
somme vaut un. Chaque polynôme dont tous les coefficients sont positifs
ou nuls est donc positif ou nul sur le rectangle. Ainsi (BC) implique (C).
On peut certifier

\[
\gamma_0=\min\mathcal B(P_{\alpha,xx})\ge g,
\quad M_3=\max|\mathcal B(P_{\alpha,xxx})|,
\quad M_4=\max|\mathcal B(P_{\alpha,xxxx})|,
\quad M_{TT}=\max|\mathcal B(P_{\alpha,TT})|.
\]

Ces constantes et les quantités de (Q) sont calculables en rationnels.
Le théorème 2 s'applique. □

Cette condition est suffisante à degré fixé. Un échec ne prouve ni
l'impossibilité de (P), ni l'absence d'une autre surface régulière.
Le LP numérique ne reçoit que les observations ; les coefficients du
générateur de la démonstration ne lui sont pas fournis.

## 6. Utilisation et sémantique des fichiers

```powershell
# Depuis la racine du dépôt, dans le Python .venv312 explicite :
python -m pip install -r requirements-lock.txt
python -m pip install --no-build-isolation --no-deps -e .

# Grille exacte provenant de TON téléchargement, déjà accepté par le collecteur :
python -u -m dupire_joint criterion `
  --logical-grid ".\runs\yahoo_valide_20261026T203526_495751Z\collecte\accepted\F0.exact_grid.json" `
  --scheme joint --sigma-min 0.05 --sigma-max 1.0 --threads 4 `
  --out .\runs\critere_yahoo

# Vérification indépendante, sans téléchargement ni résolution :
python -u -m dupire_joint verify-criterion `
  --problem .\runs\critere_yahoo\criterion.problem.json `
  --certificate .\runs\critere_yahoo\criterion.certificate.json `
  --logical-grid ".\runs\yahoo_valide_20261026T203526_495751Z\collecte\accepted\F0.exact_grid.json" `
  --out .\runs\critere_yahoo_verifie

# Critère constructif et seuil prouvé sur un exemple contrôlé :
python -u -m dupire_joint construct --demo --device cpu `
  --degree-time 2 --degree-space 4 --threads 4 --out .\runs\construction_prouvee
python -u -m dupire_joint verify-construct `
  --certificate .\runs\construction_prouvee\constructive.certificate.json `
  --quotes .\runs\construction_prouvee\observations.csv `
  --out .\runs\construction_verifiee
```

Pour un autre fichier normalisé, utiliser `criterion --quotes fichier.csv`.
Les raffinements du théorème 1 se demandent par `--space-level` et
`--time-level` ; ils conservent toutes les lignes observées, sans garantir
la faisabilité. Le théorème 2, lorsqu'il est certifié, garantit les niveaux
à partir du seuil calculé et n'a pas besoin de relancer les LP à ces niveaux.

| Chemin | Arithmétique faisant autorité |
| --- | --- |
| `criterion --quotes` | Décimaux du CSV interprétés exactement comme rationnels |
| `criterion --logical-grid` | Rationnels déclarés dans le JSON, avant arrondi du LP numérique |
| `construct`, `verify-construct` | Valeurs binary64 du CSV interprétées exactement comme rationnels ; paramètres des bornes et marges saisis exactement depuis 0.1.6 |
| Anciennes commandes `solve`, `verify` | LP binary64 et audits/certificats décrits dans `MATHEMATICS.md` |

Les exports NPZ de `construct` sont arrondis et audités séparément. La preuve
porte sur le polynôme rationnel et les axes rationnels de `mesh.exact.json`.
La limite `--max-nodes` borne l'export, sans invalider le seuil théorique.
`construction.json` contient `quadratic_criterion`, ses constantes et la
marge exacte de chaque niveau essayé. `verify-construct` recalcule ces
quantités à partir du témoin, sans croire aux minima enregistrés.

Codes retour de `criterion` : `0` faisabilité exacte ; `4` impossibilité
exacte sur le problème déclaré ; `3` résultat non certifié ; `2` erreur
d'entrée ou d'exécution. `verify-criterion` renvoie `0` pour une preuve
valide, qu'elle soit positive ou négative. Un certificat négatif F0 se
vérifie avec `F0.problem.json` et `F0.certificate.json`.

## 7. Portée scientifique

Le résultat répond à une question de non-vacuité **dans une classe précisée**.
Le théorème 1 caractérise exactement le système discret déclaré. Le
théorème 2 fournit une condition suffisante sur une classe de témoins lisses,
avec un seuil quantifié préservant les observations. Il ne repose pas sur
l'emboîtement des ensembles de calibrations discrètes, qui n'est pas
affirmé.

Le théorème 2 exclut `T=0`, les gammas nuls, les bornes par cellule et les
grilles spatiales mobiles. Aucun des deux théorèmes ne démontre une
extension des queues à l'infini, une diffusion martingale globale, une
robustesse simultanée à toutes les courbes `F,D` possibles, ou la cohérence
de toute la chaîne Yahoo brute après une sélection de strikes. Une
sélection préalable au pas de 50 est une restriction des observations,
pas le raffinement préservant les observations du théorème 2.

Les outils de séparation convexe/Farkas, de Bernstein et de Taylor sont
classiques. Cette formulation précise leurs hypothèses et leur liaison
au système implémenté. Une revendication de nouveauté ou de résolution
générale de la question de Buehler–Ryskin demanderait un travail
bibliographique et mathématique supplémentaire.

## Références primaires

1. S. Plotkin, *CS361B — Advanced Algorithms*, Stanford, 2014, §7.1 :
   [alternative de Farkas et certificats de faisabilité](https://web.stanford.edu/class/cs361b/files/cs361b-notes.pdf).
2. N. M. Patrikalakis, T. Maekawa, W. Cho, *Shape Interrogation for Computer
   Aided Design and Manufacturing*, §1.3.1–1.3.2 :
   [positivité, partition de l'unité et dérivées de Bernstein](https://web.mit.edu/hyperbook/Patrikalakis-Maekawa-Cho/node9.html).
3. H. Buehler, E. Ryskin, *Discrete Local Volatility for Large Time Steps*,
   version extensive 2.401, §3.3 et annexe A.1 :
   [problème sous bornes et différences sur grilles non uniformes](https://quantitative-research.de/dl/Discrete%20Local%20Volatility%20-%20Extensive.pdf).
