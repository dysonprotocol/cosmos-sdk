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
        from . import DysEval, DysRuntimeError

        code = sys.stdin.read()

        try:
            DysEval().validate(code)
        except Exception as e:
            print(f"Error validating code: {e} type={type(e)}")
            sys.exit(1)

        try:
            formatted_code = black.format_str(code, mode=black.Mode())
            print(formatted_code)
        except Exception as e:
            print(f"Error formatting code: {e}")
            sys.exit(1)

