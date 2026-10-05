"""List kept items whose gist/points/action are still empty, with only the core passages Claude needs to read."""
import json
from classify import apply_rules
cfg = json.load(open("config.json"))
for it in json.load(open("data/items.json")):
    if it.get("summary"):
        continue
    if apply_rules(it, cfg)["status"] == "excluded":
        continue
    print(f'### {it["id"]} | {it["subject"]} | {it["sender"]} | depth={it.get("depth","?")}')
    print("\n".join(" ".join(c.split())[:420] for c in it.get("core", [])) or "(no substantive passages found)")
    print()
