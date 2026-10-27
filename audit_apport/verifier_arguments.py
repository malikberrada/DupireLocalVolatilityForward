"""Check the two scoped mathematical arguments without a solver or network."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dossier.argument_checks import verify_arguments

if __name__ == '__main__':
    print(json.dumps(verify_arguments(), ensure_ascii=False, indent=2))
