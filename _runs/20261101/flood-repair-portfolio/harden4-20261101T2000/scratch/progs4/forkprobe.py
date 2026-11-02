import os, subprocess, sys, time
# fork probe: leaves a child and a double-forked grandchild, then hangs past the book limit
subprocess.Popen(["sleep", "900"])
if os.fork() == 0:
    if os.fork() == 0:
        time.sleep(900)
    os._exit(0)
time.sleep(900)
