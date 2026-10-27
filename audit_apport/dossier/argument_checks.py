"""Exact checks for two explicitly scoped bibliographic arguments; stdlib only."""
from fractions import Fraction as Q


def ensure(condition):
    if not condition:
        raise ValueError('A scoped mathematical argument failed its exact check')


def add(*polys):
    out = {}
    for poly in polys:
        for powers, value in poly.items():
            out[powers] = out.get(powers, Q(0)) + value
    return {k: v for k, v in out.items() if v}


def mul(left, right):
    out = {}
    for a, av in left.items():
        for b, bv in right.items():
            k = tuple(x+y for x, y in zip(a, b))
            out[k] = out.get(k, Q(0)) + av*bv
    return {k: v for k, v in out.items() if v}


def neg(poly):
    return {k: -v for k, v in poly.items()}


def derivative(poly, variable):
    out = {}
    for powers, value in poly.items():
        if powers[variable]:
            new = list(powers); new[variable] -= 1
            out[tuple(new)] = value*powers[variable]
    return out


def evaluate(poly, values):
    return sum((c*prod(v**p for v, p in zip(values, powers)) for powers, c in poly.items()), Q(0))


def prod(values):
    result = Q(1)
    for value in values: result *= value
    return result


def threshold_interval(dt, x, kappa, lower, upper, gamma):
    dt, x, kappa, lower, upper, gamma = map(Q, (dt, x, kappa, lower, upper, gamma))
    if not (dt > 0 and x > 0 and kappa > 0 and gamma > 0 and 0 < lower < upper):
        raise ValueError('Require positive step, strike, kappa, gamma and 0<lower<upper')
    a = x*x*dt/2
    lo = a*lower*gamma
    hi = a*upper*gamma/(1+a*upper*kappa)
    return {'lower_increment': str(lo), 'upper_increment': str(hi), 'nonempty': lo <= hi,
            'threshold': str(2*(upper-lower)/(x*x*kappa*lower*upper))}


def verify_arguments():
    # Variables a,l,u,k,g: a*l*g*(1+a*u*k)-a*u*g = a*g*(l-u+a*k*l*u).
    one = {(0, 0, 0, 0, 0): Q(1)}
    variables = [{tuple(int(j == i) for j in range(5)): Q(1)} for i in range(5)]
    a, l, u, k, g = variables
    left = add(mul(mul(mul(a, l), g), add(one, mul(mul(a, u), k))), neg(mul(mul(a, u), g)))
    right = mul(mul(a, g), add(l, neg(u), mul(mul(mul(a, k), l), u)))
    ensure(left == right)

    # P(T,x) = 4/5-x+x^2*(1+T/50)/4. All calculations below are rational.
    p = {(0, 0): Q(4, 5), (0, 1): Q(-1), (0, 2): Q(1, 4), (1, 2): Q(1, 200)}
    px = derivative(p, 1); pxx = derivative(px, 1)
    pt = derivative(p, 0); ptt = derivative(pt, 0)
    pxxx = derivative(pxx, 1); pxxxx = derivative(pxxx, 1)
    t0, t1, x0, x1 = Q(1, 4), Q(7, 20), Q(9, 10), Q(27, 25)
    q0, q1 = (1+t0/50)/4, (1+t1/50)/4
    vmin, vmax, delta, gamma0 = Q(19, 1000), Q(21, 1000), Q(1, 2000), Q(1, 2)
    bounds = {'P_min': evaluate(p, (t0, x1)), 'P_max': evaluate(p, (t1, x0)),
              'P_minus_intrinsic_lower_bound': min(evaluate(p, (t0, x1)), q0*x0*x0-Q(1, 5)),
              'Px_min': -1+2*q0*x0, 'Px_max': -1+2*q1*x1,
              'Pxx_min': 2*q0, 'Pxx_max': 2*q1,
              'raccord_lower_bound': Q(1, 5)+q0*x0*x0,
              'variance_min': 1/(50+t1), 'variance_max': 1/(50+t0)}
    ensure(bounds['P_min'] > 0 and bounds['P_max'] < 1 and bounds['P_minus_intrinsic_lower_bound'] > 0)
    ensure(-1 <= bounds['Px_min'] <= bounds['Px_max'] <= 0)
    ensure(bounds['Pxx_min'] >= gamma0 and bounds['raccord_lower_bound'] > 0)
    ensure(vmin+delta <= bounds['variance_min'] <= bounds['variance_max'] <= vmax-delta)
    ensure(not ptt and not pxxx and not pxxxx)
    ensure(mul(pt, {(0, 0): Q(100), (1, 0): Q(2)}) == mul({(0, 2): Q(1)}, pxx))
    # The exact quadratic least-squares fit to a time-affine polynomial has zero curvature.
    times = [t0, Q(3, 10), t1]
    prices = [evaluate(p, (t, Q(1))) for t in times]
    second_divided_difference = ((prices[2]-prices[1])/(times[2]-times[1])-
                                (prices[1]-prices[0])/(times[1]-times[0]))/(times[2]-times[0])
    ensure(second_divided_difference == 0)
    return {'status': 'scoped_bibliographic_arguments_checked',
            'BR2016_C3_threshold_component': {
                'polynomial_identity_verified': True,
                'starting_point': 'BR2016 (18),(21), restricted to the project three-strike constant-neighbour class',
                'positive_assumptions': 'a=x^2*DeltaT/2>0; kappa>0; gamma0>0; 0<l<u',
                'common_increment_interval': '[a*l*gamma0, a*u*gamma0/(1+a*u*kappa)]',
                'iff': 'DeltaT <= 2*(u-l)/(x^2*kappa*l*u)',
                'scope': 'threshold component derived algebraically; not attribution of the printed formula or of the entire refinement construction to BR2016'},
            'ZHANG2025_C1_literal_A5_application': {
                'polynomial': '4/5-x+x^2*(1+T/50)/4',
                'domain': {'T': [str(t0), str(t1)], 'x': [str(x0), str(x1)]},
                'variance_bounds': [str(vmin), str(vmax)], 'delta': str(delta), 'gamma_floor': str(gamma0),
                'M3': '0', 'M4': '0', 'Mtt': '0',
                'C1_continuous_conditions_checked': True, 'bounds': {key: str(v) for key, v in bounds.items()},
                'P_TT': '0', 'exact_time_quadratic_fit_curvature': str(2*second_divided_difference),
                'positive_time_mesh_violates_displayed_A5_with_exact_zero_envelope': True,
                'scope': 'blocks the literal hypothesis identification C=P with the exact curvature envelope; does not disprove Lemma S0.2 or establish scientific originality'},
            'scientific_priority_certified': False, 'solver_called': False,
            'third_party_imports': False, 'network_used': False}
