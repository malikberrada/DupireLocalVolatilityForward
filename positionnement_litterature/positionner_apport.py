"""Run from the project directory after installing dupire-joint 0.1.6."""
if __name__=="__main__":
    import multiprocessing
    import sys
    multiprocessing.freeze_support()
    try:
        from positionnement.app import main
        raise SystemExit(main())
    except (ImportError,FileNotFoundError,ValueError,ArithmeticError) as exc:
        print("ERROR: "+str(exc),file=sys.stderr,flush=True)
        print("Requires the installed dupire-joint 0.1.6 source package. Original inputs are preserved.",file=sys.stderr,flush=True)
        raise SystemExit(2) from None
