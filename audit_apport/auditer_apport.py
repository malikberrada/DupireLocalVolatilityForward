"""Run inside the project's Python environment after installing dupire-joint 0.1.6."""
if __name__ == "__main__":
    import multiprocessing
    import sys
    multiprocessing.freeze_support()
    try:
        from dossier.app import main
        raise SystemExit(main())
    except (ImportError, FileNotFoundError, ValueError, ArithmeticError, KeyError, OSError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr, flush=True)
        print("Inputs were preserved. No incomplete trace or numerical solver status is promoted to a proof.",
              file=sys.stderr, flush=True)
        raise SystemExit(2) from None
