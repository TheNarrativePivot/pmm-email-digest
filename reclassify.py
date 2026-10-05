"""Refresh raw judgments for every stored item from data/bodies (use after adding or rewording a question)."""
import json, os
from typesafe_sdk import TypeSafeClient
from classify import classify
items = json.load(open("data/items.json"))
with TypeSafeClient() as client:
    for it in items:
        p = f"data/bodies/{it['id']}.txt"
        if not os.path.exists(p):
            continue
        subject, meta, body = open(p).read().split("\n", 2)
        row = classify(client, {"id": it["id"], "date": it["date"], "sender": it["sender"], "subject": it["subject"], "body": body})
        it["raw"] = row["raw"]
json.dump(items, open("data/items.json", "w"), indent=1, ensure_ascii=False)
print("reclassified", len(items))
