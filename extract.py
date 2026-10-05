"""Pick the 'meat' of each email with TypeSafe, so Claude only has to read the selected passages.
Code splits the body into blocks; TypeSafe judges each block's role; code keeps the useful ones, in order, verbatim.
Usage: python extract.py <id> [<id> ...]   (reads data/bodies/<id>.txt, writes data/meat/<id>.json)"""
import asyncio, json, os, re, sys
from typesafe_sdk import AsyncTypeSafeClient, Choice

ROLES = {
    "steps": "A concrete step, method, framework element, template, checklist item, tactic, or recommendation the reader could apply (including the heading that names it).",
    "insight": "A central claim, finding, statistic, or argument that explains why the approach matters or how the situation works.",
    "example": "A specific example, case study, or quote that illustrates a point already made.",
    "setup": "A hook, personal story, scene-setting, context, or transition that introduces the topic without adding new substance.",
    "promo": "An advertisement, sponsor block, membership or event pitch, call to action, subscription or footer text.",
    "links": "A list of other articles, links, upcoming events, or navigation.",
}
CORE_BUDGET = 1800
BOILER = re.compile(r"(View in browser|Unsubscribe|Subscription details|Manage subscription|Read on LinkedIn|Member since)", re.I)

def split_long(b, limit=700):
    """Some sources (LinkedIn) arrive as one giant paragraph; chunk on sentence ends."""
    if len(b) <= limit * 1.4:
        return [b]
    sents = re.split(r"(?<=[.?!])\s+(?=[A-Z0-9\"“])", b)
    chunks, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) > limit:
            chunks.append(cur.strip()); cur = ""
        cur += s + " "
    if cur.strip():
        chunks.append(cur.strip())
    return chunks

def blocks(body):
    parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    out, pending = [], ""
    for p in parts:
        is_head = len(p) < 70 and not p.endswith((".", "?", ":")) and "\n" not in p.strip("-*\n ")
        if re.fullmatch(r"[-*=\s]+", p):
            continue
        if is_head and len(p) < 70:
            pending += p + "\n"
            continue
        out.append((pending + p).strip()); pending = ""
    if pending:
        out.append(pending.strip())
    out = [c for b in out for c in split_long(b)]
    return [b for b in out if len(b) > 25 and not BOILER.search(b[:80])]

async def judge(client, sem, subject, prev, text):
    async with sem:
        r = await client.system_one(
            state={"newsletter_subject": subject, "previous_passage": prev[-300:], "passage": text[:2000]},
            questions={"role": Choice(
                instructions="What role does this passage play in the newsletter, for a busy product marketer who wants the substance and none of the filler?",
                criteria=ROLES)})
        p = r.choices["role"].probabilities
        return {"role": r.choices["role"].choice, "p": p}

async def run(email_id):
    raw = open(f"data/bodies/{email_id}.txt").read()
    subject, _, body = raw.split("\n", 2)
    bl = blocks(body)
    sem = asyncio.Semaphore(8)
    async with AsyncTypeSafeClient() as client:
        res = await asyncio.gather(*[judge(client, sem, subject, bl[i-1] if i else "", b) for i, b in enumerate(bl)])
    rows = [{"text": b, **r, "meat": r["p"].get("steps", 0) + r["p"].get("insight", 0),
             "rank": r["p"].get("steps", 0) + 0.7 * r["p"].get("insight", 0)} for b, r in zip(bl, res)]
    kept = [r for r in rows if r["meat"] >= 0.5]
    # core: highest-ranked passages up to a character budget, back in original order. This is all Claude reads.
    core, used = set(), 0
    for i in sorted(range(len(rows)), key=lambda i: -rows[i]["rank"]):
        if rows[i]["meat"] < 0.5 or used + len(rows[i]["text"]) > CORE_BUDGET:
            continue
        core.add(i); used += len(rows[i]["text"])
    core_text = [rows[i]["text"] for i in sorted(core)]
    depth = "partial" if re.search(r"Upgrade to continue reading", body) else ("teaser" if re.search(r"included in your Insider plan|waiting in your Insider dashboard", body) else "full")
    out = {"id": email_id, "subject": subject, "depth": depth, "blocks": len(rows),
           "chars_total": len(body), "chars_meat": sum(len(r["text"]) for r in kept),
           "meat": [r["text"] for r in kept], "core": core_text, "chars_core": used, "roles": [(r["role"], round(r["meat"], 2)) for r in rows]}
    os.makedirs("data/meat", exist_ok=True)
    json.dump(out, open(f"data/meat/{email_id}.json", "w"), indent=1, ensure_ascii=False)
    return out

if __name__ == "__main__":
    for i in sys.argv[1:]:
        o = asyncio.run(run(i))
        print(f'{o["subject"][:50]} | depth={o["depth"]} blocks={o["blocks"]} meat {o["chars_meat"]} core {o["chars_core"]} of {o["chars_total"]}')
