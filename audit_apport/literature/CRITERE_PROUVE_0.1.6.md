# Proven feasibility and refinement criteria

Engine version **0.1.6**. This note states an exact necessary and sufficient alternative on a fixed finite grid, followed by a constructive sufficient condition and an observation preserving refinement threshold. The proofs concern the constraints below. Floating-point certificate discovery is incomplete; every accepted certificate is checked in exact rational arithmetic.

Theorem 1 here corresponds to manuscript Theorem 1. Theorem 2 here is the sufficient refinement result, numbered Theorem 4 in the manuscript. See [the research guide](../../docs/RESEARCH.md) for the three-strike and endpoint-separation results.

## 1. Observations, normalization, and domain

**O1: fixed normalization.** Observations are European call intervals or put intervals translated into calls by parity. Settlement conventions, year fraction `T`, forward `F(T)>0`, and discount factor `D(T)>0` are fixed for each maturity:

$$
x=K/F(T),\qquad [b,a]=[\mathrm{bid},\mathrm{ask}]/(D(T)F(T)).
$$

A put constrains the **same call** through `[put_bid/(DF)+1-x, put_ask/(DF)+1-x]`. Call and put observations remain distinct intervals; they are not averaged. The result is conditional on normalization. It does not quantify errors in `F,D,T` or establish synchronized quotes.

**O2: finite observations.** There are `N>=1` finite quadruples `(t_k,x_k,b_k,a_k)`. Duplicates remain separate constraints. For Theorem 1, crossed intervals `b_k>a_k` and negative quoted bounds are retained and may imply infeasibility. Theorem 2 requires a witness satisfying every interval, which excludes such contradictions.

**G1: common grid.** Computation uses the Cartesian product

$$
\mathcal G=\{T_0<\cdots<T_m\}\times\{0<x_0<\cdots<x_n\},
\quad m\ge1,\ n\ge2,\ T_0\ge0.
$$

Every observation is exactly a node. Different observed strikes across expiries are permitted: their union supplies the common axis, and unquoted nodes become unknown prices. No observed quote is interpolated. Steps are positive, without a mesh-ratio bound. Moving spatial grids with transport between expiries are outside this formulation.

**G2: finite window.** A convex connection to `(x,c)=(0,1)` is imposed on the left. The final strike price is not fixed to zero. Bounded support and global tail extension define additional problems.

**B1: prescribed bounds.** Theorem 1 permits finite cellwise **variance** bounds `0<=v_min[j,i]<=v_max[j,i]`, including equality. CLI inputs are volatilities, squared to obtain variance. Theorem 2 uses distinct constant bounds and an explicit interior margin. `finite_criterion.Problem` accepts cellwise arrays; `criterion` searches with scalar CLI bounds; `verify-criterion` honors the arrays in the saved problem.

These declarations define a mathematical problem. Downloaded observations are not thereby asserted to be exact arbitrage-free market prices.

## 2. Fixed-grid constraints

The unknowns are normalized calls `c[j,i]`. Define

$$
h_i^-=x_i-x_{i-1},\quad h_i^+=x_{i+1}-x_i,\quad
s_{j,i}=\frac{c_{j,i+1}-c_{j,i}}{x_{i+1}-x_i},
$$

$$
\Gamma_{j,i}=\frac{2}{h_i^-+h_i^+}
\left(\frac{c_{j,i+1}-c_{j,i}}{h_i^+}-\frac{c_{j,i}-c_{j,i-1}}{h_i^-}\right),
\qquad \Theta_{j,i}=\frac{c_{j+1,i}-c_{j,i}}{\Delta T_j}.
$$

`F0` imposes:

1. `(1-x_i)^+ <= c[j,i] <= 1`, with the exact payoff on the first row if `T_0=0`;
2. `-1 <= s[j,i] <= 0` and `Gamma[j,i]>=0`;
3. `c[j+1,i]>=c[j,i]` at every strike;
4. `(c[j,0]-1)/x_0 <= s[j,0]`, the convex left connection;
5. `b_k <= c[j(k),i(k)] <= a_k` for **every** observation.

For stencil `s`, `F_s` additionally imposes

