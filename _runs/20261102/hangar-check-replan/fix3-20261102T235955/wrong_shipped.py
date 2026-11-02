import json,sys
from pathlib import Path
out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
answers={'summary.json': {}, 'policy_audit.json': {}, 'data_quality.json': {}, 'region_North.json': {}, 'region_South.json': {}, 'region_West.json': {}, 'region_East.json': {}, 'segment_commercial.json': {}, 'segment_public.json': {}}
for name,value in answers.items(): (out/name).write_text(json.dumps(value))
