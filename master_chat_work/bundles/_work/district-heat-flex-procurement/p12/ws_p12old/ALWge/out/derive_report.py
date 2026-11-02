import os, runpy, sys
os.environ["VARIANT_FLAG"] = "ALWge"
os.environ["VARIANT_TESTS"] = "/k/p12/new_tests.py"
runpy.run_path("/k/p12/variant.py", run_name="__main__")
