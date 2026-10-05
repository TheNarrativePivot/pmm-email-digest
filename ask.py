"""Deep question over the whole repository, on this machine, using TypeSafe to judge relevance.
Usage: zsh -ic './.venv/bin/python ask.py "how do I position against a bigger competitor?"'
Pipeline: keyword + synonym retrieval picks ~60 candidate passages from every stored email; TypeSafe judges each
candidate against your question (a yes/no probability); the best passages are printed with their sources.
Claude (in a Claude Code session) can then answer from just those few passages instead of reading emails."""
import asyncio, json, math, re, sys
from collections import Counter
from typesafe_sdk import AsyncTypeSafeClient, Noul
from classify import apply_rules
ACCOUNT = json.load(open("config.json")).get("gmail_account", "")

STOP = set("a an the and or of to in on for with is are was were be been it its this that these those as at by from how do does did i we you your our can should would could what which who when where why about into than then so if not no yes but my me us they them their there".split())
SYN = {"position": ["differentiation", "category", "competitive", "compete"], "message": ["value", "prop", "copy", "narrative"], "competitor": ["competitive", "battlecard", "rival", "compete"], "launch": ["gtm", "release", "tier", "ship"], "ai": ["claude", "prompt", "agent", "llm"], "safe": ["security", "privacy", "risk", "governance"], "measure": ["metric", "kpi", "roi", "impact"], "enablement": ["sales", "rep", "coaching"], "price": ["packaging", "tier"], "plan": ["roadmap", "process"]}
stem = lambda w: re.sub(r"(ing|ed|es|ly|s)$", "", w)
toks = lambda s: [stem(w) for w in re.findall(r"[a-z0-9][a-z0-9'-]*", s.lower()) if w not in STOP and len(w) > 1]

def load():
    cfg = json.load(open("config.json"))
    passages = []
    for it in json.load(open("data/items.json")):
        if apply_rules(it, cfg)["status"] == "excluded":
            continue
        texts = [" ".join(filter(None, [it.get("summary"), it.get("action")]))] + it.get("points", []) + it.get("meat", [])
        for t in texts:
            if t and len(t) > 20:
                passages.append({"item": it, "text": t, "toks": toks(t)})
    return passages

def candidates(q, passages, n=60):
    base = toks(q); allw = set(base)
    for b in base:
        for k, v in SYN.items():
            if b == stem(k) or b in map(stem, v):
                allw |= {stem(k), *map(stem, v)}
    df = Counter(w for p in passages for w in set(p["toks"]))
    N = len(passages)
    def score(p):
        tf = Counter(p["toks"]); s = 0
        for w in allw:
            if tf[w]:
                s += (1 if w in base else .45) * math.log(1 + (N - df[w] + .5) / (df[w] + .5)) * (tf[w] * 2.2) / (tf[w] + 1.2)
        return s
    ranked = sorted(passages, key=score, reverse=True)
    return [p for p in ranked[:n] if score(p) > 0]

async def judge(client, sem, q, p):
    async with sem:
        r = await client.system_one(
            state={"question": q, "passage": p["text"][:1500], "source_title": p["item"]["subject"]},
            questions={"helps": Noul(instructions="Does this passage contain information that directly helps answer the question (a method, step, finding, example, or number the asker could use)? Passages that only mention the topic in passing do not count.")})
        return r.nouls["helps"].noul

async def main(q):
    passages = load()
    cands = candidates(q, passages)
    sem = asyncio.Semaphore(8)
    async with AsyncTypeSafeClient() as client:
        probs = await asyncio.gather(*[judge(client, sem, q, p) for p in cands])
    ranked = sorted(zip(probs, cands), key=lambda x: -x[0])
    print(f"Q: {q}\nsearched {len(passages)} passages across {len({p['item']['id'] for p in passages})} emails; judged {len(cands)}\n")
    seen = Counter()
    shown = 0
    for pr, p in ranked:
        if pr < 0.8 or shown >= 8:
            break
        if seen[p["item"]["id"]] >= 2:
            continue
        seen[p["item"]["id"]] += 1; shown += 1
        it = p["item"]
        print(f'[{pr:.2f}] {it["subject"]} ({it["sender"].split("@")[0]}, {it["date"][:10]}, {it.get("depth", "full")})')
        print("   " + " ".join(p["text"].split())[:420])
        print(f'   https://mail.google.com/mail/?authuser={ACCOUNT}#all/{it["id"]}\n')
    if not shown:
        print("No passage clearly answers this. Try different words, or the topic may not be in the repository yet.")

asyncio.run(main(" ".join(sys.argv[1:])))
