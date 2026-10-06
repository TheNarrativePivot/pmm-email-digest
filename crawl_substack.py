"""Crawl watched Substack publications and append new posts to data/inbox.json (same shape ingest.py writes).
Uses each publication's public JSON endpoints (/api/v1/archive and /api/v1/posts/<slug>), not page scraping.
Run AFTER ingest.py, which rewrites inbox.json; this script appends and de-duplicates.
Usage: python crawl_substack.py [--since YYYY-MM-DD] [--only host]"""
import datetime, html, json, os, re, sys, time, urllib.request
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; pmm-digest/1.0; personal reading digest)"
DEFAULT_SINCE = "2026-06-15"
PAYWALL_MARKER = "[[PAYWALL]]"
PAUSE = 0.6  # seconds between requests

BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "figure", "div", "ul", "ol", "table", "tr", "hr"}
SKIP_CLASS = re.compile(r"subscription-widget|button-wrapper|captioned-button|share-dialog|footnote-anchor|image-link|poll-embed|embedded-post|pencraft")

class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.stack = [], 0, []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        skip = tag in ("script", "style", "svg", "button", "iframe") or bool(SKIP_CLASS.search(cls))
        self.stack.append(skip and tag not in ("p",))
        if self.stack[-1]:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in BLOCK:
            self.out.append("\n\n")
        if tag == "li":
            self.out.append("\n* ")
        if tag == "br":
            self.out.append("\n")

    def handle_endtag(self, tag):
        if self.stack and self.stack.pop():
            self.skip -= 1
        elif not self.skip and tag in BLOCK:
            self.out.append("\n\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

def to_text(body_html):
    p = Text()
    p.feed(body_html or "")
    t = "".join(p.out)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[ \t\xa0​]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 2:
                print(f"  failed {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))

def crawl(host, since, known):
    found, offset, done = [], 0, False
    while not done:
        page = get(f"https://{host}/api/v1/archive?sort=new&limit=25&offset={offset}")
        time.sleep(PAUSE)
        if not page:
            break
        for p in page:
            if p["post_date"][:10] < since:
                done = True
                break
            if p.get("type") != "newsletter":
                continue
            pid = f"sub-{host.split('.')[0]}-{p['slug']}"[:120]
            if pid in known:
                continue
            full = get(f"https://{host}/api/v1/posts/{p['slug']}")
            time.sleep(PAUSE)
            if not full:
                continue
            text = to_text(full.get("body_html"))
            if full.get("audience") == "only_paid" and "paywall" in (full.get("body_html") or "") or p.get("audience") == "only_paid":
                text += f"\n\n{PAYWALL_MARKER}"
            found.append({"id": pid, "date": p["post_date"], "sender": host, "subject": html.unescape(p["title"]),
                          "body": text, "url": p.get("canonical_url") or f"https://{host}/p/{p['slug']}"})
        if len(page) < 25:
            break
        offset += 25
    return found

if __name__ == "__main__":
    src = json.load(open("sources.json")).get("substack", [])
    hosts = [s["host"] if isinstance(s, dict) else s for s in src]
    if "--only" in sys.argv:
        hosts = [sys.argv[sys.argv.index("--only") + 1]]
    state = json.load(open("data/state.json")) if os.path.exists("data/state.json") else {}
    since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else state.get("last_crawl", DEFAULT_SINCE)
    known = {i["id"] for i in json.load(open("data/items.json"))} if os.path.exists("data/items.json") else set()
    inbox = json.load(open("data/inbox.json")) if os.path.exists("data/inbox.json") else []
    have = {e["id"] for e in inbox}
    added = 0
    for h in hosts:
        new = [e for e in crawl(h, since, known | have)]
        print(f"{h}: {len(new)} new since {since}")
        inbox += new
        added += len(new)
    json.dump(inbox, open("data/inbox.json", "w"), indent=1, ensure_ascii=False)
    state["last_crawl"] = datetime.date.today().isoformat()
    json.dump(state, open("data/state.json", "w"), indent=2)
    print(f"{added} Substack posts appended to data/inbox.json ({len(inbox)} total pending)")