$$
\tfrac12\underline v_{j,i}x_i^2\Delta T_j\Gamma^s_{j,i}
\le c_{j+1,i}-c_{j,i}
\le\tfrac12\overline v_{j,i}x_i^2\Delta T_j\Gamma^s_{j,i}.
\tag{L}
$$

`Gamma^forward[j,i]=Gamma[j,i]`; `Gamma^backward[j,i]=Gamma[j+1,i]`. `F_joint` imposes both on **one price vector**. Two separately feasible vectors do not establish a nonempty intersection.

At `Gamma=0`, (L) requires zero time increment and remains well-defined. It identifies no variance quotient. Strictly positive gamma is needed to identify variance everywhere; Theorem 2 establishes it on its witness.

## 3. Theorem 1: exact alternative on a fixed grid

Under O1-O2, G1-G2, and B1, choose `F0`, `F_forward`, `F_backward`, or `F_joint`. Write its non-box constraints as

$$
Ac\le b,\qquad l\le c\le u,\tag{P}
$$

where `l[j,i]=(1-x_i)^+`, `u[j,i]=1`, and the first row's upper and lower bounds agree if `T_0=0`. The coefficients are explicitly computable from geometry, observations, and variance bounds. The box is compact and nonempty.

**Statement.** Exactly one alternative holds:

- a price vector `c` satisfies (P);
- a vector `lambda>=0` satisfies

$$
\sum_q\min\{r_ql_q,r_qu_q\}>\lambda^Tb,
\qquad r=A^T\lambda.\tag{S}
$$

For rational data, the relevant witness can be chosen rational. The box term accounts exactly for a nonzero dual residual `A^T lambda`.

### Proof

If `c` is feasible and `lambda>=0`,

$$
\sum_q\min\{r_ql_q,r_qu_q\}\le r^Tc
=\lambda^TAc\le\lambda^Tb.
$$

Thus (S) excludes feasibility. Conversely, put `B=[l,u]` and `K={Ac+s:c in B,s>=0}`. The set is nonempty, convex, and closed: `AB` is compact and its sum with the closed orthant is closed. Feasibility is equivalent to `b in K`.

If `b` lies outside `K`, let `z` be its projection onto `K` and set `lambda=z-b`. Projection gives `lambda^T(k-z)>=0` for every `k in K`. Since `z+t*e_i in K` for every `t>=0`, each component of `lambda` is nonnegative. Furthermore,

$$
\min_{k\in K}\lambda^Tk=\lambda^Tz
=\lambda^Tb+\|z-b\|^2>\lambda^Tb.
$$

For nonnegative `lambda`, this minimum is `min_{c in B} lambda^T A c`, exactly the left side of (S).

For rational inputs, a nonempty compact rational polytope has a rational vertex, obtainable by solving rational active constraints. In the infeasible case, the strict gap persists under a sufficiently close rational approximation to `lambda` within the nonnegative orthant. Both forms of evidence can therefore be finite and rational. This is a bounded-variable form of the classical Farkas alternative.

### Verification and diagnosis

`finite_criterion.py` assembles coefficients **directly as rationals**. Floating-point matrices are used only for discovery. Positive witnesses are checked against every exact row and box bound; negative witnesses are checked by (S) on the same exact system.

`criterion --quotes` interprets CSV decimals exactly. `--logical-grid` uses declared rational coordinates before rounding, including the collector's `F0.exact_grid.json`. SHA-256 binds the full problem: grid, observations, bounds, stencil, and provenance. It does not authenticate an external provider.

| Verified result | Justified conclusion |
|---|---|
| `F0` infeasible | Observations and shape restrictions conflict under the fixed normalization |
| `F0` feasible, `F_s` infeasible | Those observations conflict with the chosen bounds and grid |
| `F_joint` feasible | One witness satisfies both stencils on that grid |
| No exact witness recovered | `not_certified`; feasibility and infeasibility remain undecided |

The second row does not by itself determine whether bounds or geometry should change. A feasible new grid with **the same observations** demonstrates a grid effect. Dropping observations or widening intervals changes the problem.

