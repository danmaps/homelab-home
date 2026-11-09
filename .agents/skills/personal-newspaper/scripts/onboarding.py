"""Guided intake and configurable full-edition page planning."""
from copy import deepcopy
from datetime import time
import re
from zoneinfo import ZoneInfo


QUESTION_GROUPS = [
    {"id": "basics", "questions": [
        "What should the newspaper be called, who is it for, and what city and IANA time zone should it use?",
        "Would you like US Letter or A4, and the full newspaper or a shorter selection of sections?"
    ]},
    {"id": "household", "questions": [
        "Who should have personal pages? Give preferred names, adult/child roles, interests and optional reading levels; exact birthdates are unnecessary.",
        "Which children need grades, current-term assignments and every open task/subtask? Which exact school portals and task lists belong to each person?",
        "Which shared school, lunch, club, Scout or other activity sources should appear on the two Family Desk pages?",
        "Who should have the adult personal desk, and whom would you like a discussion desk for?"
    ]},
    {"id": "sources", "questions": [
        "Which mail accounts/folders, calendars and task lists may the agent read? What date ranges and source-access limitations apply?",
        "Which newsletters, feeds, publications, official video channels and personal interests should it cover? Suggest discoveries for selection.",
        "Would you like organization and industry reading pages? Which sources require EVERY new topic plus older still-active notices, including secondary topics?",
        "What are the school's verified current term dates? If unavailable, should the paper continue with the academic coverage gap stated?"
    ]},
    {"id": "art_and_games", "questions": [
        "Would you like one full-width illustration on every page, optional artwork, or text only? Which people should get three-panel comics?",
        "What art style, humor level, clothing colors and approved character references should be used? Are there optional pets, and which markings must remain accurate?",
        "Who would enjoy drawing lessons? Choose subjects, breeds/poses to rotate, and numbered-step detail; dog-and-cat pairs are available.",
        "Which puzzles would you like: personalized 5x5 crossword, four-word Jumble, unique Sudoku, and chess mate-in-one? One compact game page or two roomy pages?"
    ]},
    {"id": "privacy_and_delivery", "questions": [
        "What must stay out of print and artwork prompts? Suggested exclusions: credentials, home addresses, tracking numbers, private money and medical detail.",
        "Should delivery mean a checked local PDF or a verified sent email? For email, confirm exact recipients and the account/tool that may send it.",
        "Should there be a recurring edition? Specify local start, readiness target and deadline, and identify any existing newspaper schedule to reuse.",
        "Would you like printing? Specify printer, paper, color and duplex settings. Automatic printing begins only after a submitted test and your confirmation of the physical result."
    ]}
]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    check(isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", value),
          "Use stable lowercase identifiers, starting with a letter.")
    return value


