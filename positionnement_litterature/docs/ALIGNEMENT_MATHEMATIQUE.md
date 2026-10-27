# Align mathematical statements before comparing contributions

The project result concerns normalized calls on a finite interior rectangle, a common Cartesian grid, and fixed observed intervals. Compare statements under those assumptions; a method's name or a numerical success does not establish equivalence.

## Separate the claim's components

Bernstein bases, coefficient shape constraints, linear programming, Dupire's formula, and Taylor estimates are prior tools. The literature matrix records versions and locators. The software adds exact reproducible checking of the implemented statement.

The candidate chain to compare is

$$
\text{fixed observed intervals}\longrightarrow
\text{rational polynomial witness}\longrightarrow
(\gamma_0,M_3,M_4,M_{TT})\longrightarrow
\text{dyadic threshold for both endpoint stencils}.
$$

The finite coefficient system is sufficient at a fixed degree. Failure does not decide existence among every possible surface. A correct proof alone does not establish that a specialization is not an immediate consequence of known results. See [the research guide](../../docs/RESEARCH.md) for the separate endpoint-preservation result.

## Match the problems

| Dimension | Alignment question |
|---|---|
| Unknown | Nodal prices, polynomial coefficients, density, local variance, or a network? |
| Domain | One strike slice, interior rectangle, or a global domain with tails? |
| Observations | Hard intervals, midpoint least squares, or penalties for interval violations? |
| Geometry | Common grid, moving grids, interpolation, or transport operator? |
| Bounds | Implied, continuous local, or discrete local variance; one or both stencils? |
| Positivity | Certified strict gamma, nonnegative gamma, or a numerical threshold? |
| Refinement | Original intervals and bounds retained at every subsequent level? |
| Evidence | Tolerated residuals, certified intervals, or exact rational arithmetic? |

A regularized inverse problem and a hard-interval nonemptiness problem answer different questions. Smooth slices do not establish maturity calendars. Bounds on transition variables are not automatically the same bounds on a post-smoothing stencil quotient.

## Interpret the sufficient threshold

With an interior margin `delta`,

$$
e_r=\frac{D_hM_3}{3r}+\frac{H^2M_4}{12r^2},\qquad
|v_h-v|\le\frac{\tau M_{TT}/(r x_a^2)+v_{\max}e_r}{\gamma_0-e_r}.
$$

This yields `C*r^2-A*r-B>=0`. It certifies grids sampled from one witness, not the earliest grid admitting any nodal calibration. The code records separately the first level guaranteed by the bound, levels at which the same polynomial actually satisfies both stencils, and levels at which a nodal LP finds another feasible witness.

In the included control, the last two tests pass at level 0 while the sufficient estimate guarantees level 2. This demonstrates conservatism of the bound, rather than improved accuracy or speed over published methods.

## Comparator scope

`kkt2016.py` implements a published fixed-degree per-slice formulation. Verified coefficients establish that formulation's slice shape constraints without silently adding project constraints. Rational rounding correction is bounded uniformly by partition of unity and records its budget and effect; it does not prove exact least-squares optimality.

`experiments.py` also adapts a published repair objective to the project's `F0` window. Auditing that objective does not reproduce the paper's complete market model, data filtering, or experiments.

The polynomial ablation retains every interval, the degrees, gamma floor, and calendar while removing only the local bounds. If it also satisfies those bounds on the tested data, the report says so and attributes no empirical benefit to imposing them.

Failed rational reconstruction of a comparator's numerical witness proves neither infeasibility nor failure of a published theorem. Numerical residuals retain their units and scale.

## Bibliographic closure

`not_determined_by_this_tool` describes the tool's reach. Establishing originality requires comparison of complete nearest statements against the obligations above, including constrained approximation and irregular-grid finite-difference literature. Unread full texts remain access gaps rather than evidence of absent results.

A correct mathematical statement, an exact software witness on declared data, and possible scientific priority are three different assertions. Computation checks identities and witnesses; priority requires substantive source analysis and remains limited by the documented corpus.
