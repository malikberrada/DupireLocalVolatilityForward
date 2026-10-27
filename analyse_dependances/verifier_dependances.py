"""Exact arithmetic accompanying Analyse_dependances_Dupire_20261027.pdf.

No solver, network, or third-party package is used. This is an arithmetic
checker and a constructive special-case algorithm, not a literature reader
or a formal proof assistant. Run: python -I -S verifier_dependances.py
"""
from fractions import Fraction as Q
from pathlib import Path
import json
import hashlib
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verifier_joint_independant import verify_folder, rebuild


def require(condition, message):
    if not condition:
        raise ValueError(message)


def product(values):
    out = Q(1)
    for value in values:
        out *= value
    return out


def poly_add(*polys):
    out = {}
    for p in polys:
        for powers, value in p.items():
            out[powers] = out.get(powers, Q(0)) + value
    return {k: v for k, v in out.items() if v}


def poly_mul(p, q):
    out = {}
    for a, av in p.items():
        for b, bv in q.items():
            k = tuple(x + y for x, y in zip(a, b))
            out[k] = out.get(k, Q(0)) + av * bv
    return {k: v for k, v in out.items() if v}


def scale(p, c):
    return {k: v * c for k, v in p.items() if v * c}


def power(p, n):
    out = {tuple(0 for _ in next(iter(p))): Q(1)}
    for _ in range(n):
        out = poly_mul(out, p)
    return out


def symbolic_checks():
    # The unequal-spacing stencil, checked as a polynomial identity after
    # multiplication by p+q, on each Taylor monomial through degree four.
    p, q = {(1, 0): Q(1)}, {(0, 1): Q(1)}
    summ = poly_add(p, q)
    coeffs = [Q(0), Q(0), {(0, 0): Q(2)},
              scale(poly_add(p, scale(q, -1)), 2),
              scale(poly_add(power(p, 2), scale(poly_mul(p, q), -1), power(q, 2)), 2)]
    for n in range(1, 5):
        numerator = scale(poly_add(power(p, n - 1), scale(power(q, n - 1), (-1) ** n)), 2)
        expected = poly_mul(summ, coeffs[n]) if isinstance(coeffs[n], dict) else {}
        require(numerator == expected, 'Taylor stencil polynomial identity failed')
    # Crank-Nicolson / implicit midpoint for g'=-c*g:
    # rho=(1-z)/(1+z) satisfies rho-1=-z*(rho+1).
    one, z = {(0,): Q(1)}, {(1,): Q(1)}
    num, den = poly_add(one, scale(z, -1)), poly_add(one, z)
    require(not poly_add(num, scale(den, -1), poly_mul(z, poly_add(num, den))),
            'Midpoint identity failed')
    # C1: delta*g*r^2 - d*r - (v+delta)*(a*r+b).
    vs = [{tuple(int(i == j) for i in range(7)): Q(1)} for j in range(7)]
    delta, g, r, d, v, a, b = vs
    left = poly_add(poly_mul(poly_mul(delta, g), power(r, 2)),
                    scale(poly_mul(d, r), -1),
                    scale(poly_mul(poly_add(v, delta), poly_add(poly_mul(a, r), b)), -1))
    A = poly_add(d, poly_mul(poly_add(v, delta), a))
    B = poly_mul(poly_add(v, delta), b)
    right = poly_add(poly_mul(poly_mul(delta, g), power(r, 2)),
                     scale(poly_mul(A, r), -1), scale(B, -1))
    require(left == right, 'C1 quadratic rearrangement failed')
    return {'unequal_spacing_Taylor_monomials': 'exact_through_degree_4',
            'C1_quadratic_rearrangement': 'exact_polynomial_identity',
            'C3_midpoint_recurrence': 'exact_polynomial_identity'}


