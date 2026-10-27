# Research results and manuscript scope

**Dupire Local Volatility: Joint Feasibility and Observation Preserving Refinement** studies European call prices on a common irregular Cartesian grid. Normalization, retained bid-ask intervals, boundary conventions, and variance bounds define the finite problem.

The manuscript's computation record is pinned to commit `173d1cf0c941a14669bb14fd65ac438f7796a0de`, engine version `0.1.6`. Documentation revisions do not change those archived inputs.

## Questions and answers

| Question | Result | Scope |
|---|---|---|
| Can fixed-grid feasibility be characterized exactly? | A price witness or a strict rational separating certificate supplies an exact alternative. | The declared finite system; numerical certificate discovery remains incomplete. |
| Does separate feasibility imply joint feasibility? | No. A positive-spread example has two feasible individual systems and an empty intersection. | One price vector must satisfy both endpoint stencils. |
| Can subdivision restore joint feasibility with the same observations? | Yes in the certified example; an exact reachability criterion covers the constant-neighbor three-strike class. | Observed intervals are retained, while selected prices may change. |
| Can the old calibrated endpoint always be preserved? | No. Every refined joint endpoint exceeds every coarse backward endpoint in the example. | One temporal halving and the specified bounds and spread box. |
| Is there an explicit sufficient refinement rule on broader grids? | Yes, given a certified regular polynomial witness with positive gamma and a variance margin. | Interior rectangle, common grid, constant variance bounds, coupled space-time refinement. |
| Does this solve the entire motivating open problem? | It gives a constructive answer to restricted formulations. | A general data-only criterion for the full Buehler-Ryskin framework is not established. |

## Correspondence between the manuscript and repository

| Manuscript result | Repository label or implementation | Main guide |
|---|---|---|
| Theorem 1: exact fixed-grid alternative | `criterion`, `verify-criterion` | [Exact criteria](CRITERE_PROUVE.md), Theorem 1 |
| Theorem 2: exact terminal reachability | Three-strike extension of C3; `caracterisation_trois_strikes.json` | [Proof reconstruction](../analyse_dependances/README.txt) |
| Theorem 3: positive-spread separation | C2 and the additional endpoint-preservation dual | [Separation analysis](../audit_apport/literature/JOINT_SEPARATION.md) |
| Theorem 4: sufficient refinement | C1; `construct`, `verify-construct` | [Exact criteria](CRITERE_PROUVE.md), Theorem 2 |

The theorem numbers in the original engine notes differ from the manuscript. Their mathematical statements should be matched by content and assumptions.

## Exact endpoint separation

Across every allowed choice of prices in the example's positive bid-ask spreads,

$$
c_{\mathrm{final}}^{\mathrm{coarse\ backward}}
\le \frac{50669}{1000000}
< \frac{1297357}{25600000}
\le c_{\mathrm{final}}^{\mathrm{refined\ joint}}.
$$

The strict gap is `1153/128000000`. The augmented refined system, with the coarse backward upper constraint imposed on the same endpoints, also has a ten-term exact dual certificate with margin `4739/384000000`. The margin depends on row scaling; it is distinct from the price gap.

This separates recovery after one halving from a construction that preserves a coarse backward calibrated endpoint. Buehler-Ryskin Section 4.4 also permits recalibration on a finer grid, which is compatible with the example. The comparison does not exclude every modification of their method.

## Three strikes and a terminal interval

With constant neighboring prices, let `g0>0` be the initial central gamma, `kappa=2/(h_minus*h_plus)`, and `0<l<u` the variance bounds. For step `j`, set `a_j=x^2*DeltaT_j/2`, `alpha_j=1/(1+kappa*a_j*u)`, and `beta_j=1-kappa*a_j*l`.

A joint path reaching a terminal increment interval `J` exists precisely when every step satisfies `a_j*kappa*l*u <= u-l` and `J` intersects

$$
\left[\frac{g_0}{\kappa}\left(1-\prod_j\beta_j\right),
      \frac{g_0}{\kappa}\left(1-\prod_j\alpha_j\right)\right].
$$

There are no intermediate central quote constraints in this characterization. Initial shape conditions and compatibility of the fixed neighbors with their quote intervals are required to embed it in the full three-strike problem. Rational inputs and a rational target admit a rational constructive path. In the two-half-step example, the terminal increment interval is `[87/128000, 9/12500]`.

## Classical tools and remaining questions

The fixed-grid alternative follows from convex separation and Farkas-type reasoning. The local scalar threshold follows algebraically from the endpoint inequalities. The harmonic-variance recurrence is the implicit midpoint rule. Bernstein positivity and the Taylor/quotient estimates are established tools.

The contribution is the explicit characterization and certification of the stated joint problem, particularly the positive-spread endpoint separation and its constructive recovery. Correctness of these statements and their targeted comparison do not establish general bibliographic priority or general non-derivability from prior work.

The market illustration comprises four SPXW archives from one date under nominal normalization and broad volatility bounds. It is not an independent multi-day success-rate study. The synthetic results preserve numerical feasible, exact stored-LP infeasible, and indeterminate outcomes. See [validation](../VALIDATION.md).
