"""Render the shipped data folder of depot-charge-plan into BUNDLE/environment/data (stdlib only).
Usage: python3 datagen.py   (seed 905143, kind shipped)"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_core  # noqa: E402

BUNDLE = os.path.join(HERE, "..", "..", "depot-charge-plan")
DATA = os.path.join(BUNDLE, "environment", "data")

if __name__ == "__main__":
    if os.path.isdir(DATA):
        shutil.rmtree(DATA)
    os.makedirs(os.path.join(DATA, "docs"))
    gen_core.render(905143, "shipped", DATA)
    shutil.copyfile(os.path.join(HERE, "docs_master", "charging_rules.md"), os.path.join(DATA, "docs", "charging_rules.md"))
    print("rendered", sorted(os.listdir(DATA)))