def reachable(kappa, a_steps, lower, upper, gamma0):
    """Exact complete reachability, ONLY for constant two neighbour prices.

    a_steps[j] = x_middle**2 * (t[j+1]-t[j]) / 2.
    There are no intermediate centre quotes. lower,upper are variances.
    The proof of completeness is in the PDF; this routine computes endpoints.
    """
    k, l, u, g0 = map(Q, (kappa, lower, upper, gamma0))
    steps = list(map(Q, a_steps))
    require(k > 0 and 0 < l < u and g0 > 0 and steps and min(steps) > 0,
            'Require k>0, gamma0>0, positive steps and 0<l<u')
    intervals = [(1 / (1 + k * a * u), 1 - k * a * l) for a in steps]
    if any(lo > hi for lo, hi in intervals):
        return {'feasible': False, 'reason': 'empty_local_ratio_interval'}
    lo_product = product(lo for lo, _ in intervals)
    hi_product = product(hi for _, hi in intervals)
    return {'feasible': True, 'intervals': intervals,
            'increment_min': g0 * (1 - hi_product) / k,
            'increment_max': g0 * (1 - lo_product) / k}


def construct(kappa, a_steps, lower, upper, gamma0, terminal_bid, terminal_ask):
    """Construct a rational admissible gamma path for a terminal-increment box.

    Does not take roots. It intersects the one-step interval with the backward
    reachable interval for the chosen terminal gamma, using rational endpoints.
    """
    k, l, u, g0, bid, ask = map(Q, (kappa, lower, upper, gamma0, terminal_bid, terminal_ask))
    require(bid <= ask, 'Reversed terminal increment box')
    steps = list(map(Q, a_steps))
    reach = reachable(k, steps, l, u, g0)
    if not reach['feasible']:
        return reach
    dlo, dhi = max(bid, reach['increment_min']), min(ask, reach['increment_max'])
    if dlo > dhi:
        return {'feasible': False, 'reason': 'terminal_quote_misses_reachable_interval'}
    target = g0 - k * (dlo + dhi) / 2
    gammas = [g0]
    intervals = reach['intervals']
    for j, (lo, hi) in enumerate(intervals):
        rest_lo = product(a for a, _ in intervals[j + 1:])
        rest_hi = product(b for _, b in intervals[j + 1:])
        next_lo = max(lo * gammas[-1], target / rest_hi)
        next_hi = min(hi * gammas[-1], target / rest_lo)
        require(next_lo <= next_hi, 'Backward reachable intersection unexpectedly empty')
        gammas.append((next_lo + next_hi) / 2)
    require(gammas[-1] == target and target > 0, 'Terminal gamma mismatch')
    increments = [(a - b) / k for a, b in zip(gammas, gammas[1:])]
    for a, before, after, inc in zip(steps, gammas, gammas[1:], increments):
        require(a*l*before <= inc <= a*u*before and a*l*after <= inc <= a*u*after,
                'A raw forward/backward inequality failed on a constructed path')
    require(bid <= sum(increments, Q(0)) <= ask, 'Terminal quote failed')
    return {'feasible': True, 'gammas': gammas, 'increments': increments}


def verify_reachability():
    k, l, u, g = Q(250), Q(3, 100), Q(1, 25), Q(1, 2)
    coarse_a = Q(1, 20)
    require(not reachable(k, [coarse_a], l, u, g)['feasible'], 'Coarse interval must be empty')
    reach2 = reachable(k, [coarse_a/2]*2, l, u, g)
    require(reach2['increment_min'] == Q(87, 128000) and
            reach2['increment_max'] == Q(9, 12500), 'Two-step exact reachable endpoints changed')
    checked = 0
    # Test endpoints, interior quotes, an excluded quote, and unequal steps.
    # These are arithmetic regression checks; the PDF contains the general proof.
    for steps in ([coarse_a/2]*2, [Q(1, 50), Q(3, 100)], [coarse_a/4]*4,
                  [coarse_a/8]*8, [coarse_a/16]*16):
        rr = reachable(k, steps, l, u, g)
        require(rr['feasible'], 'Expected feasible local intervals')
        d0, d1 = rr['increment_min'], rr['increment_max']
        for bid, ask in ((d0, d0), (d1, d1), (d0, d1), (Q(1, 2000), Q(11, 10000))):
            require(construct(k, steps, l, u, g, bid, ask)['feasible'], 'Reachable target rejected')
            checked += 1
        require(not construct(k, steps, l, u, g, d1+Q(1, 10**8), d1+Q(1, 10**7))['feasible'],
                'An unreachable terminal quote was accepted')
        checked += 1
    require(not reachable(k, [Q(3, 80)], l, u, g)['feasible'], 'Oversized local step was accepted')
    # Existing harmonic midpoint witness, tested against all four raw bounds.
    z = Q(3, 28); rho = (1-z)/(1+z)
    gs = [g, rho*g, rho*rho*g]
    ds = [(a-b)/k for a, b in zip(gs, gs[1:])]
    for before, after, inc in zip(gs, gs[1:], ds):
        require(coarse_a*l*before/2 <= inc <= coarse_a*u*before/2 and
                coarse_a*l*after/2 <= inc <= coarse_a*u*after/2, 'Midpoint raw bound failed')
    require(sum(ds, Q(0)) == Q(84, 120125), 'Midpoint terminal increment changed')
    return {'scope': 'three_strikes_constant_neighbours_no_intermediate_centre_quotes',
            'two_step_exact_increment_interval': [str(reach2['increment_min']), str(reach2['increment_max'])],
            'rational_endpoint_and_quote_checks': checked,
            'midpoint_terminal_increment': str(sum(ds, Q(0)))}


