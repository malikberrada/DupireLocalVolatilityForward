# Formulation et portée des garanties

La référence principale depuis 0.1.6 est
[CRITERE_PROUVE.md](CRITERE_PROUVE.md) : alternative exacte sur grille
fixée, construction suffisante et preuve du seuil de raffinement.
La présente note documente les commandes historiques `solve`, `verify`,
`bound` et leurs audits binary64. Les nouveaux chemins `criterion` et
`verify-criterion` assemblent et vérifient les coefficients géométriques
en rationnels depuis les données déclarées, et ne sont donc pas limités
au LP binary64 sauvegardé.

Les variables sont les calls normalisés `c(T,x) = C(T,x F(T))/(D(T) F(T))`,
avec `x = K/F(T)`. Les expériences synthétiques utilisent `F=D=1`.
Pour le marché, `F,D,T`, le style européen et le règlement doivent être fournis
et vérifiés par famille de contrats. L'analyse est conditionnelle à ces valeurs.

## Grille et opérateurs

La grille est commune et irrégulière : `T_j`, `x_i`. L'union des strikes
observés est utilisée. Les nœuds non cotés sont des inconnues ; aucune
interpolation n'est ajoutée aux observations. Ajouter des dates de calcul
ne fabrique aucune nouvelle cotation.

Avec `h- = x_i-x_(i-1)`, `h+ = x_(i+1)-x_i` :

\[
\Gamma_{j,i}=\frac{2}{h^-+h^+}
\left(\frac{c_{j,i+1}-c_{j,i}}{h^+}-\frac{c_{j,i}-c_{j,i-1}}{h^-}\right).
\]

Le LP impose :

- `(1-x)+ <= c <= 1` ; payoff exact à la première tranche si `T_0=0` ;
- pentes entre -1 et 0 ; convexité discrète ; calendriers croissants ;
- convexité du raccord de la première tranche de strikes à `c(T,0)=1` ;
- intervalles bid/ask, y compris les observations dupliquées ou contradictoires ;
- à tous les nœuds spatiaux intérieurs et sur chaque intervalle de temps,

\[
\frac12\underline v_{j,i}x_i^2\Delta T_j\Gamma^*_{j,i}
\le c_{j+1,i}-c_{j,i}
\le\frac12\overline v_{j,i}x_i^2\Delta T_j\Gamma^*_{j,i}.
\]

`Gamma* = Gamma_j` en forward, `Gamma_(j+1)` en backward.
Les variantes sont résolues séparément. Les bornes portent sur `v = sigma²`.
L'interface CLI demande des volatilités décimales et les élève au carré.
L'API `build_lp` accepte aussi des tableaux de bornes par cellule.

Les cellules `Gamma=Theta=0` satisfont les inégalités, mais ne permettent pas
d'identifier une variance. Le quotient y est enregistré `NaN`, jamais zéro
par convention. Un seuil numérique `gamma_tol=1e-12` identifie les quotients
exploitables ; ce seuil ne modifie pas le LP.

## Domaine, bords et non-arbitrage

Par défaut, l'étude porte sur une fenêtre finie en strikes et en maturités.
Les prix des deux extrémités sont des variables, sauf cotations observées.
On ne pose pas artificiellement le dernier call à zéro. Les contraintes de
forme sont nécessaires pour une surface globale sans arbitrage ; une solution
sur cette fenêtre ne certifie ni un prolongement global aux queues ni une
diffusion continue ou un noyau de transition reproduisant les prix.

L'option `--tail-x B` ajoute explicitement un strike `B` à prix zéro pour toutes
les maturités : elle fait l'hypothèse supplémentaire d'un support borné. Elle
change le problème scientifique. Les certificats et rapports enregistrent
cette hypothèse. Elle ne doit pas être utilisée pour prétendre avoir certifié
la surface Black–Scholes globale, dont la queue n'est pas de support borné.

