# Numerical LP formulation and certificate scope

For exact geometry from declared inputs, use [CRITERE_PROUVE.md](CRITERE_PROUVE.md): `criterion` and `verify-criterion` assemble and check rational coefficients directly. This note documents the historical `solve`, `verify`, and `bound` commands and their **binary64 LP** audits.

Normalized calls are `c(T,x)=C(T,x*F(T))/(D(T)*F(T))`, with `x=K/F(T)`. Synthetic experiments use `F=D=1`. Market normalization requires declared and checked forward, discount, time, European exercise, and settlement conventions for each contract family. Every conclusion is conditional on them.

## Grid and operators

Use a common irregular grid `T_j,x_i`, taking the union of observed strikes. Unquoted nodes are unknowns. Adding computation dates creates no new observations. For `h_minus=x_i-x_(i-1)` and `h_plus=x_(i+1)-x_i`,

$$
\Gamma_{j,i}=\frac{2}{h^-+h^+}
\left(\frac{c_{j,i+1}-c_{j,i}}{h^+}-\frac{c_{j,i}-c_{j,i-1}}{h^-}\right).
$$

The LP imposes price bounds `(1-x)^+<=c<=1`, exact first-row payoff if `T_0=0`, slopes in `[-1,0]`, discrete convexity, increasing calendars, a convex left connection to `(0,1)`, and every observed interval, including duplicates or contradictions. At interior spatial nodes,

$$
\tfrac12\underline v_{j,i}x_i^2\Delta T_j\Gamma^*_{j,i}
\le c_{j+1,i}-c_{j,i}
\le\tfrac12\overline v_{j,i}x_i^2\Delta T_j\Gamma^*_{j,i}.
$$

Forward uses `Gamma_j`; backward uses `Gamma_(j+1)`. The historical variants are solved separately. Bounds concern **variance** `v=sigma^2`; the CLI squares decimal volatility inputs. `build_lp` also accepts cellwise bound arrays.

When `Gamma=Theta=0`, the inequalities hold but variance is unidentified. Quotients are stored as `NaN`, not zero. The numerical `gamma_tol=1e-12` identifies usable quotients without changing the LP.

## Finite domain and boundaries

Boundary prices remain variables unless observed. The last strike call is not artificially zero. The finite-window shape restrictions are necessary for a global arbitrage-free surface, but feasibility here proves no global tail extension, continuous diffusion, or transition kernel.

`--tail-x B` explicitly adds a zero-priced strike at every maturity, imposing bounded support and changing the problem. Reports and certificates record this assumption. It does not certify the global Black-Scholes tail, whose support is unbounded.

`F0` denotes intervals plus the recorded finite-window shape restrictions. `Fh` adds the chosen local stencil's bounds. This common-grid formulation does not reproduce every Buehler-Ryskin moving-grid transport or transition-kernel construction.

## Status values and evidence

| Status | Guarantee |
|---|---|
| `feasible_numeric` | A witness passes two independent CPU audits at the declared tolerance |
| `infeasible_certified_binary_lp` | A separating inequality is checked in exact rational arithmetic on the stored binary64 coefficients |
| `infeasible_solver_only` | Solver reports infeasibility, without an exact certificate verified by this program |
| `indeterminate` | No preceding result established, for example because of a time limit or numerical failure |

On this historical path, geometry is computed in double precision. An exact negative certificate therefore concerns the **stored floating-point LP**, not symbolic geometry or unknown true market prices. Positive feasibility is numerical.

Audit 1 recomputes `A*x-b` and box residuals without trusting solver residuals. Audit 2 directly recomputes slopes, gamma, calendars, and time increments without reusing LP matrices. Local residuals are measured after multiplication by `DeltaT`, in normalized call-price units. Small price residuals can imply large variance-quotient errors when gamma is small; inspect residuals and unidentified cells alongside ratios.

For `A*x<=b`, `l<=x<=u`, and `y>=0`, set

$$
r=A^Ty,\qquad d=b^Ty,\qquad
\min_{l\le x\le u}r^Tx=\sum_j\min(r_jl_j,r_ju_j).
$$

If the minimum exceeds `d`, the system is infeasible. `fractions.Fraction` represents the stored floats exactly. This box correction remains valid even when `A^T*y` is not exactly zero. The program first tries the HiGHS dual ray, then an auxiliary Farkas LP if needed. `verify` reloads the model, checks SHA-256, and repeats the calculation.