def box_linear(coeffs, boxes, maximize=False):
    return sum((c * (hi if (c >= 0) == maximize else lo)
                for c, (lo, hi) in zip(coeffs, boxes)), Q(0))


def verify_preserved_endpoint_obstruction(folder):
    p = json.loads((folder/'coarse_joint.problem.json').read_text())
    ts, xs = list(map(Q, p['times'])), list(map(Q, p['strikes']))
    require(len(ts) == 2 and len(xs) == 3, 'Expected the certified 2x3 example')
    hm, hp = xs[1]-xs[0], xs[2]-xs[1]
    w0, w2, k = 2/((hm+hp)*hm), 2/((hm+hp)*hp), 2/(hm*hp)
    quotes = {(Q(t), Q(x)): (Q(b), Q(a)) for t, x, b, a in p['observations']}
    initial = [quotes[ts[0], x] for x in xs]
    terminal = [quotes[ts[1], x] for x in xs]
    gmin = box_linear([w0, -k, w2], initial)
    gmax = box_linear([w0, -k, w2], initial, True)
    # Calendar constraints imply nonnegative neighbour increments on each half.
    # Their total increments cannot exceed final ask minus initial bid.
    qmax = w0*(terminal[0][1]-initial[0][0]) + w2*(terminal[2][1]-initial[2][0])
    a = xs[1]**2*(ts[1]-ts[0])/2
    l, u = Q(p['vmin'][0][0]), Q(p['vmax'][0][0])
    ah = a/2
    require(gmin > 0 and 1-k*ah*l > 0 and qmax >= 0, 'Obstruction assumptions failed')
    coarse_cap = initial[1][1] + a*u*(gmax+qmax)/(1+a*k*u)
    fine_floor = initial[1][0] + (2*ah*l-k*(ah*l)**2)*gmin
    gap = fine_floor-coarse_cap
    require(coarse_cap == Q(50669, 1000000) and fine_floor == Q(1297357, 25600000)
            and gap == Q(1153, 128000000) > 0, 'Strict preserved-endpoint obstruction failed')
    # Coarse backward-upper implies c_final<=coarse_cap. Refined forward-lower
    # plus calendars implies c_final>=fine_floor. Both necessary bounds hold for
    # ALL selections in the positive bid-ask boxes, not just the midpoint data.
    return {'coarse_backward_terminal_price_upper_bound': str(coarse_cap),
            'two_half_steps_joint_terminal_price_lower_bound': str(fine_floor),
            'strict_gap': str(gap),
            'positive_spread_box_scope': True,
            'conclusion': 'no_coarse_backward_fit_can_be_preserved_by_a_joint_fit_after_one_halving',
            'scope_of_comparison': 'BR2016_section_4_4_preserves_calibrated_expiry_prices; no_claim_about_all_possible_modifications'}