`F0` signifie ici : fourchettes + contraintes de forme enregistrées, sur ce
domaine. `Fh` ajoute les bornes locales du schéma choisi. C'est une formulation
sur grille commune dans l'esprit du problème Buehler–Ryskin ; elle ne reproduit
pas tous leurs opérateurs de transport sur grilles différentes ou leurs noyaux.

## Statuts et certificats

| Statut | Garantie |
| --- | --- |
| `feasible_numeric` | Un témoin passe deux audits CPU indépendants à la tolérance indiquée. |
| `infeasible_certified_binary_lp` | Une inégalité séparatrice est vérifiée en arithmétique rationnelle exacte sur les coefficients binary64 sauvegardés. |
| `infeasible_solver_only` | Le solveur annonce une infaisabilité, sans certificat exact vérifié par ce programme. |
| `indeterminate` | Aucun des résultats précédents n'est établi : limite de temps, problème numérique, etc. |

Les coefficients géométriques sont calculés en double précision. Un certificat
exact concerne donc le LP à coefficients flottants sauvegardé, pas un LP à
coefficients symboliques exacts, ni les prix de marché inconnus. La faisabilité
est numérique : elle n'est pas présentée comme un certificat rationnel exact.

L'audit 1 recalcule `A x - b` et les bornes sans utiliser les résidus du solveur.
L'audit 2 recalcule directement les pentes, Gamma, calendriers et différences
temporelles sans réutiliser les matrices du LP. Les résidus locaux sont mesurés
sur les inégalités multipliées par `DeltaT`, en unités de call normalisé.
Une petite erreur en prix peut induire une grande erreur sur le quotient de
variance quand Gamma est petit : les résidus et les cellules non identifiables
doivent être examinés avec les quotients.

Pour l'infaisabilité, si `A x <= b`, `l <= x <= u` et `y>=0`, alors :

\[
r=A^Ty,\qquad d=b^Ty,\qquad
\min_{l\le x\le u} r^Tx = \sum_j \min(r_jl_j,r_ju_j).
\]

Si ce minimum est strictement supérieur à `d`, le système est impossible.
Le calcul est fait avec `fractions.Fraction`, qui représente exactement les
flottants sauvegardés. Cette correction par la boîte des variables reste
valide lorsque `A^T y` n'est pas exactement nul. Le programme essaie d'abord
le rayon dual de HiGHS, puis un LP de Farkas auxiliaire si nécessaire.
`verify` recharge le modèle, contrôle son SHA-256 et refait tout ce calcul.

`F0` certifié impossible indique une incompatibilité des observations sous les
hypothèses enregistrées. `F0` numériquement faisable et `Fh` certifié impossible
indiquent une incompatibilité conjointe sur cette grille. Une grille plus fine
faisable montre une dépendance au maillage avec un témoin numérique. Plusieurs
échecs ne prouvent aucune inexistence continue. Les ensembles ne sont pas
supposés emboîtés au raffinement.

## Deux relâchements distincts

`--relax` résout d'abord le LP :

\[
\min \varepsilon,\quad
b_k-\varepsilon w_k\le c_k\le a_k+\varepsilon w_k,\quad \varepsilon\ge0.
\]

Par défaut `w_k=max(|ask-bid|/2,1e-5)`, en prix normalisés. Une colonne CSV
`weight` permet d'imposer un tick/une échelle propre à chaque observation.
Le seul élargissement concerne les cotations : les contraintes de forme
et les bornes de variance restent imposées. L'optimum est numérique ; une
limite de temps avec un témoin admissible n'est pas étiquetée optimum.

Ensuite, si `F0` est numériquement faisable, une dichotomie à grille fixe cherche
le plus petit lambda permettant `(vmin-lambda)+ <= vh <= vmax+lambda`.
Chaque lambda fixé définit un LP. La réponse est un intervalle numérique,
en **variance**, avec l'historique de toutes les évaluations. Le bord inférieur
n'est pas annoncé comme un certificat exact d'optimalité. Un statut inconnu
interrompt la dichotomie ; il n'est jamais assimilé à une infaisabilité.
Optimiser lambda et les prix simultanément produirait des produits bilinéaires.