The theorem is a complete alternative. Numerical certificate discovery is not a complete exact decision algorithm: time limits, degeneracy, or failed rational reconstruction can produce `not_certified` despite mathematical existence of a certificate.

## 4. Theorem 2: sufficient condition and explicit refinement

Let `R=[T_a,T_b] x [x_a,x_b]` be an interior rectangle with `T_a>0`, `x_a>0`, containing all observations and the base grid, with matching endpoints. Suppose a rational polynomial `P(T,x)` has been **constructed and certified** on `R` to satisfy

$$
\begin{gathered}
(1-x)^+\le P\le1,\quad -1\le P_x\le0,\quad P_{xx}\ge\gamma_0>0,\\
1-P(T,x_a)+x_aP_x(T,x_a)\ge0,\qquad b_k\le P(t_k,x_k)\le a_k,\\
0\le v_{\min}<v_{\max}<\infty,\quad 0<2\delta<v_{\max}-v_{\min},\\
v_{\min}+\delta\le\frac{2P_T}{x^2P_{xx}}\le v_{\max}-\delta.
\end{gathered}\tag{C}
$$

Also certify global bounds `|P_xxx|<=M3`, `|P_xxxx|<=M4`, and `|P_TT|<=Mtt`. Numerical derivative samples alone do not establish these bounds. Section 5 supplies a finite sufficient certificate.

For the base axes, define

$$
H=\max_i(x_{i+1}-x_i),\quad
D_h=\max_i|(x_{i+1}-x_i)-(x_i-x_{i-1})|,\quad
\tau=\max_j\Delta T_j.
$$

At level `ell`, subdivide **every** original spatial and temporal interval into `r=2^ell` equal parts. Set

$$
a=\frac{D_hM_3}{3},\quad b=\frac{H^2M_4}{12},\quad
 d=\frac{\tau M_{TT}}{x_a^2},\qquad
A=d+(v_{\max}+\delta)a,\quad
B=(v_{\max}+\delta)b,\quad C=\delta\gamma_0>0.
$$

**Statement.** Under (C) and the certified derivative bounds,

$$
Cr^2-Ar-B\ge0,\qquad r=2^\ell\tag{Q}
$$

guarantees `c[j,i]=P(T_j,x_i) in F_joint` on the refined grid, with strictly positive interior gammas. The **same polynomial**, original observations, and variance bounds work at every subsequent dyadic level.

An explicit sufficient threshold is

$$
r_* = \frac{A+\sqrt{A^2+4BC}}{2C},\qquad
\ell_* = \min\{\ell\in\mathbb N_0:2^\ell\ge\max(1,r_*)\}.
$$

A looser rational-only integer bound is

$$
R_0=\max\left(1,\left\lceil\frac{A+B}{C}\right\rceil\right),
\qquad \ell_*\le\lceil\log_2R_0\rceil.\tag{U}
$$

The implementation tests (Q) in rationals and reports (U), including when a search cap prevents enumerating every level. This is a threshold for the **sufficient estimate**, not the earliest grid admitting any calibration.

### Proof

Taylor expansion of the two spatial slopes gives

$$
|\Gamma_h(T,x_i)-P_{xx}(T,x_i)|
\le\frac{|h_i^+-h_i^-|M_3}{3}
+\frac{(h_i^+)^3+(h_i^-)^3}{12(h_i^++h_i^-)}M_4.\tag{E1}
$$

The constant and linear price terms cancel in the second difference. The cubic term is `(h_i^+-h_i^-)*P_xxx/3`. Each fourth-order price remainder is bounded by `M4*h^4/24`; division by the step and by `(h_i^++h_i^-)/2` gives the second term in (E1).

At an original node, adjacent steps scale by `1/r`; at a new node inside an original interval, the steps are equal. Since `(p^3+q^3)/(p+q)=p^2-p*q+q^2<=max(p,q)^2`, the uniform spatial error is at most

$$
e_r=a/r+b/r^2.
$$

At **either** temporal endpoint `T_*`, the time difference is the average of `P_T`. Hence

$$
|\Theta_h-P_T(T_*,x_i)|\le\frac{\tau M_{TT}}{2r}.\tag{E2}
$$