def preserved_endpoint_rows(p):
    require(p['format'] == 'dupire-preserved-endpoint-problem-v1', 'Wrong extended problem format')
    fine = p['fine_problem']
    require(fine['scheme'] == 'joint' and len(fine['times']) == 3 and len(fine['strikes']) == 3,
            'Expected a two-step joint base problem')
    rows, _, _ = rebuild(fine)
    ts, xs = list(map(Q, fine['times'])), list(map(Q, fine['strikes']))
    u = Q(p['coarse_backward_variance_upper'])
    require(u == Q(fine['vmax'][0][0]) == Q(fine['vmax'][1][0]), 'Upper variance changed')
    a = xs[1]**2*(ts[2]-ts[0])/2
    hm, hp = xs[1]-xs[0], xs[2]-xs[1]
    w0, w2, k = 2/((hm+hp)*hm), 2/((hm+hp)*hp), 2/(hm*hp)
    # Additional coarse backward upper constraint on the SAME initial and
    # final price variables as the refined problem: c7-c1 <= a*u*Gamma2.
    rows.append(('coarse_backward_upper',
                 {1: Q(-1), 6: -a*u*w0, 7: 1+a*u*k, 8: -a*u*w2}, Q(0)))
    return rows


def verify_preserved_endpoint_dual(folder):
    p = json.loads((folder/'conservation_endpoint.problem.json').read_text())
    c = json.loads((folder/'conservation_endpoint.certificate.json').read_text())
    original_fine = json.loads((folder/'refined_joint.problem.json').read_text())
    require(p['fine_problem'] == original_fine, 'Changed refined problem in the extended certificate')
    digest = hashlib.sha256(json.dumps(p, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(c['format'] == 'dupire-preserved-endpoint-dual-v1' and c['problem_sha256'] == digest,
            'Extended certificate binding failed')
    rows = preserved_endpoint_rows(p)
    require(len(c['rows']) == len(c['multipliers']) == len(set(c['rows'])) > 0, 'Invalid dual support')
    residual, rhs = {}, Q(0)
    labels = set()
    for i, weight in zip(c['rows'], map(Q, c['multipliers'])):
        require(type(i) is int and 0 <= i < len(rows) and weight > 0, 'Invalid positive dual multiplier')
        label, row, bound = rows[i]
        labels.add(label); rhs += weight*bound
        for j, value in row.items():
            residual[j] = residual.get(j, Q(0)) + weight*value
    require(not any(residual.values()) and rhs < 0, 'Not an exact Farkas contradiction')
    require({'coarse_backward_upper', 'forward_local_lower', 'calendar', 'ask', 'bid'} <= labels,
            'Expected both temporal scales, calendars and quote bounds in the separator')
    require(-rhs == Q(c['strict_margin']), 'Incorrect stated dual margin')
    return {'verified': True, 'support_size': len(c['rows']), 'strict_margin': str(-rhs),
            'scope': 'refined_joint_plus_coarse_backward_upper_on_identical_endpoint_variables'}


def verify_all(folder=None):
    folder = Path(folder) if folder is not None else Path(__file__).resolve().parent/'certificats'
    result = {'status': 'derivations_and_strict_method_separation_checked',
              'symbolic_arithmetic': symbolic_checks(),
              'original_example': verify_folder(folder),
              'complete_special_case': verify_reachability(),
              'additional_method_separation': verify_preserved_endpoint_obstruction(folder),
              'additional_method_separation_dual': verify_preserved_endpoint_dual(folder),
              'bibliographic_conclusion': 'targeted_nonimplication_proved_global_originality_not_established',
              'scope': 'arithmetic_checks_and_written_proofs_not_automated_semantic_or_formal_verification'}
    return result


if __name__ == '__main__':
    answer = verify_all()
    if len(sys.argv) == 3 and sys.argv[1] == '--verify-json':
        expected = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        require(expected == answer, 'Saved arithmetic result differs from recomputation')
    elif len(sys.argv) != 1:
        raise SystemExit('Usage: python -I -S verifier_dependances.py [--verify-json preuves_dependances.json]')
    print(json.dumps(answer, ensure_ascii=False, indent=2))
