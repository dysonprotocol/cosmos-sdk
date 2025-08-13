if __name__ == "__main__":
    import sys

    if sys.argv[1] == "exec_script":
        from . import dysvm_server
        dysvm_server.main(*sys.argv[2:])

    elif sys.argv[1] == "run_wsgi":
        from . import dyswsgi
        dyswsgi.main(*sys.argv[2:])
    
    elif sys.argv[1] == "run_benchmark":
        import json
        from . import fp_benchmark
        iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        details = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else True
        result = fp_benchmark.detect_fp_differences(iterations, details)
        print(json.dumps(result))
    
    elif sys.argv[1] == "dys_format":
        import black
        from . import DysEval

        code = sys.stdin.read()

        def _pos(exc):
            n = getattr(exc, "lineno", None)
            c = getattr(exc, "offset", None) or getattr(exc, "col_offset", None) or getattr(exc, "colno", None)
            if n is None:
                node = getattr(exc, "node", None)
                if node is not None:
                    n = getattr(node, "lineno", None)
                    c = getattr(node, "col_offset", None)
            return n, c

        try:
            DysEval().validate(code)
        except Exception as e:
            n, c = _pos(e)
            print(f"Error validating code: {e} line={n} col={c} type={type(e)}")
            sys.exit(1)

        try:
            formatted_code = black.format_str(code, mode=black.Mode())
            print(formatted_code)
        except Exception as e:
            n, c = _pos(e)
            if n is None:
                inner = getattr(e, "exc", None)
                if inner is not None:
                    n, c = _pos(inner)
            print(f"Error formatting code: {e} line={n} col={c}")
            sys.exit(1)

