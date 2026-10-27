# Constructive calibration and certified refinement

Introduced in 0.1.2 and updated in **0.1.6**. The result concerns normalized European calls, a common strike grid, a finite interior rectangle, and constant local variance bounds. It is sufficient and conservative. The complete proof and explicit quadratic threshold appear in [CRITERE_PROUVE.md](CRITERE_PROUVE.md), Theorem 2, corresponding to manuscript Theorem 4 and project label C1.

## 1. Finite data and unknowns

The financial inputs are intervals `(T_k,x_k,bid_k,ask_k)` in normalized call units. Their coordinate extrema define

$$
R=[T_a,T_b]\times[x_a,x_b],\qquad T_a>0,\quad x_a>0.
$$

The union of observed strikes and maturities supplies the base grid. Unquoted nodes are unknowns, not observations. With only two distinct strikes, their midpoint is added to the base axis. At least two distinct maturities are required.

Prescribe `0<=v_min<v_max`, an interior **variance** buffer `0<delta<(v_max-v_min)/2`, and `g>0`. `--sigma-min` and `--sigma-max` are volatility strings interpreted exactly before squaring since 0.1.6. `--variance-buffer` and `--gamma-floor` are also read exactly. CSV observations on this path retain their exact binary64 rational representations.

For chosen degrees `m>=1`, `n>=2`, the unknowns are the `(m+1)*(n+1)` rational coefficients

$$
P_a(T,x)=\sum_{p=0}^m\sum_{q=0}^n a_{pq}B_p^m(u)B_q^n(w),
\quad u=\frac{T-T_a}{T_b-T_a},\quad w=\frac{x-x_a}{x_b-x_a}.
$$

No admissible surface, unknown-surface derivatives, or reference prices are provided to the fit. Even `--demo` supplies only a CSV of quote intervals.

## 2. Finite coefficient constraints

Write `B(f)` for Bernstein coefficients on `R`, after degree elevation when needed. Find a rational coefficient vector satisfying

$$
\begin{aligned}
&b_k\le P_a(T_k,x_k)\le A_k\quad\text{for every observation},\\
&\mathcal B(P_a),\ \mathcal B(P_a-1+x),\ \mathcal B(1-P_a)\ge0,\\
&\mathcal B(-P_{a,x}),\ \mathcal B(1+P_{a,x})\ge0,\\
&\mathcal B(P_{a,xx}-g)\ge0,\\
&\mathcal B(P_{a,T}-\tfrac12(v_{\min}+\delta)x^2P_{a,xx})\ge0,\\
&\mathcal B(\tfrac12(v_{\max}-\delta)x^2P_{a,xx}-P_{a,T})\ge0,\\
&\mathcal B_T(1-P_a(T,x_a)+x_aP_{a,x}(T,x_a))\ge0.
\end{aligned}\tag{C}
$$

Here `b_k=bid_k` and `A_k=ask_k`. The last row covers the software's `left_chord` constraint. All rows are linear in the coefficients. Quote rows can also be written `|E_k*a-mid_k|<=half_spread_k`, with `E_k` given by the Bernstein evaluation basis.

HiGHS searches this coefficient LP and maximizes a common numerical margin `rho>=0`: each row `r*a+d>=0` becomes `r*a+d>=s_r*rho`, where `s_r=max(1,|d|,sum|r_i|)`. A positive numerical margin is not a proof. Every reconstructed coefficient row and observed interval is then checked exactly, without tolerance. Boundary candidates can also be accepted when they pass that check. Numerical discovery is incomplete for degenerate exact LPs.

This is a finite sufficient polynomial family, more restrictive than the original nodal calibration LP. It is not a necessary condition on arbitrary quote sets or their spread widths.

## 3. Certified global constants

Compute on the **same constructed polynomial**:

$$
\gamma_0=\min\mathcal B(P_{a,xx})\ge g>0,\quad
M_3=\max|\mathcal B(P_{a,xxx})|,\quad
M_4=\max|\mathcal B(P_{a,xxxx})|,\quad
M_{TT}=\max|\mathcal B(P_{a,TT})|.
$$

Nonnegativity and partition of unity certify these global bounds. An identically zero derivative yields zero. These constants are computed after construction, rather than assumed to be known beforehand.

## 4. A sufficient test on a given grid

Retain every observed coordinate. For each interior strike, let

$$
E_{\gamma,i}=\frac{|h_i^+-h_i^-|M_3}{3}
+\frac{((h_i^+)^3+(h_i^-)^3)M_4}{12(h_i^++h_i^-)}.
$$

If every spatial node and time cell satisfies

$$
E_{\gamma,i}<\gamma_0,\qquad
\frac{\Delta T_jM_{TT}/x_a^2+v_{\max}E_{\gamma,i}}
{\gamma_0-E_{\gamma,i}}\le\delta,\tag{G}
$$

then the constructed samples `P_a(T_j,x_i)` satisfy all observed intervals, price bounds, slopes, convexity, calendars, the left connection, and **both local variance systems simultaneously**. Interior discrete gamma is positive, so no `0/0` quotient is used.