Certified infeasible `F0` means observations conflict with the recorded assumptions. Numerically feasible `F0` and certified infeasible `Fh` identify incompatibility of observations, bounds, and grid. A feasible refinement supplies numerical evidence of a grid effect for that instance. Repeated failures do not prove continuous nonexistence; feasible sets are not assumed nested.

## Two different relaxations

With `--relax`, the first LP minimizes quote widening:

$$
\min\varepsilon,\quad b_k-\varepsilon w_k\le c_k\le a_k+\varepsilon w_k,
\quad\varepsilon\ge0.
$$

Default `w_k=max(|ask-bid|/2,1e-5)` is in normalized prices. An optional CSV `weight` sets an observation-specific tick or scale. Only quote intervals widen; shape and variance bounds remain imposed. The optimum is numerical. A time-limited feasible candidate is not labeled an optimum.

If `F0` is numerically feasible, fixed-grid bisection then searches for the smallest `lambda` allowing `(vmin-lambda)^+<=vh<=vmax+lambda`. Each fixed `lambda` defines an LP. The result is a numerical interval in **variance units**, with evaluation history. Its lower endpoint is not an exact optimality certificate. An unknown status stops bisection rather than being treated as infeasible. Joint optimization in prices and `lambda` would be bilinear.

## Conditional quantitative estimate

For an assumed continuous surface on the whole rectangle, require `c_xx>=gamma0>0`, derivative bounds `|c_xxx|<=M3`, `|c_xxxx|<=M4`, `|c_tt|<=Mtt`, `0<=v<=vmax`, `x>=xmin>0`, and a variance margin `delta_v` from the prescribed limits.

Taylor bounds give

$$
E_\Gamma=\frac{|h^+-h^-|}{3}M_3+
\frac{(h^+)^3+(h^-)^3}{12(h^++h^-)}M_4,
\qquad E_\Theta=\frac{\Delta T}{2}M_{tt}.
$$

If `E_Gamma<gamma0`, the forward ratio at the left endpoint or backward ratio at the right endpoint satisfies

$$
|v_h-v|\le\frac{\Delta T M_{tt}/x_{\min}^2+v_{\max}E_\Gamma}
{\gamma_0-E_\Gamma}.
$$

The cubic spatial term is `(h_plus-h_minus)*c_xxx/3`; fourth-order remainders give the other gamma term. The quotient identity

$$
\frac{2\Theta_h}{x^2\Gamma_h}-v
=\frac{2(\Theta_h-c_t)/x^2-v(\Gamma_h-c_{xx})}{\Gamma_h}
$$

gives the variance estimate using a positive denominator bound. If it is at most `delta_v`, samples satisfy the discrete local bounds **provided the surface also satisfies all observed intervals and boundary assumptions**.

`bound` searches for a dyadic level by reducing adjacent spatial steps and the time step together. User-supplied derivative constants must be certified global bounds; sampled maxima do not suffice. This standard estimate is not a standalone data-only nonemptiness criterion. The constructive path in [CONSTRUCTIVE.md](CONSTRUCTIVE.md) instead computes and certifies a polynomial witness.

No temporal interpolation term occurs on this common grid. A future moving-grid transport would need to account explicitly for terms such as `h_interp^2/DeltaT`.

## References and comparisons

- [Buehler-Ryskin, extensive version 2.401](https://quantitative-research.de/dl/Discrete%20Local%20Volatility%20-%20Extensive.pdf), Section 3.3, page 18.
- HiGHS: [Python interface](https://ergo-code.github.io/HiGHS/dev/interfaces/python/example-py/), [callbacks](https://ergo-code.github.io/HiGHS/dev/callbacks/), and [GPU guide](https://ergo-code.github.io/HiGHS/dev/guide/gpu/).
- Cboe: [SPX](https://www.cboe.com/en/tradable-products/sp-500/spx-options/) and [European-style XSP](https://www.cboe.com/tradable_products/sp_500/mini_spx_options/european_style/).
- [yfinance `option_chain` source](https://github.com/ranaroussi/yfinance/blob/main/yfinance/ticker.py).

The engine does not implement Andreasen-Huge, SSVI, SANOS, Tikhonov, or the full Cohen-Reisinger-Wang repair framework as general calibration comparators. The separate positioning module includes limited, explicitly adapted experiments. A comparator's absence or numerical failure is not a nonexistence certificate for this problem.
