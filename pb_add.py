"""Merge playbook records (a JSON list on stdin or in a file) into data/playbooks.json, keyed by id."""
import json, os, sys
src = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
new = json.loads(src)
path = "data/playbooks.json"
cur = {p["id"]: p for p in json.load(open(path))} if os.path.exists(path) else {}
items = {i["id"]: i for i in json.load(open("data/items.json"))}
THEMES = set(json.load(open("config.json"))["playbook_themes"])
for p in new:
    it = items[p["id"]]
    bad = [t for t in p["themes"] if t not in THEMES]
    assert not bad, (p["id"], bad)
    p.setdefault("date", it["date"][:10]); p.setdefault("depth", it.get("depth", "full"))
    p.setdefault("url", it.get("url") or f'https://mail.google.com/mail/?authuser={json.load(open("config.json"))["gmail_account"]}#all/{it["id"]}')
    cur[p["id"]] = p
json.dump(list(cur.values()), open(path, "w"), indent=1, ensure_ascii=False)
print(len(new), "merged;", len(cur), "playbooks total")
