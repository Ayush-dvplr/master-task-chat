"""Time the reference package and a plain unit-step simulator on one book."""
import subprocess, sys, time, os, pathlib
book, pkg, work = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path[:0] = [os.path.join(work, "engine"), work]
env = dict(os.environ, PYTHONPATH=os.path.join(pkg, "src"), PYTHONDONTWRITEBYTECODE="1")
t0 = time.perf_counter()
subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import leasebook; sys.exit(leasebook.main(sys.argv[2:]))",
                os.path.join(pkg, "src"), book, "/tmp/ref_out"], check=True)
ref = time.perf_counter() - t0
import check_exact, refsim
t0 = time.perf_counter()
refsim.documents(check_exact.parse_book(pathlib.Path(book)))
unit = time.perf_counter() - t0
print("reference_package_s %.2f" % ref)
print("unit_step_sim_s %.2f" % unit)
