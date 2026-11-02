#!/usr/bin/env python3
"""Print saved image IDs for one conservative cleanup category; never calls Docker."""
import csv
import json
import sys
from pathlib import Path

allowed={'parked/dropped task','dangling'}
if len(sys.argv)!=2 or sys.argv[1] not in allowed:
    raise SystemExit('usage: list_cleanup_ids.py "parked/dropped task"|dangling')
path=Path(__file__).resolve().parents[1]/'IMAGES.csv'
tb=Path('/Users/mac/Desktop/Terminal Bench')
stage={t['slug']: t.get('pipeline',{}).get('stage','') for t in json.load((tb/'master_chat_tasks/registry/tasks.json').open())['tasks']}
for row in csv.DictReader(path.open()):
    if row['category']==sys.argv[1] and row['containers']=='0':
        if sys.argv[1]=='parked/dropped task' and stage.get(row['task_slug']) not in {'parked','dropped','killed'}:
            continue
        print(row['image_id'])
