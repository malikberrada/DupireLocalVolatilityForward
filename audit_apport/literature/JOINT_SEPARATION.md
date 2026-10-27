# Separate feasibility, intersection, and temporal refinement

Mathematical companion 0.3.0, dated 27 October 2026, for the finite system in engine 0.1.6. The lemmas below establish the stated rational example. Midpoint stepping, finite differences, interval intersections, and Farkas separation are classical; general bibliographic priority is not asserted.

The later [research guide](../../docs/RESEARCH.md) also records the complete terminal-interval characterization and the ten-term endpoint-preservation certificate from `analyse_dependances/`.

## 1. Compatibility of both local constraints

In one cell, put `d=c[j+1,i]-c[j,i]`, `a=x_i^2*DeltaT/2>0`, `g0=Gamma[j,i]`, and `g1=Gamma[j+1,i]`, with nonnegative gammas and the same variance bounds `0<=l<=u` for both stencils.

**Lemma 1.** The four local inequalities are equivalent to

$$
al\max(g_0,g_1)\le d\le au\min(g_0,g_1).
$$

**Proof.** Take the larger lower bound and the smaller upper bound. The equivalence includes zero gamma. If `l>0` and both gammas are positive, an admissible increment requires `max(g0,g1)/min(g0,g1)<=u/l`. This gamma-ratio test alone does not establish that the increment already determined by a price vector lies inside the interval.

Two different vectors, each feasible for one stencil, are therefore insufficient to establish joint feasibility. Section 4 gives an exact counterexample with positive spreads and irregular strikes.

## 2. Three strikes with constant neighbors

Let `x0<x1<x2`, `h_minus=x1-x0`, `h_plus=x2-x1`, and `kappa=2/(h_minus*h_plus)>0`. Neighboring prices are constant. With initial central gamma `g0>0`, a central increment `d` gives

$$
g_1=g_0-\kappa d.
$$

**Lemma 2.** For `0<l<u`, a free central endpoint satisfies both stencils if and only if

$$
\Delta T\le\frac{2(u-l)}{x_1^2\kappa lu}.\tag{T}
$$

If the initial slice satisfies `F0`, the construction below preserves shape. A final central quote interval must still be checked. The later complete characterization adds that terminal-interval condition explicitly.

**Proof.** Set `a=x1^2*DeltaT/2`. Forward-lower gives `d>=a*l*g0`; backward-upper gives `d<=a*u*g0/(1+a*u*kappa)`. The other two bounds are weaker because `0<g1<=g0`. The interval is nonempty exactly when `l*(1+a*u*kappa)<=u`, which is (T).

Take the harmonic mean `v_star=2*l*u/(l+u)`, and set

$$
z=\frac{\kappa x_1^2\Delta T v_*}{4},\qquad
\rho=\frac{1-z}{1+z},\qquad g_1=\rho g_0,\qquad
 d=\frac{g_0-g_1}{\kappa}.
$$

Under (T), `z<1`, and the ratios are

$$
v_f=\frac{v_*}{1+z},\qquad v_b=\frac{v_*}{1-z},
\qquad v_f,v_b\in[l,u].
$$

The update is the classical implicit midpoint rule for the scalar gamma equation. The central price increases but remains below the neighbor chord. New slopes remain between the initial slopes and keep their order, so bounds `[-1,0]`, convexity, price boxes, and the connection to `(0,1)` are retained.

For **moving neighbors**, define

$$
q=\frac{2}{h_-+h_+}
\left(\frac{\Delta c_0}{h_-}+\frac{\Delta c_2}{h_+}\right).
$$

Then `g1=g0+q-kappa*d`. Combining forward-lower with multiplier `1+a*kappa*u` and backward-upper with multiplier 1 gives

$$
a\{l(1+a\kappa u)-u\}g_0-auq\le0.\tag{O}
$$

A strictly positive minimum of the left side over the quote intervals proves that every joint selection is impossible. Positive quote multipliers then complete a rational separator. This is the positive-spread version: it does not assume that all permitted neighboring prices are constant.

## 3. Construction at all later temporal levels

Fix total duration `D`, the three strikes, and constant neighboring prices. Divide time into `r` equal steps; use `z_r=kappa*x1^2*D*v_star/(4*r)`, `rho_r=(1-z_r)/(1+z_r)`, and `g_j=g0*rho_r^j`.

**Lemma 3.** Both stencils are admissible in every cell once

$$
r\ge R_*:=\frac{\kappa x_1^2Dlu}{2(u-l)}.
$$

For the certified family, additionally `lambda=kappa*x1^2*D*v_star/2` lies in `(0,1)`. Uniformly over admissible `r`,

$$
\frac{g_0}{\kappa}\frac{\lambda}{1+\lambda}
\le c_r-c_0\le\frac{g_0}{\kappa}\lambda.\tag{I}
$$

