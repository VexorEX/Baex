import json
def load_json(filename, default=None):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if data else (default or {})
    except Exception as e:
        return default or {}


print(load_json(filename="main/modules/cmd.json"))