For `e_r<gamma0`, `Gamma_h>=gamma0-e_r>0`. Use `v=2*P_T/(x_i^2*P_xx)` and both derivatives at the same temporal endpoint:

$$
\frac{2\Theta_h}{x_i^2\Gamma_h}-v
=\frac{2(\Theta_h-P_T)/x_i^2-v(\Gamma_h-P_{xx})}{\Gamma_h}.
$$

Equations (E1)-(E2), `x_i>=x_a`, and `0<=v<=v_max` imply

$$
|v_h-v|\le\frac{d/r+v_{\max}e_r}{\gamma_0-e_r}.\tag{E3}
$$

Condition (Q) is exactly `d/r+(v_max+delta)*e_r<=delta*gamma0`. It implies `e_r<=delta*gamma0/(v_max+delta)<gamma0` and makes (E3) at most `delta`. The interior margin then puts the forward ratio at the left endpoint and the backward ratio at the right endpoint inside the prescribed bounds, for the **same sampled prices**.

Discrete slopes are averages of `P_x`, so they lie in `[-1,0]`; convexity follows from positive `P_xx`. The continuous variance margin gives `P_T>0`, hence increasing calendars. The left connection follows from

$$
\frac{P(T,x_a)-1}{x_a}\le P_x(T,x_a)
\le\frac{P(T,x_1)-P(T,x_a)}{x_1-x_a}.
$$

Other price bounds and all observed intervals follow by evaluating `P` at retained nodes. Finally, `A,B>=0` and `C>0`; the quadratic stays nonnegative above its positive root. For `r>=1`, `Ar+B<=(A+B)r`, proving (U). When `A=B=0`, level zero suffices. This establishes finite mathematical termination and every stated conclusion.

## 5. Finite certification from observations and bounds

For degrees `p>=1`, `q>=2`, search for rational coefficients of

$$
P_\alpha(T,x)=\sum_{a=0}^p\sum_{b=0}^q\alpha_{ab}
B_a^p\left(\frac{T-T_a}{T_b-T_a}\right)
B_b^q\left(\frac{x-x_a}{x_b-x_a}\right).
$$

Let `B(f)` denote Bernstein coefficients after degree elevation when needed. The following are finite **linear inequalities in alpha**:

$$
\begin{aligned}
&b_k\le P_\alpha(t_k,x_k)\le a_k,\\
&\mathcal B(P_\alpha),\ \mathcal B(P_\alpha-1+x),\ \mathcal B(1-P_\alpha)\ge0,\\
&\mathcal B(-P_{\alpha,x}),\ \mathcal B(1+P_{\alpha,x})\ge0,\\
&\mathcal B(P_{\alpha,xx}-g)\ge0\quad(g>0),\\
&\mathcal B(P_{\alpha,T}-\tfrac12(v_{\min}+\delta)x^2P_{\alpha,xx})\ge0,\\
&\mathcal B(\tfrac12(v_{\max}-\delta)x^2P_{\alpha,xx}-P_{\alpha,T})\ge0,\\
&\mathcal B_T(1-P_\alpha(T,x_a)+x_aP_{\alpha,x}(T,x_a))\ge0.
\end{aligned}\tag{BC}
$$

The implementation supports `1<=p<=8`, `2<=q<=20`; the theorem allows any finite polynomial degree.

**Constructive corollary.** A rational vector satisfying (BC), together with a grid satisfying (Q), gives a finite sufficient criterion directly linked to the observations and local bounds.

**Proof.** Bernstein basis functions are nonnegative and sum to one. Nonnegative coefficients imply a nonnegative polynomial throughout the rectangle. Thus (BC) implies (C), and it certifies

$$
\gamma_0=\min\mathcal B(P_{\alpha,xx})\ge g,\quad
M_3=\max|\mathcal B(P_{\alpha,xxx})|,\quad
M_4=\max|\mathcal B(P_{\alpha,xxxx})|,\quad
M_{TT}=\max|\mathcal B(P_{\alpha,TT})|.
$$

All constants and (Q) are rationally computable, so Theorem 2 applies.

This condition is sufficient at fixed degree. Failure proves neither discrete infeasibility nor absence of another regular surface. The fit receives observations only; the demonstration generator's coefficients are not supplied to it.

