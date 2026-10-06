"""Apply config rules to data/items.json, then write digest.md and page/index.html."""
import datetime, json, os
from classify import TOPICS, apply_rules

cfg = json.load(open("config.json"))
items = json.load(open("data/items.json"))
labels, tl = cfg["sender_labels"], cfg["topic_labels"]

rows = []
for it in items:
    a = apply_rules(it, cfg)
    rows.append({
        "id": a["id"], "date": a["date"], "subject": a["subject"],
        "sender_label": labels.get(a["sender"], a["sender"]),
        "summary": a.get("summary", ""), "excerpt": a.get("excerpt", ""),
        "points": a.get("points", []), "purpose": a.get("purpose", ""), "action": a.get("action", ""), "depth": a.get("depth", "full"), "meat": a.get("meat", []),
        "topics": a["topics"], "tags": a["tags"], "status": a["status"], "reason": a["reason"],
        "actionability": round(a["raw"]["actionability"], 2),
        "url": a.get("url") or f'https://mail.google.com/mail/?authuser={cfg["gmail_account"]}#all/{a["id"]}',
    })
rows.sort(key=lambda r: r["date"], reverse=True)
today = datetime.date.today().isoformat()
live = [r for r in rows if r["status"] != "excluded"]

# page
data = {"items": rows, "generated": datetime.date.today().strftime("%b %-d, %Y")}
html = open("page/template.html").read()
html = html.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
html = html.replace("/*__TOPICS__*/null", json.dumps(tl, ensure_ascii=False))
pb = json.load(open("data/playbooks.json")) if os.path.exists("data/playbooks.json") else []
html = html.replace("/*__PLAYBOOKS__*/null", json.dumps(pb, ensure_ascii=False).replace("</", "<\\/"))
html = html.replace("/*__PBTHEMES__*/null", json.dumps(cfg["playbook_themes"], ensure_ascii=False))
open("page/index.html", "w").write(html)

# one readable markdown file per playbook
os.makedirs("data/playbooks", exist_ok=True)
for p in pb:
    md = [f"# {p['title']}", "", f"Source: {p['source']}, {p['date']} ({p['url']})", f"Themes: {', '.join(cfg['playbook_themes'][t] for t in p['themes'])}", "", f"**For:** {p['purpose']}", f"**You end up with:** {p['outcome']}", f"**You need:** {'; '.join(p['need'])}", f"**Time:** {p['time']}", ""]
    for i, s in enumerate(p["steps"], 1):
        md += [f"## {i}. {s['title']}", ""] + [f"- {d}" for d in s["do"]] + [""]
        for pr in s.get("prompts", []):
            md += [f"**{pr['label']}** ({'added by this tool' if pr['src']=='added' else 'verbatim from the author'})", "", "```", pr["text"], "```", ""]
        if s.get("fallback"):
            md += [f"**Other LLM or manual version:** {s['fallback']}", ""]
    if p.get("tips"): md += ["**Tips:** " + " ".join(p["tips"]), ""]
    if p.get("missing"): md += ["_Not in the visible text:_ " + p["missing"], ""]
    open(f"data/playbooks/{p['id']}.md", "w").write("\n".join(md))

# markdown
def line(r, full=False):
    d = r["date"][:10]
    tags = " ".join(f"`{t}`" for t in r["tags"])
    s = r["summary"] or r["excerpt"]
    note = {"partial": " _(preview only, rest is paywalled)_", "teaser": " _(teaser, full piece is members-only)_"}.get(r["depth"], "")
    pts = "".join(f"\n  - {p}" for p in r["points"]) if full else ""
    act = f"\n  - **Do this:** {r['action']}" if r["action"] else ""
    purpose = f"\n  - **Purpose:** {r['purpose']}" if r["purpose"] else ""
    return f'- **{r["subject"]}** ({r["sender_label"]}, {d}, actionability {r["actionability"]:.1f}) {tags}{note}  \n  {s}{purpose}{pts}{act}\n  [{"Gmail" if "mail.google" in r["url"] else "Post"}]({r["url"]})'

out = [f"# PMM Reading Digest", "",
       f"Generated {today}. {len(live)} items kept, {len(rows)-len(live)} filtered out. Edit `sources.json` and `config.json` to change what is watched and how strict the filters are; see README.md.", "",
       "## Best things to act on", ""]
top = sorted([r for r in live if "actionable" in r["tags"]], key=lambda r: -r["actionability"])[:8]
out += [line(r, True) for r in top] or ["_Nothing flagged yet._"]
out += ["", "## Frameworks", ""]
out += [line(r, True) for r in live if "framework" in r["tags"]] or ["_None yet._"]
out += ["", "## By topic", ""]
for t in list(TOPICS) + ["uncategorized"]:
    members = [r for r in live if (t in r["topics"]) or (t == "uncategorized" and r["status"] == "uncategorized")]
    if not members:
        continue
    out += [f"### {tl[t]} ({len(members)})", ""] + [line(r) for r in members] + [""]
out += ["## Filtered out", ""]
out += [f'- {r["subject"]} ({r["sender_label"]}, {r["date"][:10]}): {r["reason"]}' for r in rows if r["status"] == "excluded"]
open("digest.md", "w").write("\n".join(out) + "\n")
print(f"built: {len(live)} kept, {len(rows)-len(live)} filtered; digest.md and page/index.html written")