def build_profile(answers):
    check(answers.get("confirmed") is True, "Setup answers must be reviewed and confirmed by the new user.")
    check(answers.get("title", "").strip(), "Choose a newspaper title.")
    ZoneInfo(answers["timezone"])
    check(answers.get("paper", "Letter") in {"Letter", "A4"}, "Choose Letter or A4.")
    members = deepcopy(answers.get("members", []))
    seen = set()
    for member in members:
        identity = identifier(member["id"])
        check(identity not in seen and member.get("name", "").strip(), "Each person needs a unique ID and name.")
        check(member.get("role") in {"adult", "child"}, "Member roles are adult or child.")
        check(not member.get("todo_required") or member.get("todo_lists"), "Exact task lists are required for complete TODO coverage.")
        seen.add(identity)
    owner = answers.get("owner_id")
    discussion = answers.get("discussion_person_id")
    check(owner is None or owner in seen, "Choose an existing person for the personal desk.")
    check(discussion is None or discussion in seen, "Choose an existing person for the discussion desk.")
    check(not discussion or owner, "A discussion desk needs a personal-desk owner.")
    by_id = {m["id"]: m for m in members}
    sections = [{"id": "today", "title": "Today", "kind": "front"}]
    planning = answers.get("planning", True)
    if planning:
        sections += [{"id": key, "title": title, "kind": "planning", "window": key}
                     for key, title in (("tomorrow", "Tomorrow"), ("week", "Next Seven Days"), ("month", "Next 30 Days"))]
    if answers.get("family_desk", bool(members)):
        sections += [{"id": f"family-{n}", "title": "The Family Desk", "kind": "family", "part": n} for n in (1, 2)]
    for person in members:
        if person["role"] == "child" and person.get("pages", True):
            sections += [{"id": f"{person['id']}-{n}", "title": person["name"], "kind": "child",
                          "person_id": person["id"], "part": n} for n in (1, 2)]
    if owner:
        sections += [{"id": f"personal-{n}", "title": by_id[owner]["name"], "kind": "personal",
                      "person_id": owner, "part": n} for n in (1, 2)]
    if discussion:
        sections += [{"id": f"discussion-{n}", "title": "Talk With " + by_id[discussion]["name"],
                      "kind": "discussion", "person_id": discussion, "part": n} for n in (1, 2)]
    reading = deepcopy(answers.get("reading", []))
    for page in reading:
        identifier(page["id"])
        check(page.get("title", "").strip(), "Reading pages need a title.")
        sections.append({**page, "kind": "reading"})
    games = deepcopy(answers.get("games", {"enabled": ["crossword", "jumble", "sudoku", "chess"], "pages": 2}))
    check(set(games.get("enabled", [])).issubset({"crossword", "jumble", "sudoku", "chess"}), "Unknown game.")
    check(games.get("pages", 2) in {1, 2}, "Choose one or two game pages.")
    if games.get("enabled"):
        splits = [games["enabled"]] if games.get("pages", 2) == 1 else [
            [g for g in games["enabled"] if g in {"crossword", "jumble"}],
            [g for g in games["enabled"] if g in {"sudoku", "chess"}]]
        for number, group in enumerate([g for g in splits if g], 1):
            sections.append({"id": f"games-{number}", "title": "Comic and Games" if number == 1 else "More Games",
                             "kind": "games", "games": group})
    check(len({p["id"] for p in sections}) == len(sections), "Page IDs must be unique.")
    source_configs = deepcopy(answers.get("sources", []))
    check(source_configs and len({s["id"] for s in source_configs}) == len(source_configs), "Configure unique sources.")
    for source in source_configs:
        identifier(source["id"])
        source.setdefault("required", True)
        source.setdefault("coverage", "selective")
        source.setdefault("max_age_minutes", 60)
        source.setdefault("page_ids", [])
        check(set(source["page_ids"]).issubset({p["id"] for p in sections}), "Source targets an unknown page.")
        check(source["coverage"] in {"selective", "all_topics"}, "Unknown source coverage mode.")
        check(source["coverage"] != "all_topics" or source["page_ids"], "All-topic sources need target pages.")
    artwork = deepcopy(answers.get("artwork", {"mode": "one_per_page", "daily_fresh": True}))
    check(artwork.get("mode") in {"none", "optional", "one_per_page"}, "Choose an artwork mode.")
    check(set(artwork.get("comic_people", [])).issubset(seen), "Comic characters must be configured people.")
    eligible = {s["person_id"] for s in sections if s.get("person_id")}
    check(set(artwork.get("comic_people", [])).issubset(eligible), "Selected comic people need a personal, child or discussion desk.")
    check(not artwork.get("lesson_person_id") or artwork["lesson_person_id"] in seen, "Drawing lessons need a configured person.")
    if artwork.get("lesson_person_id"):
        check(any(s["kind"] == "child" and s.get("person_id") == artwork["lesson_person_id"] for s in sections),
              "The illustrated lesson needs an enabled child-page pair.")
    check(artwork.get("mode") != "none" or not (artwork.get("comic_people") or artwork.get("lesson_person_id") or artwork.get("back_comic")),
          "Enable artwork to request comics or illustrated lessons.")
    delivery = deepcopy(answers.get("delivery", {"channel": "local_pdf", "recipients": []}))
    check(delivery.get("channel") in {"local_pdf", "email"}, "Choose local_pdf or email delivery.")
    check(delivery["channel"] != "email" or (delivery.get("recipients") and delivery.get("authorization")),
          "Email needs the new user's recipient and authorization record.")
    schedule = {"enabled": False, "requested": False, "start": "05:00", "ready_by": "05:50", "deadline": "06:00",
                **deepcopy(answers.get("schedule", {}))}
    schedule["enabled"] = False
    for key in ("start", "ready_by", "deadline"):
        time.fromisoformat(schedule[key])
    printing = {"requested": False, "printer": None, "color": "Gray", "duplex": "DuplexNoTumble",
                **deepcopy(answers.get("printing", {})), "enabled": False, "test_passed": False, "physical_output_verified": False}
    return {"schema_version": 1, "feature_version": 2, "setup_confirmed": True,
            "title": answers["title"], "timezone": answers["timezone"], "paper": answers.get("paper", "Letter"),
            "city": answers.get("city", ""), "motto": answers.get("motto", "Your day, thoughtfully assembled."),
            "allow_partial": answers.get("allow_partial", True), "members": members, "owner_id": owner,
            "planning": {"enabled": bool(planning), "front_week": answers.get("front_week", True), "family_scope": "parent_actions_only"},
            "sections": sections, "sources": source_configs, "artwork": artwork, "games": games,
            "privacy": deepcopy(answers.get("privacy", {"exclude": ["credentials", "street addresses", "tracking numbers", "private money"]})),
            "delivery": delivery, "printing": printing, "schedule": schedule}


def registry(profile):
    return {"schema_version": 1, "sources": [{"id": s["id"], "discovery_path": s.get("discovery_path", "Set up with the new user's connector"),
            "page_ids": s.get("page_ids", []), "scope": s.get("scope", "Confirm configured scope"),
            "last_verified_at": None, "newest_issue_id": None, "limits": "Not collected yet"} for s in profile["sources"]]}