Bernstein positivity gives the continuous shape conditions and interior variance margin. Discrete slopes are averages of `P_x`; convexity orders them. Taylor expansion bounds the gamma error by `E_gamma`. The time difference differs from `P_T` at either endpoint by at most `DeltaT*Mtt/2`. Subtracting the two Dupire quotients and using `Gamma_h>=gamma0-E_gamma` gives (G). The left endpoint supplies forward and the right endpoint backward, with the same prices. The full proof is in [the exact-criteria note](CRITERE_PROUVE.md).

## 5. Refinement and termination

Keep the same certified polynomial and original observations. Divide every base spatial and temporal interval into `r=2^ell` equal pieces. Put

$$
H=\max_i h_i,\quad D_h=\max_i|h_{i+1}-h_i|,\quad
\tau=\max_j\Delta T_j,\qquad
e_\ell=\frac{D_hM_3}{3\,2^\ell}+\frac{H^2M_4}{12\,4^\ell}.
$$

At old nodes, asymmetry scales by `1/r`; at new nodes within a base interval, it vanishes. The identity `(a^3+b^3)/(a+b)=a^2-a*b+b^2<=max(a,b)^2` gives a uniform bound for every `E_gamma`.

The implementation searches in rational arithmetic for

$$
e_\ell<\gamma_0,\qquad
\frac{\tau M_{TT}/(2^\ell x_a^2)+v_{\max}e_\ell}
{\gamma_0-e_\ell}\le\delta.\tag{R}
$$

Equivalently, set `a=D_h*M3/3`, `b=H^2*M4/12`, `d=tau*Mtt/x_a^2`, `A=d+(v_max+delta)*a`, `B=(v_max+delta)*b`, and `C=delta*gamma0`. Test `C*r^2-A*r-B>=0`. The report gives the constants, exact quadratic margins, and an integer bound on the required level.

Finite constants and positive `gamma0`, `delta`, and `x_a` guarantee a finite sufficient threshold. All later dyadic levels satisfy the estimate. No nodal LP needs to be resolved at those levels. Old node values remain identical and quote intervals are never widened.

`--max-level` bounds the search. If no threshold is visited, the continuous-window certificate can still be retained without declaring a computed level. `--max-nodes` limits materialized samples only: the theoretical threshold can be certified without allocating the refined grid. Extreme rational levels may exceed binary64 resolution or available export memory.

Other observation preserving grid families can satisfy the same estimate when both error maxima tend to zero. The implemented rule couples space and time refinement. Refining only time cannot generally remove spatial error, and conversely, unless the unchanged error is already absorbed or zero.

## 6. Commands, outputs, and statuses

```powershell
& $PyDupire -u -m dupire_joint construct --demo --device cpu `
  --degree-time 2 --degree-space 4 --threads 4 --out runs/constructive

& $PyDupire -u -m dupire_joint verify-construct `
  --certificate runs/constructive/constructive.certificate.json `
  --quotes runs/constructive/observations.csv --out runs/constructive_verified
```

HiGHS C++ performs discovery through its pip wheel. NumPy/BLAS evaluates CPU samples; optional `--device cuda` uses PyTorch float64 matrix operations. Exact checking uses CPU `fractions.Fraction`. No compiler, CMake, nvcc, or JIT build is required for the reference workflow. Long phases retain progress counters and supervisor heartbeats.

The certificate stores rational observations, hashes, parameters, and polynomial coefficients. `verify-construct` recalculates every constraint and constant; it does not trust stored minima, a HiGHS status, or a tolerance. A hash binds data and certificate, rather than authenticating external prices.

NPZ samples are rounded exports. They separately pass the binary64 LP audit and direct per-stencil audit at `--audit-tol`. The mathematical proof concerns rational samples on the axes in `mesh.exact.json`; it does not assert that every hardware-rounded sample belongs exactly to the binary64 LP.

| Status | Meaning |
|---|---|
| `feasible_from_guaranteed_level` | Exact certificate and sufficient threshold found; any export is audited separately |
| `continuous_window_certified` | Continuous polynomial conditions certified; bounded search did not reach a threshold |
| `not_certified` | No candidate passed exact verification; no general infeasibility follows |

Exit code `0` means successful certification, `3` means `not_certified`, and `2` indicates an input/assumption or execution error. Read `construction.json` for every attempt.

## 7. Scope and references

The guarantee is established on a computed witness. Finding a witness in this family is not guaranteed: tight intervals, sparse wings, small degrees, or a large gamma floor can prevent certification even when another calibration exists. Changing parameters or degrees starts a new search requiring a new certificate.

The theorem excludes the payoff kink at `T=0`, infinite tails, bounded-support zero anchors, global time extension, martingale diffusion construction, cellwise variable variance bounds, and moving strike grids. A common union of strikes avoids transport interpolation error of type `h_interp^2/DeltaT`; this does not extend automatically to moving grids.

Later-level admissibility follows from the same witness and (R), rather than general nesting of nodal feasible sets. Bernstein positivity and Taylor analysis are classical. The implementation establishes the stated restricted construction; tests do not establish general bibliographic priority.

Primary references: [Bernstein properties, derivatives, and degree elevation](https://web.mit.edu/hyperbook/Patrikalakis-Maekawa-Cho/node9.html), and [Buehler-Ryskin, extensive version, Section 3.3](https://quantitative-research.de/dl/Discrete%20Local%20Volatility%20-%20Extensive.pdf).
