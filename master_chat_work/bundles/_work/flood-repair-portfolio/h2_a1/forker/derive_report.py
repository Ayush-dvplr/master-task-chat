"""Fork-survivor probe (WORK only): a delivered program that leaves workers behind.
It starts a child python3 busy loop, a multiprocessing pool busy on two tasks, and a
double-forked grandchild, a child in its own session, then sleeps past the verifier's per-book limit."""
import multiprocessing as mp
import os
import subprocess
import sys
import time


def spin(_):
    while True:
        pass


if __name__ == "__main__":
    subprocess.Popen([sys.executable, "-c", "while True: pass"])
    pool = mp.Pool(2)
    pool.map_async(spin, range(2))
    if os.fork() == 0:
        if os.fork() == 0:
            time.sleep(10000)
        os._exit(0)
    if os.fork() == 0:
        os.setsid()
        time.sleep(10000)
    time.sleep(10000)
