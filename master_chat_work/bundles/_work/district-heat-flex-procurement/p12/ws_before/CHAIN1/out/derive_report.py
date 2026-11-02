import os, runpy, sys
os.environ["VARIANT_FLAG"] = "CHAIN1"
os.environ["VARIANT_TESTS"] = "/k/p12/before/tests/test_output.py"
runpy.run_path("/k/p12/variant.py", run_name="__main__")
