"""Turn saved Gmail get_thread dumps into data/inbox.json (new, unseen emails only).
Usage: python ingest.py <dir-with-get_thread-dumps> [--expect id1,id2,...]"""
import glob, json, os, re, sys

src = sys.argv[1]
expect = []
if "--expect" in sys.argv:
    expect = sys.argv[sys.argv.index("--expect") + 1].split(",")

known = set()
if os.path.exists("data/items.json"):
    known = {i["id"] for i in json.load(open("data/items.json"))}

out, seen = [], set()
for f in sorted(glob.glob(f"{src}/mcp-0136*get_thread*") + glob.glob(f"{src}/toolu_*.txt") + glob.glob("data/raw/*.json")):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    if "messages" not in d:
        continue
    for m in d["messages"]:
        if m["id"] in seen or m["id"] in known or "SENT" in m.get("labelIds", []):
            continue
        seen.add(m["id"])
        text = m.get("plaintextBody") or ""
        text = re.sub(r"\[https?://[^\]]*\]", "", text)
        text = re.sub(r"\(\s*https?://[^)]*\)", "", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"[ \t‌͏​\xa0]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
        out.append({"id": m["id"], "date": m["date"], "sender": m["sender"],
                    "subject": m["subject"], "body": text})

os.makedirs("data", exist_ok=True)
json.dump(out, open("data/inbox.json", "w"), indent=1)
print(f"{len(out)} new emails written to data/inbox.json")
missing = [e for e in expect if e not in seen and e not in known]
if missing:
    print("MISSING (refetch these, parallel downloads can overwrite each other):", ",".join(missing))
