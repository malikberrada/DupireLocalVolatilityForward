"""Adapter for a genuine user-provided pricer; contains no substitute model."""
from fractions import Fraction as Q
import argparse
import csv
import importlib
import json
import math
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--problem',type=Path,required=True)
    p.add_argument('--pricer',required=True,help='Importable MODULE:FUNCTION implementing price(T,x)')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if ':' not in a.pricer:p.error('Use MODULE:FUNCTION')
    module,function=a.pricer.split(':',1)
    sys.path.insert(0,str(Path.cwd()))
    price=getattr(importlib.import_module(module),function)
    from dupire_joint.finite_criterion import Problem
    problem=Problem.load(json.loads(a.problem.read_text(encoding='utf-8-sig')))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['time','x','price'])
        for t in problem.times:
            for x in problem.strikes:
                value=price(float(t),float(x))
                if isinstance(value,(str,Q,int)):exact=Q(value)
                else:
                    number=float(value)
                    if not math.isfinite(number):raise ValueError('Nonfinite price returned by the external implementation')
                    exact=Q(number)
                writer.writerow([str(t),str(x),str(exact)])
    print(str(a.out.resolve()),flush=True)


if __name__=='__main__':main()
