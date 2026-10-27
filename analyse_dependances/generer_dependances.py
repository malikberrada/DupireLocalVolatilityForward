"""Reproduce the written proofs, reconstruct the exact dual, and verify outputs.

Python standard library only. The symbolic and numerical checks do not replace
the written general proofs. There is no solver or literature-priority oracle.

Usage: python -I -S generer_dependances.py --out PATH [--compile-pdf]
"""
from fractions import Fraction as Q
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from verifier_dependances import (
    construct, preserved_endpoint_rows, reachable, require, verify_all,
)

DOCUMENT = 'Analyse_dependances_Dupire_20261027'
BASE_CERTIFICATES = (
    'coarse_forward.problem.json', 'coarse_forward.certificate.json',
    'coarse_backward.problem.json', 'coarse_backward.certificate.json',
    'coarse_joint.problem.json', 'coarse_joint.certificate.json',
    'refined_joint.problem.json', 'refined_joint.certificate.json', 'result.json',
)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def json_fractions(value):
    if isinstance(value, Q):
        return str(value)
    if isinstance(value, dict):
        return {key: json_fractions(v) for key, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_fractions(v) for v in value]
    return value


def rebuild_dual(fine):
    """Build a positive Farkas combination from the actual row definitions.

    The stored conservation_endpoint.certificate.json is never read here.
    The witness is an analytic construction for the delivered two-half-step
    example; it is not an infeasibility-search solver for arbitrary problems.
    """
    ts, xs = list(map(Q, fine['times'])), list(map(Q, fine['strikes']))
    require(len(ts) == len(xs) == 3 and ts[1]-ts[0] == ts[2]-ts[1],
            'Require three strikes and exactly two equal time steps')
    l = Q(fine['vmin'][0][0]); u = Q(fine['vmax'][0][0])
    require(all(list(map(Q, row)) == [l] for row in fine['vmin']) and
            all(list(map(Q, row)) == [u] for row in fine['vmax']),
            'The analytic certificate requires constant variance bounds')
    hm, hp = xs[1]-xs[0], xs[2]-xs[1]
    w0, w2, k = 2/((hm+hp)*hm), 2/((hm+hp)*hp), 2/(hm*hp)
    a = xs[1]**2*(ts[2]-ts[0])/2; ah = a/2
    beta = 1-k*ah*l
    require(beta > 0, 'Analytic forward-lower multiplier is not positive')
    problem = {'format': 'dupire-preserved-endpoint-problem-v1',
               'fine_problem': fine, 'coarse_backward_variance_upper': str(u)}
    rows = preserved_endpoint_rows(problem)
    forward_lower = [i for i, (label, _, _) in enumerate(rows) if label == 'forward_local_lower']
    require(len(forward_lower) == 2, 'Expected one forward-lower row per half-step')
    weights = {len(rows)-1: 1/(1+a*k*u), forward_lower[0]: beta, forward_lower[1]: Q(1)}
    for terms, weight in (({0: Q(1), 3: Q(-1)}, ah*l*w0),
                          ({2: Q(1), 5: Q(-1)}, ah*l*w2)):
        matches = [i for i, (label, row, rhs) in enumerate(rows)
                   if label == 'calendar' and row == terms and rhs == 0]
        require(len(matches) == 1, 'Calendar row not uniquely identified')
        weights[matches[0]] = weight
    residual = {}
    for i, weight in weights.items():
        for j, coefficient in rows[i][1].items():
            residual[j] = residual.get(j, Q(0)) + weight*coefficient
    # Eliminate every remaining coefficient with an actual observed bid/ask row.
    for j, coefficient in residual.items():
        if not coefficient:
            continue
        wanted = Q(-1) if coefficient > 0 else Q(1)
        matches = [i for i, (label, row, _) in enumerate(rows)
                   if label in ('ask', 'bid') and row == {j: wanted}]
        require(len(matches) == 1, 'Quote bound not uniquely identified')
        i = matches[0]
        weights[i] = weights.get(i, Q(0)) + abs(coefficient)
    remaining, rhs = {}, Q(0)
    for i, weight in weights.items():
        require(weight > 0, 'Nonpositive analytic multiplier')
        rhs += weight*rows[i][2]
        for j, coefficient in rows[i][1].items():
            remaining[j] = remaining.get(j, Q(0)) + weight*coefficient
    require(not any(remaining.values()) and rhs < 0, 'Constructed combination is not a contradiction')
    indices = sorted(weights)
    digest = hashlib.sha256(json.dumps(problem, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    certificate = {'format': 'dupire-preserved-endpoint-dual-v1', 'problem_sha256': digest,
                   'rows': indices, 'multipliers': [str(weights[i]) for i in indices],
                   'strict_margin': str(-rhs)}
    return problem, certificate


def export_proof_fragments(source, destination):
    """Reproduce authored text, rather than claiming automatic theorem proving."""
    markers = [r'\stitle{' + str(i) + '.' for i in range(1, 8)]
    positions = [source.index(marker) for marker in markers]
    require(positions == sorted(positions), 'Unexpected order of proof sections')
    scopes = (
        ('C1_taylor_quotient.tex', 0, 1),
        ('C3_seuil_point_milieu.tex', 1, 2),
        ('caracterisation_trois_strikes.tex', 2, 3),
        ('separation_robuste.tex', 3, 5),
    )
    destination.mkdir(parents=True, exist_ok=True)
    out = []
    for name, start, stop in scopes:
        fragment = source[positions[start]:positions[stop]].rstrip()
        if fragment.endswith(r'\clearpage'):
            fragment = fragment[:-len(r'\clearpage')].rstrip()
        header = ('% Fragment du rapport maitre ' + DOCUMENT + '.tex\n'
                  '% Texte de preuve redige et reproduit, pas preuve formelle automatique.\n'
                  '% Les renvois de pages designent le rapport complet.\n')
        (destination/name).write_text(header+fragment+'\n', encoding='utf-8')
        out.append('preuves/'+name)
    return out


def characterization_example(fine):
    ts, xs = list(map(Q, fine['times'])), list(map(Q, fine['strikes']))
    initial_boxes = {Q(x): (Q(bid), Q(ask)) for t, x, bid, ask in fine['observations'] if Q(t) == ts[0]}
    initial_prices = [(initial_boxes[x][0]+initial_boxes[x][1])/2 for x in xs]
    hm, hp = xs[1]-xs[0], xs[2]-xs[1]
    k = 2/(hm*hp)
    g0 = 2/(hm+hp)*((initial_prices[2]-initial_prices[1])/hp-
                      (initial_prices[1]-initial_prices[0])/hm)
    l, u = Q(fine['vmin'][0][0]), Q(fine['vmax'][0][0])
    a_steps = [xs[1]**2*(b-a)/2 for a, b in zip(ts, ts[1:])]
    quote = next((Q(bid), Q(ask)) for t, x, bid, ask in fine['observations']
                 if Q(t) == ts[-1] and Q(x) == xs[1])
    bid, ask = quote[0]-initial_prices[1], quote[1]-initial_prices[1]
    reach = reachable(k, a_steps, l, u, g0)
    require(reach['feasible'], 'The delivered two-step class should be feasible')
    paths = {}
    for name, bounds in (('reachable_lower_endpoint', (reach['increment_min'],)*2),
                         ('reachable_upper_endpoint', (reach['increment_max'],)*2),
                         ('observed_terminal_quote', (bid, ask))):
        path = construct(k, a_steps, l, u, g0, *bounds)
        require(path['feasible'], 'Constructive reachability check failed')
        path['central_prices'] = [initial_prices[1]+(g0-g)/k for g in path['gammas']]
        paths[name] = path
    return json_fractions({
        'scope': 'three_strikes_constant_neighbours_no_intermediate_centre_quotes',
        'variances_not_volatilities': True,
        'necessary_and_sufficient_conditions': [
            'For every j: a_j*kappa*l*u <= u-l',
            'J intersects [g0/kappa*(1-product(beta_j)), g0/kappa*(1-product(alpha_j))]',
        ],
        'definitions': {'a_j': 'x_middle^2*Delta_t_j/2', 'alpha_j': '1/(1+kappa*a_j*u)',
                        'beta_j': '1-kappa*a_j*l', 'J': 'terminal central-price INCREMENT bid-ask interval'},
        'general_proof': 'preuves/caracterisation_trois_strikes.tex; authored mathematical proof',
        'example': {'kappa': k, 'gamma0': g0, 'a_steps': a_steps, 'lower_variance': l,
                    'upper_variance': u, 'terminal_increment_quote': [bid, ask],
                    'exact_reachable_increment_interval': [reach['increment_min'], reach['increment_max']],
                    'rational_witnesses': paths},
    })


def generate(destination, compile_pdf=False):
    destination = Path(destination).resolve()
    require(destination != ROOT and destination not in ROOT.parents,
            'Choose an output directory different from the source bundle and its ancestors')
    pdf_command = shutil.which('pdflatex') if compile_pdf else None
    require(not compile_pdf or pdf_command is not None, '--compile-pdf requires pdflatex on PATH')
    source = (ROOT/(DOCUMENT+'.tex')).read_text(encoding='utf-8')
    fine = json.loads((ROOT/'certificats/refined_joint.problem.json').read_text(encoding='utf-8'))
    problem, certificate = rebuild_dual(fine)
    characterization = characterization_example(fine)
    destination.mkdir(parents=True, exist_ok=True)
    cert_folder = destination/'certificats'; cert_folder.mkdir(exist_ok=True)
    for name in BASE_CERTIFICATES:
        shutil.copyfile(ROOT/'certificats'/name, cert_folder/name)
    dump(cert_folder/'conservation_endpoint.problem.json', problem)
    dump(cert_folder/'conservation_endpoint.certificate.json', certificate)
    proof_names = export_proof_fragments(source, destination/'preuves')
    for name in (DOCUMENT+'.tex', 'verifier_dependances.py', 'verifier_joint_independant.py',
                 'generer_dependances.py', 'sources.json', 'README.txt'):
        shutil.copyfile(ROOT/name, destination/name)
    if compile_pdf:
        command = [pdf_command, '-interaction=nonstopmode', '-halt-on-error', DOCUMENT+'.tex']
        for _ in range(2):
            result = subprocess.run(command, cwd=destination, capture_output=True, text=True,
                                    encoding='utf-8', errors='replace')
            require(result.returncode == 0, 'LaTeX compilation failed:\n'+result.stdout[-4000:])
        pdf_status = 'recompiled_from_authored_latex'
    else:
        shutil.copyfile(ROOT/(DOCUMENT+'.pdf'), destination/(DOCUMENT+'.pdf'))
        pdf_status = 'existing_render_copied_no_tex_installation_required'
    checks = verify_all(cert_folder)  # Checks the newly written dual, not the input dual.
    dump(destination/'preuves_dependances.json', checks)
    dump(destination/'caracterisation_trois_strikes.json', characterization)
    dump(destination/'separation_robuste.json', {
        'price_box_bounds': checks['additional_method_separation'],
        'new_exact_dual': checks['additional_method_separation_dual'],
        'written_proof': 'preuves/separation_robuste.tex',
    })
    dump(destination/'C1_C3_derivations.json', {
        'symbolic_arithmetic': checks['symbolic_arithmetic'],
        'C1_proof': 'preuves/C1_taylor_quotient.tex',
        'C3_proof': 'preuves/C3_seuil_point_milieu.tex',
        'scope': 'symbolic_identities_checked_general_arguments_reproduced_from_authored_note',
    })
    summary = {
        'status': 'proof_texts_reproduced_exact_dual_regenerated_and_verified',
        'output': str(destination), 'proof_fragments': proof_names,
        'dual_generated_from_constraints_not_read_from_stored_certificate': True,
        'dual_support_size': len(certificate['rows']), 'dual_strict_margin': certificate['strict_margin'],
        'robust_terminal_price_gap': checks['additional_method_separation']['strict_gap'],
        'characterization_example': 'caracterisation_trois_strikes.json',
        'pdf': pdf_status, 'general_proofs_formally_machine_verified': False,
        'solver_called': False, 'network_used': False,
    }
    dump(destination/'generation.json', summary)
    managed_names = ([str(Path('certificats')/name) for name in BASE_CERTIFICATES] +
                     ['certificats/conservation_endpoint.problem.json',
                      'certificats/conservation_endpoint.certificate.json'] + proof_names +
                     [DOCUMENT+'.tex', DOCUMENT+'.pdf', 'verifier_dependances.py',
                      'verifier_joint_independant.py', 'generer_dependances.py', 'sources.json',
                      'README.txt', 'preuves_dependances.json', 'caracterisation_trois_strikes.json',
                      'separation_robuste.json', 'C1_C3_derivations.json', 'generation.json'])
    files = [destination/name for name in sorted(managed_names)]
    dump(destination/'manifest.json', {'hash_algorithm': 'sha256', 'files': {
        p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--compile-pdf', action='store_true',
                        help='Recompile the full authored note with pdflatex; otherwise copy the supplied PDF')
    args = parser.parse_args()
    print(json.dumps(generate(args.out, args.compile_pdf), ensure_ascii=False, indent=2))
