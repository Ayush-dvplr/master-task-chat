import os, runpy, sys
os.environ["VARIANT_FLAG"] = "REENTRY"
os.environ["VARIANT_TESTS"] = "/b/tests/test_output.py"
runpy.run_path("/k/p12/variant.py", run_name="__main__")
