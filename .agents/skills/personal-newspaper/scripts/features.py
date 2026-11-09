"""Family, editorial, artwork and playable-game contracts for full editions."""
from collections import defaultdict
from datetime import date, timedelta
import re

from games import validate_chess, validate_crossword, validate_jumble, validate_sudoku


def need(condition, message):
    if not condition:
        raise ValueError(message)


def useful(value):
    return isinstance(value, str) and bool(value.strip())


def validate_features(profile, snapshot, edition, basic):
    if profile.get("feature_version", 1) < 2:
        return {}
    need(profile.get("setup_confirmed") is True, "Finish the new user's setup before full production.")
    pages = {p["id"]: p for p in edition["pages"]}
    sections = {s["id"]: s for s in profile["sections"]}
    members = {p["id"]: p for p in profile.get("members", [])}
    index = {i["id"]: i for s in snapshot["sources"].values() for i in s["items"]}
    day = date.fromisoformat(edition["date"])
    gaps, terms, games = [], {}, {}
    allowed_kinds = {"front", "planning", "family", "child", "personal", "discussion", "reading", "games"}
    need(all(s.get("kind") in allowed_kinds for s in sections.values()), "Unknown full-edition page kind.")
    need(next(iter(sections.values()))["kind"] == "front", "The full edition starts with Today.")
    # A pair must be physically consecutive and in part order, including adult desks.
    for kind in ("family", "child", "personal", "discussion"):
        groups = defaultdict(list)
        for position, section in enumerate(sections.values()):
            if section["kind"] == kind:
                groups[section.get("person_id", "family")].append((position, section))
        for person, group in groups.items():
            need(len(group) == 2 and [s.get("part") for _, s in group] == [1, 2] and group[1][0] == group[0][0] + 1,
                 f"{kind} pages must be a consecutive two-page pair: {person}")
            if kind != "family":
                need(person in members, "A personal page refers to an unknown household member.")
    family_positions = [n for n, s in enumerate(sections.values()) if s["kind"] == "family"]
    child_positions = [n for n, s in enumerate(sections.values()) if s["kind"] == "child"]
    need(not family_positions or not child_positions or max(family_positions) < min(child_positions),
         "The Family Desk opens the family section before child pages.")
    for person in members:
        found = [i for i in index.values() if i.get("kind") == "school_term" and i.get("person_id") == person
                 and i.get("start_date", "9999") <= edition["date"] <= i.get("end_date", "0000")]
        need(len({(i.get("term_id"), i.get("start_date"), i.get("end_date")) for i in found}) <= 1,
             f"Conflicting current school terms: {person}")
        if found:
            need(useful(found[0].get("term_id")), "School term needs its actual term ID.")
            terms[person] = found[0]

    def current_assignment(item):
        term = terms.get(item.get("person_id"))
        if not term:
            return False
        if item.get("term_id"):
            return item["term_id"] == term["term_id"]
        return bool(item.get("due_date") and term["start_date"] <= item["due_date"][:10] <= term["end_date"])

    def obsolete_task(item):
        assignment = index.get(item.get("assignment_id"))
        return assignment is not None and assignment.get("kind") == "assignment" and not current_assignment(assignment)

    def row_ids(article):
        return sum([article.get(name, []) for name in ("grade_ids", "assignment_ids", "task_ids")], [])

    def coverage_gap(pair, person, module, reason):
        note = [note for p in pair for note in p.get("coverage_notes", []) if note.get("module") == module
                and note.get("status") in {"unavailable", "partial"} and useful(note.get("reason"))]
        need(note, f"Print an explicit {module} coverage note for {person}: {reason}")
        gaps.append({"person_id": person, "module": module, "reason": reason})

    # A required normalized topic cannot be satisfied by invisible metadata.
    for section_id, page in pages.items():
        section = sections[section_id]
        person = section.get("person_id")
        for article in page["articles"]:
            for field, expected_kind in (("grade_ids", "grade"), ("assignment_ids", "assignment"), ("task_ids", "task")):
                need(isinstance(article.get(field, []), list), f"{field} must be a list of source IDs.")
                for identity in article.get(field, []):
                    need(identity in article["source_ids"] and identity in index, "Visible table rows must cite their own source IDs.")
                    need(index[identity].get("kind") == expected_kind, f"Wrong source kind for {field}: {identity}")
                    need(section["kind"] in {"child", "personal"} and index[identity].get("person_id") == person,
                         "Individual grades, assignments and tasks belong on their matching person's pages.")
            if article.get("table"):
                table = article["table"]
                need(table.get("headers") and table.get("rows") and all(len(row) == len(table["headers"]) for row in table["rows"]),
                     "Data table column counts must agree.")
            if section["kind"] == "discussion":
                need(useful(article.get("discussion_question")) and useful(article.get("decision_needed")),
                     "Discussion pages require a shared question and decision, not assigned tasks.")
            if section["kind"] == "planning":
                need(article.get("audience") in {"general", "parent_action"}, "Planning articles need an audience.")
                children = [i for i in article["source_ids"] if index[i].get("person_id") in members
                            and members[index[i]["person_id"]]["role"] == "child"]
                need(not children or article["audience"] == "parent_action", "Child-derived planning requires a real parent action.")
                if article["audience"] == "parent_action":
                    need(useful(article.get("parent_action")), "Describe the concrete parent decision or coordination.")
            for identity in article["source_ids"]:
                item = index[identity]
                if item.get("kind") == "assignment":
                    need(current_assignment(item), "Previous-term or unscoped assignments must not appear anywhere.")
                need(not obsolete_task(item), "A TODO must not revive a previous-term assignment.")
                if item.get("action_status") == "completed":
                    need(article.get("action_status") == "completed", "A completed request cannot be presented as open work.")
                if section["kind"] == "child" and item.get("person_id"):
                    need(item["person_id"] == person, "A child page cites another person's individual record.")

    for person, member in members.items():
        pair = [pages[s["id"]] for s in sections.values() if s.get("person_id") == person and s["kind"] in {"child", "personal"}]
        if not pair:
            continue
        visible = {identity for p in pair for a in p["articles"] for identity in row_ids(a)}
        own_items = [i for i in index.values() if i.get("person_id") == person]
        if member.get("todo_required"):
            scopes = [i for i in own_items if i.get("kind") == "task_scope" and i.get("all_open") is True
                      and i.get("undated") is True and i.get("nested") is True and i.get("scope_complete") is True
                      and set(i.get("lists", [])) == set(member["todo_lists"])]
            if not scopes:
                coverage_gap(pair, person, "tasks", "Exact lists, undated items and nested subtasks were not completely verified.")
            required = {i["id"] for i in own_items if i.get("kind") == "task" and i.get("state", "open") == "open" and not obsolete_task(i)}
            need(required.issubset(visible), f"Every open TODO and nested subtask needs a visible row: {person}: {sorted(required - visible)}")
        if member.get("academics_required"):
            grades = [i for i in own_items if i.get("kind") == "grade"]
            if not grades or not any(i.get("kind") == "grade_scope" and i.get("all_latest") is True for i in own_items):
                coverage_gap(pair, person, "grades", "All latest published course gradebooks were not verified.")
            for grade in grades:
                need(all(key in grade for key in ("course", "mark", "percent", "term_id")), "Published grade fields must remain exact.")
            need({i["id"] for i in grades}.issubset(visible), f"Every latest published grade needs a visible row: {person}")
            if person not in terms:
                coverage_gap(pair, person, "assignments", "The current school term could not be verified.")
            else:
                assignments = {i["id"] for i in own_items if i.get("kind") == "assignment" and current_assignment(i)
                               and i.get("state") in {"open", "missing", "unscored", "completed_late"}}
                need(assignments.issubset(visible), f"Current-term open/unscored/late assignments need visible rows: {person}")
    shared = defaultdict(set)
    for page_id, page in pages.items():
        for article in page["articles"]:
            for identity in article["source_ids"]:
                if index[identity].get("kind") in {"lunch", "shared_notice", "opportunity"}:
                    shared[identity].add(page_id)
    for identity, page_ids in shared.items():
        need(len(page_ids) == 1 and sections[next(iter(page_ids))]["kind"] == "family",
             f"Shared school/lunch/opportunity details appear once on the Family Desk: {identity}")
    # Configured publication/industry pairs retain both identity and order.
    for group in {s.get("pair_group") for s in sections.values() if s.get("pair_group")}:
        positions = [n for n, s in enumerate(sections.values()) if s.get("pair_group") == group]
        need(len(positions) == 2 and positions[1] == positions[0] + 1, "Organization/industry reading pages form one consecutive pair.")
    if profile.get("planning", {}).get("front_week"):
        front = next(pages[s["id"]] for s in sections.values() if s["kind"] == "front")
        week = front.get("front_week", {})
        sunday = day - timedelta(days=(day.weekday() + 1) % 7)
        need(week.get("start_date") == str(sunday) and week.get("end_date") == str(sunday + timedelta(days=7)),
             "The front activity strip runs Sunday through the next Sunday, inclusive.")
        for item in week.get("items", []):
            need(week["start_date"] <= item.get("event_date", "") <= week["end_date"] and item.get("source_ids")
                 and all(identity in index for identity in item["source_ids"]), "Front-week events need correct dates and citations.")
    art = profile.get("artwork", {})
    for section_id, page in pages.items():
        section = sections[section_id]
        comic = page.get("comic")
        if comic:
            need(page.get("image") and page["image"].get("origin") == "generated", "A comic requires its generated combined strip.")
            need(useful(comic.get("premise")) and len(comic.get("captions", [])) == 3 and all(useful(x) for x in comic["captions"]),
                 "A comic needs a fresh premise and exactly three visible HTML captions.")
            need(comic.get("cast_ids") and set(comic["cast_ids"]).issubset(members), "Comic cast must match configured people.")
            refs = set(comic.get("reference_ids", []))
            required_refs = {members[p]["character_reference"] for p in comic["cast_ids"] if members[p].get("character_reference")}
            need(required_refs.issubset(refs), "Use the configured character references for likenesses.")
        if section.get("person_id") in art.get("comic_people", []) and section["kind"] in {"child", "personal", "discussion"} and section.get("part") == 1:
            need(comic, "The requested person's first page needs their personalized comic.")
        if section["kind"] == "games" and section_id == next(s["id"] for s in sections.values() if s["kind"] == "games") and art.get("back_comic"):
            need(comic, "The games page needs the requested back-page comic.")
        lesson_person = art.get("lesson_person_id")
        if lesson_person and section.get("person_id") == lesson_person and section.get("part") == 2 and section["kind"] == "child":
            lesson = page.get("drawing_lesson")
            need(lesson and page.get("image") and not comic, "The second lesson page needs one composite tutorial image.")
            animals = lesson.get("subjects", [])
            need({x.get("species") for x in animals} == set(art.get("lesson_species", ["dog", "cat"])), "Teach all selected drawing subjects.")
            need(len({x.get("pose") for x in animals}) == len(animals), "Drawing subjects need different poses.")
            for animal in animals:
                need(all(useful(animal.get(k)) for k in ("species", "breed", "pose")), "Lesson needs species, breed and pose.")
                need(isinstance(animal.get("steps"), list) and len(animal["steps"]) >= 3 and all(useful(x) for x in animal["steps"]),
                     "Drawing lessons need visible written steps matching numbered stages.")
                need(animal.get("illustrated_step_count") == len(animal["steps"]), "Illustrated and written stage counts must agree.")
        if art.get("daily_fresh") and page.get("image", {}).get("origin") == "generated":
            need(page["image"].get("generation_evidence", {}).get("prompt"), "Keep the exact artwork generation prompt.")
    game_names = []
    for section in sections.values():
        if section["kind"] == "games":
            for game in section["games"]:
                game_names.append(game)
                need(game in profile.get("games", {}).get("enabled", []), "A page includes an unselected game.")
                puzzle = edition.get("puzzles", {}).get(game)
                need(isinstance(puzzle, dict), f"Missing playable puzzle: {game}")
                if game == "crossword":
                    games[game] = validate_crossword(puzzle, profile["games"].get("personalized_ratio", .5))
                elif game == "jumble":
                    validate_jumble(puzzle)
                    games[game] = {"checked": True}
                elif game == "sudoku":
                    games[game] = validate_sudoku(puzzle)
                elif game == "chess":
                    games[game] = validate_chess(puzzle)
    need(set(games) == set(profile.get("games", {}).get("enabled", [])), "Every selected game needs a playable page.")
    need(len(game_names) == len(set(game_names)), "Each selected puzzle appears once.")
    # Restrict obvious private strings before typesetting; editorial privacy review remains necessary.
    patterns = {"credentials": r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})\b",
                "street addresses": r"\b\d{1,6}\s+(?:[\w.-]+\s+){0,5}(?:Street|Avenue|Road|Boulevard|Drive|Lane)\b",
                "tracking numbers": r"\b(?:1Z[A-Z0-9]{16}|\d{20,22})\b"}
    for page in pages.values():
        printed = [page.get("deck", "")]
        printed += page.get("comic", {}).get("captions", [])
        for lesson in page.get("drawing_lesson", {}).get("subjects", []):
            printed += [lesson["breed"], lesson["pose"], *lesson["steps"]]
        for a in page["articles"]:
            printed.extend([a["headline"], *a["paragraphs"], *a.get("steps", []), a.get("discussion_question", ""), a.get("decision_needed", "")])
            for identity in a.get("task_ids", []):
                printed.extend([index[identity]["title"], index[identity].get("notes", "")])
            for identity in a["source_ids"]:
                printed.extend([index[identity]["title"], index[identity]["source_label"]])
            for row in a.get("table", {}).get("rows", []):
                printed.extend(str(value) for value in row)
            if "private money" in profile.get("privacy", {}).get("exclude", []):
                money = re.compile(r"(?:\$\s?\d|\b\d[\d,.]*\s?(?:USD|dollars)\b)", re.I)
                if any(money.search(value) for value in [a["headline"], *a["paragraphs"]]):
                    need(a.get("public_financial_figures") is True and all(index[i].get("public") is True for i in a["source_ids"]),
                         "Private money must stay out of print; public figures need explicit public-source evidence.")
        for category in profile.get("privacy", {}).get("exclude", []):
            if category in patterns:
                need(not any(re.search(patterns[category], value, re.I) for value in printed), f"Printed content violates privacy setting: {category}")
    return {"feature_gaps": gaps, "games": games}


