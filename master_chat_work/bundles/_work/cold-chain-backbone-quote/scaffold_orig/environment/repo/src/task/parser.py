import json


def parse_events(text):
    payload = json.loads(text)
    return payload["rows"]
