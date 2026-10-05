"""Classify everything in data/inbox.json and merge into data/items.json. Run via: zsh -ic './.venv/bin/python run_week.py'"""
import json, os, re
from typesafe_sdk import TypeSafeClient
import asyncio
from classify import classify
from extract import run as extract_run

inbox = json.load(open("data/inbox.json")) if os.path.exists("data/inbox.json") else []
items = json.load(open("data/items.json")) if os.path.exists("data/items.json") else []
known = {i["id"] for i in items}

def excerpt(body, subject):
    t = body.replace(subject, "", 1)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:260]

new = 0
os.makedirs("data/bodies", exist_ok=True)
with TypeSafeClient() as client:
    for e in inbox:
        if e["id"] in known:
            continue
        row = classify(client, e)
        open(f"data/bodies/{e['id']}.txt", "w").write(f"{e['subject']}\n{e['sender']} {e['date']}\n\n{e['body']}")
        row["excerpt"] = excerpt(e["body"], e["subject"])
        row["summary"] = ""
        row["points"] = []
        row["action"] = ""
        m = asyncio.run(extract_run(e["id"]))
        row["depth"], row["meat"], row["core"] = m["depth"], m["meat"], m["core"]
        items.append(row)
        new += 1

items.sort(key=lambda r: r["date"], reverse=True)
json.dump(items, open("data/items.json", "w"), indent=1)
json.dump([], open("data/inbox.json", "w"))
print(f"classified {new} new; {len(items)} total")