**Proof.** Apply (T) to each step `D/r`. Since `2*r*z_r=lambda`, Bernoulli inequalities give

$$
\rho_r^r\ge1-\frac{2rz_r}{1+z_r}\ge1-\lambda,
\qquad
\rho_r^{-r}=\left(1+\frac{2z_r}{1-z_r}\right)^r\ge1+\lambda.
$$

Thus `1-lambda<=rho_r^r<=1/(1+lambda)`, proving (I). Intermediate centers remain between the initial center and the maximum terminal increment; Lemma 2 preserves shape. It suffices for the final central interval to contain (I) and for constant neighbors to lie in their observed intervals. These conditions are checked exactly for accepted candidates.

This refines **time only** with a nodal midpoint witness. It differs from the polynomial space-time theorem in [CRITERE_PROUVE_0.1.6.md](CRITERE_PROUVE_0.1.6.md); the latter's continuous assumptions are not automatically assigned to the nodal witness.

## 4. Certified instance

Dates are `[1/4,7/20]`, strikes `[9/10,1,27/25]`, variance bounds `l=3/100`, `u=1/25`, and initial midpoint prices `[41/400,1/20,29/2500]`.

The three initial observations are those prices plus or minus `1/1000000`. The neighbors have the same intervals at the final date; the final central interval is `[1/20+1/2000,1/20+11/10000]`. All six intervals have positive width and remain unchanged across systems.

| System | Central increment or proof |
|---|---|
| Forward only | `d=3/3500`; forward variance `6/175`, backward variance `3/50` outside the bounds |
| Backward only | `d=3/5000`; backward variance `6/175`, forward variance `3/125` outside the bounds |
| Coarse intersection | Seven-row dual; exact gap `991/8000000>0` |
| One time halving | Exact joint primal on a `3x3` grid with the same six observations |

The coarse dual combines forward-lower with multiplier `3/2`, backward-upper with multiplier `1`, and five quote constraints. It excludes **every** price vector in the interval box, not just the two displayed witnesses.

Here `kappa=250`, `v_star=6/175`, `lambda=3/7`, and the time threshold is `1/15`. The original step `1/10` exceeds it, while half-step `1/20` satisfies it. `R_star=3/2`, so the first admissible dyadic factor is 2. The refined witness has `z=3/28`, `rho=25/31`, and terminal increment `84/120125`.

The uniform interval `[3/5000,3/3500]` in (I) lies inside the observed terminal increment interval `[1/2000,11/10000]`. Thus the construction preserves observations at every temporal dyadic level `ell>=1`.

The first feasible dyadic level is exactly 1: level zero is excluded by the dual and level one certified by the primal. Two dates and three strikes are minimal for these declared two-time theta and three-strike gamma stencils. No minimality over other model or certificate classes is asserted.

## 5. Additional endpoint-preservation separation

The later standard-library dossier strengthens the comparison over the entire positive-spread box:

$$
c_{\mathrm{final}}^{\mathrm{coarse\ backward}}
\le\frac{50669}{1000000}
<\frac{1297357}{25600000}
\le c_{\mathrm{final}}^{\mathrm{refined\ joint}}.
$$

The gap is `1153/128000000`. A ten-term exact dual additionally rules out the refined joint system combined with the coarse backward upper constraint on identical endpoints, with margin `4739/384000000`. It separates one-halving joint recovery from preserving a coarse backward terminal price. Buehler-Ryskin's option of recalibrating on the finer grid remains compatible with this result.

For a prescribed terminal interval in the constant-neighbor class, the exact reachable increment interval after arbitrary time steps is given in [the research guide](../../docs/RESEARCH.md), with rational construction in [the dependency dossier](../../analyse_dependances/README.txt). The example's two-half-step interval is `[87/128000,9/12500]`.

## 6. Interpretation and checking

This example establishes that separate fits do not replace an intersection check and that subdivision can restore joint compatibility without changing observed intervals. It provides a targeted mathematical result, not a general priority certificate.

The recorded source comparisons include [Buehler-Ryskin](https://quantitative-research.de/dl/Discrete%20Local%20Volatility%20-%20Extensive.pdf), [Kundu-Kumar-Tomar](https://link.springer.com/article/10.1007/s10614-023-10368-5), [Zhang 2025](https://arxiv.org/html/2511.09175v1), and [Austing 2020](https://www.risk.net/media/download/1053071/download). The targeted review has not established general priority of these lemmas or the example.

The independent verifier reconstructs inequalities and checks the four certificates using Python's standard library. It does not replace source reading. From the repository root:

```powershell
& $PyDupire -I -S analyse_dependances/verifier_dependances.py `
  --verify-json analyse_dependances/preuves_dependances.json
```
