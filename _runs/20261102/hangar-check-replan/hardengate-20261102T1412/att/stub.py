
import json, os, sys
DOCS = {'data_quality.json': {}, 'policy_audit.json': {}, 'region_East.json': {}, 'region_North.json': {}, 'region_South.json': {}, 'region_West.json': {}, 'segment_commercial.json': {}, 'segment_public.json': {}, 'summary.json': {}}
def main():
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for name, doc in DOCS.items():
        with open(os.path.join(out, name), "w") as f:
            json.dump(doc, f)
main()