def novelty_record(edition, qa, index):
    return {"date": edition["date"], "mode": edition["mode"],
            "urls": sorted({index[i]["source_url"] for p in edition["pages"] for a in p["articles"] for i in a["source_ids"] if index[i].get("source_url")}),
            "issue_ids": sorted({item["issue_id"] for item in index.values() if item.get("issue_id")}),
            "premises": [p["comic"]["premise"] for p in edition["pages"] if p.get("comic")],
            "lessons": [s for p in edition["pages"] for s in p.get("drawing_lesson", {}).get("subjects", [])],
            "artwork_sha256": [qa["images"][p["id"]]["sha256"] for p in edition["pages"]
                               if p.get("image", {}).get("origin") == "generated"]}


def check_novelty(record, history, edition):
    prior = [r for r in history.get("editions", []) if r.get("date") != record["date"] and r.get("mode") == record["mode"]]
    if edition.get("mode") == "demo":
        return
    for old in prior:
        need(not set(record["artwork_sha256"]) & set(old.get("artwork_sha256", [])), "Daily artwork must be new; reuse likeness references instead.")
        need(not set(record["premises"]) & set(old.get("premises", [])), "A comic premise repeats an earlier edition.")
    repeated_urls = set(record["urls"]) & {u for r in prior for u in r.get("urls", [])}
    repeated_issues = set(record["issue_ids"]) & {u for r in prior for u in r.get("issue_ids", [])}
    updates = edition.get("revisit_reasons", {})
    need(all(useful(updates.get(u)) for u in repeated_urls | repeated_issues), "Revisited stories/issues need the actual new development or an explicit evergreen reason.")
    for lesson in record["lessons"]:
        repeated = any(s.get("breed") == lesson["breed"] and s.get("species") == lesson["species"] for r in prior for s in r.get("lessons", []))
        if repeated:
            need(useful(lesson.get("revisit_reason")), "A repeated lesson breed needs a rotation reason.")
            need(not any(s.get("breed") == lesson["breed"] and s.get("pose") == lesson["pose"] for r in prior for s in r.get("lessons", [])),
                 "Use a different pose when revisiting a drawing breed.")
