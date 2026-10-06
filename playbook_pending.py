"""List kept items that could become playbooks and still have none, with their implementation text.
Source text = passages TypeSafe judged as steps, insight or example (verbatim, original order), plus short setup lines that
introduce a step (e.g. 'Here is the prompt:'). Intros, promos and link lists are dropped.
Usage: python playbook_pending.py [--list] [--max-chars N] [id ...]"""
import json, os, sys
from classify import apply_rules
from extract import blocks

cfg = json.load(open("config.json"))
items = json.load(open("data/items.json"))
done = {p["id"] for p in json.load(open("data/playbooks.json"))} if os.path.exists("data/playbooks.json") else set()
skip = set(json.load(open("data/playbook_skip.json"))) if os.path.exists("data/playbook_skip.json") else set()
cap = int(sys.argv[sys.argv.index("--max-chars") + 1]) if "--max-chars" in sys.argv else 9000
want = [a for a in sys.argv[1:] if a.startswith(("sub-", "1")) or len(a) > 12]

def source_text(it):
    raw = open(f"data/bodies/{it['id']}.txt").read()
    body = raw.split("\n", 2)[2]
    bl = blocks(body)
    roles = json.load(open(f"data/meat/{it['id']}.json"))["roles"]
    out = []
    for i, (b, (role, meat)) in enumerate(zip(bl, roles)):
        nxt = roles[i + 1][0] if i + 1 < len(roles) else ""
        if role in ("steps", "insight", "example") or (role == "setup" and len(b) < 200 and nxt == "steps"):
            out.append(b)
    return out

cands = []
for it in items:
    a = apply_rules(it, cfg)
    if a["status"] == "excluded" or it["id"] in done or it["id"] in skip:
        continue
    if not ({"framework", "actionable"} & set(a["tags"])):
        continue
    if want and it["id"] not in want:
        continue
    cands.append((it, a))

if "--list" in sys.argv:
    for it, a in cands:
        print(f'{it["id"]} | {it["sender"][:22]} | act {it["raw"]["actionability"]:.1f} | {it.get("depth")} | {it["subject"][:70]}')
    sys.exit()
for it, a in cands:
    t = "\n\n".join(source_text(it))[:cap]
    print(f'### {it["id"]} | {it["subject"]} | {it["sender"]} | {it["date"][:10]} | depth={it.get("depth")}\n{t}\n')