## 6. Commands and authoritative arithmetic

Use the environment established in the root README. The archived accepted logical grid provides a reproducible example:

```powershell
& $PyDupire -u -m dupire_joint criterion `
  --logical-grid reference/market/grids/F0.exact_grid.json `
  --scheme joint --sigma-min 0.05 --sigma-max 1.0 --threads 4 `
  --out runs/criterion

& $PyDupire -u -m dupire_joint verify-criterion `
  --problem runs/criterion/criterion.problem.json `
  --certificate runs/criterion/criterion.certificate.json `
  --logical-grid reference/market/grids/F0.exact_grid.json `
  --out runs/criterion_verified

& $PyDupire -u -m dupire_joint construct --demo --device cpu `
  --degree-time 2 --degree-space 4 --threads 4 --out runs/constructive

& $PyDupire -u -m dupire_joint verify-construct `
  --certificate runs/constructive/constructive.certificate.json `
  --quotes runs/constructive/observations.csv `
  --out runs/constructive_verified
```

Use `criterion --quotes PATH.csv` for other normalized observations. `--space-level` and `--time-level` preserve every observed row but alone provide no feasibility guarantee. Once certified, Theorem 2 guarantees levels beyond its sufficient threshold without resolving a nodal LP at every level.

| Path | Authoritative arithmetic |
|---|---|
| `criterion --quotes` | CSV decimals interpreted as exact rationals |
| `criterion --logical-grid` | Declared JSON rationals before numerical rounding |
| `construct`, `verify-construct` | Exact rational representations of CSV binary64 values; bound and margin parameter strings interpreted exactly since 0.1.6 |
| Historical `solve`, `verify` | Stored binary64 LP and the audits described in [MATHEMATICS.md](../../docs/MATHEMATICS.md) |

Constructive NPZ exports are rounded and audited separately. The proof concerns the rational polynomial and axes in `mesh.exact.json`. `--max-nodes` limits export size, without invalidating the theoretical threshold. `construction.json` records `quadratic_criterion`, constants, and exact tested margins. `verify-construct` recomputes them from the witness.

| Command | Exit code | Meaning |
|---|---:|---|
| `criterion` | 0 | Exact feasibility |
| `criterion` | 4 | Exact infeasibility of the declared problem |
| `criterion` | 3 | Not certified |
| `criterion` | 2 | Input or execution error |
| `verify-criterion` | 0 | Valid certificate, whether positive or negative |

Verify a negative `F0` result with `F0.problem.json` and `F0.certificate.json`.

## 7. Scientific scope and references

Theorem 1 characterizes the declared finite system. Theorem 2 gives a sufficient condition on a regular witness class with quantified observation preserving refinement. It does not assume nested feasible sets.

Theorem 2 excludes `T=0`, zero gamma, cellwise variance bounds, and moving spatial grids. Neither theorem establishes a global tail extension, a martingale diffusion, robustness over every possible nominal curve, or consistency of an entire raw Yahoo chain after selection. Selecting strikes in multiples of 50 restricts observations; it is different from the observation preserving subdivision in Theorem 2.

Convex separation, Bernstein positivity, and Taylor estimates are classical tools. General priority or a complete solution of the broader Buehler-Ryskin question is not established by these computations.

Primary references retained from the original note:

1. S. Plotkin, *CS361B Advanced Algorithms*, Stanford, 2014, Section 7.1: [Farkas alternative and certificates](https://web.stanford.edu/class/cs361b/files/cs361b-notes.pdf).
2. N. M. Patrikalakis, T. Maekawa, and W. Cho, *Shape Interrogation for Computer Aided Design and Manufacturing*, Sections 1.3.1-1.3.2: [Bernstein properties and derivatives](https://web.mit.edu/hyperbook/Patrikalakis-Maekawa-Cho/node9.html).
3. H. Buehler and E. Ryskin, *Discrete Local Volatility for Large Time Steps*, extensive version 2.401, Section 3.3 and Appendix A.1: [full text](https://quantitative-research.de/dl/Discrete%20Local%20Volatility%20-%20Extensive.pdf).