## Borne quantitative conditionnelle sur grille commune

Pour une surface continue supposée donnée, soit :

- `c_xx >= gamma0 > 0` sur tout le rectangle étudié ;
- `|c_xxx| <= M3`, `|c_xxxx| <= M4`, `|c_tt| <= Mtt` sur les segments nécessaires ;
- `0 <= v <= vmax`, `x>=xmin>0` ;
- une marge de variance `delta_v` par rapport aux bornes prescrites.

Taylor donne, pour chaque nœud :

\[
E_\Gamma=\frac{|h^+-h^-|}{3}M_3+
\frac{(h^+)^3+(h^-)^3}{12(h^++h^-)}M_4,
\qquad E_\Theta=\frac{\Delta T}{2}M_{tt}.
\]

Si `E_Gamma < gamma0`, pour le schéma forward au temps gauche ou backward
au temps droit :

\[
|v_h-v|\le
\frac{\Delta T M_{tt}/x_{min}^2+v_{max}E_\Gamma}
{\gamma_0-E_\Gamma}.
\]

Pour la première formule, développer chaque pente jusqu'au terme cubique :
le terme de `c_xxx` vaut `(h+-h-)/3` ; les restes sont majorés par
`(h+³+h-³) M4/[12(h++h-)]`. Pour la seconde formule, écrire
`2 Theta_h/(x² Gamma_h) - v = [2(Theta_h-c_t)/x² - v(Gamma_h-c_xx)]/Gamma_h`
et utiliser le minorant du dénominateur.

Si la borne finale est <= `delta_v`, les échantillons de cette surface
respectent les bornes locales discrètes. Il faut **en plus** que cette surface
soit compatible avec toutes les fourchettes et les hypothèses de bord.
L'outil `bound` cherche un niveau dyadique satisfaisant cette condition, en
diminuant `h-`, `h+` et `DeltaT` simultanément. Les constantes sont fournies par
l'utilisateur : des maxima simplement échantillonnés ne sont pas des bornes
globales certifiées. Cette estimation standard n'est pas revendiquée comme
une nouveauté scientifique ni comme une caractérisation autonome de non-vacuité.

Il n'y a aucun terme d'interpolation temporelle dans cette implémentation sur
grille commune. Un futur transport entre grilles indépendantes devrait traiter
explicitement les erreurs de type `h_interp²/DeltaT`. L'outil ne prétend pas
implémenter ou certifier cette extension.

## Références

- Buehler, H., Ryskin, E. *Discrete Local Volatility for Large Time Steps*,
  version extensive 2.401, §3.3, p. 18 :
  https://quantitative-research.de/dl/Discrete%20Local%20Volatility%20-%20Extensive.pdf
- HiGHS, interface Python et matrices creuses :
  https://ergo-code.github.io/HiGHS/dev/interfaces/python/example-py/
- HiGHS, callbacks : https://ergo-code.github.io/HiGHS/dev/callbacks/
- HiGHS, limitations de la construction GPU : https://ergo-code.github.io/HiGHS/dev/guide/gpu/
- Cboe, SPX/XSP : https://www.cboe.com/en/tradable-products/sp-500/spx-options/
  et https://www.cboe.com/tradable_products/sp_500/mini_spx_options/european_style/
- Source yfinance, `option_chain` : https://github.com/ranaroussi/yfinance/blob/main/yfinance/ticker.py

Les comparateurs Andreasen–Huge, SSVI, SANOS, Tikhonov et les méthodes de
réparation Cohen–Reisinger–Wang ne sont pas implémentés ici. Leur absence ou
leur échec ne serait pas un certificat d'inexistence pour ce problème.
