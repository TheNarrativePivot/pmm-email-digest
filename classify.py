"""Classify newsletter emails with TypeSafe System One.
Raw judgments are stored per email; thresholds and exclusions live in config.json and apply afterwards,
so retuning never needs a rerun."""
import json, re, sys
from typesafe_sdk import Noul, Score, TypeSafeClient

MAX_CHARS = 7000

TOPICS = {
    "positioning": "market or category positioning, differentiation, narrative, or who a product is for",
    "messaging": "messaging, value propositions, copy, or how to talk about a product",
    "gtm_launch": "go-to-market strategy, product launches, channels, demand generation, or campaign planning",
    "sales_enablement": "sales enablement, battlecards, call coaching, or playbooks for sales reps",
    "competitive_research": "competitive intelligence, market research, or customer research and insight methods",
    "pricing_packaging": "pricing, packaging, tiering, or monetization",
    "ai_for_pmm": "using AI tools, agents, or prompts in product marketing or revenue work",
    "product_strategy": "product management, roadmaps, or product strategy",
}

def questions():
    q = {}
    for k, desc in TOPICS.items():
        q[f"topic_{k}"] = Noul(
            instructions=f"Is a substantial part of this newsletter issue about {desc}? Answer yes only if the issue gives it real attention, not a passing mention.")
    q["has_framework"] = Noul(
        instructions="Does this issue present a named or clearly structured, reusable model or method (for example named steps, a matrix, or a template) that a product marketer could apply to their own work? Opinions, case studies and news do not count unless they are packaged as a reusable model.")
    q["has_actionable"] = Noul(
        instructions="Does this issue give a concrete step, template, prompt, checklist, or tool the reader could set up and use this week?")
    q["has_idea"] = Noul(
        instructions="Does this issue contain an original or surprising idea, argument, or case study worth remembering, beyond restating common advice?")
    q["is_promo"] = Noul(
        instructions="Ignoring any sponsor or advertising blocks, is the main body of this issue itself a promotion for an event, course, community, membership, or product, with little standalone educational content?")
    q["is_career"] = Noul(
        instructions="Is this issue mainly about the reader's own career or role rather than about how to do the work itself? This includes jobs, hiring, job markets, salaries, promotions, joining a professional community, and onboarding into a new role (first 30, 60, 90 or 100 days, ramp plans, managing your own calendar or priorities as a new leader).")
    q["is_roundup"] = Noul(
        instructions="Is this issue mainly a roundup, index, or monthly review of other articles or content (a list of reads with a line or two about each), with no standalone method or argument of its own?")
    q["actionability"] = Score(
        instructions="How actionable is this issue for a product marketer?",
        criteria=[
            "No takeaway: news, opinion or promotion with nothing to apply",
            "Context only: interesting background but no clear next step",
            "Directional: suggests an approach but leaves the reader to design it",
            "Specific: describes a method with enough detail to try",
            "Ready to use: includes a template, prompt, checklist or step-by-step the reader can copy and apply immediately",
        ])
    return q

def classify(client, email):
    state = {"newsletter_sender": email["sender"], "subject": email["subject"], "body": email["body"][:MAX_CHARS]}
    r = client.system_one(state=state, questions=questions())
    raw = {k: r.nouls[k].noul for k in r.nouls}
    raw["actionability"] = r.scores["actionability"].score
    return {"id": email["id"], "date": email["date"], "sender": email["sender"],
            "subject": email["subject"], "raw": raw}

def apply_rules(row, cfg):
    raw = row["raw"]
    if re.search(cfg["exclude_subject_regex"], row["subject"], re.I):
        return {**row, "status": "excluded", "reason": "subject rule", "topics": [], "tags": []}
    if raw["is_career"] >= cfg["career_exclude_threshold"]:
        return {**row, "status": "excluded", "reason": "career/jobs", "topics": [], "tags": []}
    if raw.get("is_roundup", 0) >= cfg.get("roundup_exclude_threshold", 1.1):
        return {**row, "status": "excluded", "reason": "roundup of other content", "topics": [], "tags": []}
    if raw["is_promo"] >= cfg["promo_exclude_threshold"]:
        return {**row, "status": "excluded", "reason": "promo", "topics": [], "tags": []}
    topics = [k for k in TOPICS if raw[f"topic_{k}"] >= cfg["topic_threshold"]]
    tags = [t for t, k in (("framework", "has_framework"), ("actionable", "has_actionable"), ("idea", "has_idea"))
            if raw[k] >= cfg["tag_threshold"]]
    return {**row, "status": "kept" if topics else "uncategorized", "reason": "", "topics": topics, "tags": tags}
