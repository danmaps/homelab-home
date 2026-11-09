# Personalization interview

Use `python scripts/newspaper.py setup-questions` for the five question groups. Ask a few related questions at a time, prefill supported existing context, and allow a solo user, adults-only household, or any number of children. Questions configure capabilities; do not ask the current skill-maintenance user to supply a new household now.

1. **Basics:** newspaper name, audience/reading level, city, IANA time zone, paper size, full or selected sections.
2. **People and family:** preferred names/aliases, adult/child roles, interests, two-page desks, exact task-list ownership, school providers/current terms, shared menus/activities, personal-desk owner and discussion partner. Avoid collecting unnecessary dates of birth, student IDs or addresses.
3. **Sources:** selected accounts/folders/calendars/lists, scope and lookback, newsletters and public feeds, dedicated publications, official videos, organization/industry desk names, required all-topic notices. Discover candidates and let the user select them. Record confirmed organizations and units; do not copy another household's school or club.
4. **Art and games:** full/optional/text art, who gets comics, approved character references, style, clothing palette, humor level, optional pet references/markings, drawing subjects, breed/pose rotation, game selection and one/two game pages. New daily art is separate from reusable likeness references. An absent reference is not permission to infer a real appearance.
5. **Privacy and operations:** exclusions, neutral medical labels, local PDF or email, exact authorized recipients/mail account, requested schedule/deadline and existing job, desired printer/paper/color/duplex. Printing needs a test and the user's physical confirmation. Queue acceptance never substitutes for that answer.

Ask the user to confirm the concrete plan. Save the answers in their private workspace, following `assets/setup.example.json`. That example is deliberately blocked by `configure` until its `example_only` marker is removed following real personalization. Its `confirmed` flag is fixture data and cannot establish user consent. `configure` builds the full page plan, profile, source registry, empty history and pilot log. Do not overwrite an existing profile to make a routine preference change.

`members[].id` is a stable lowercase identifier; the displayed name is freely configurable. A child may disable academics or task coverage if those sources are not desired. Enabling `todo_required` requires exact `todo_lists`. `artwork.comic_people` selects people whose first personal/child page must contain a strip; `lesson_person_id` selects a child's second page. The full art default is `one_per_page`; `optional` permits selected illustrated pages, and `none` requires comics/illustrated lessons to be deselected. `reading` entries can identify Techmeme/Memeorandum or any selected equivalent. Two entries sharing `pair_group` form the consecutive organization/industry pair.

A source has a stable ID, scope, discovery path, maximum observation age, required/print requirements, coverage mode and target page IDs. An `all_topics` source covers every new message topic plus older topics that remain applicable. `page_ids` identify where complete topic coverage belongs. A local cache never establishes remote synchronization or complete accounts.

Map actual capabilities before promising full source coverage:

| Source/capability | Receiving agent setup |
| --- | --- |
| Mail/calendar/tasks | Authorized connector or supported native UI; exact accounts/lists, pagination, recurrence and unread-preservation checks |
| School grades | New user's provider and normal authenticated read path; dated term boundaries and normalized records; no bundled credentials |
| Shared school/lunch/activities | Verified sender/publisher discovery paths; inspect attachments and image-only schedules separately |
| News/newsletters/videos | Selected feeds/issues and original-text reads; retain title/description-only limitations |
| Public adapters | Optional `adapter: public`, `url`, and `format: jsonfeed`, `rss`, `atom` or `nws`; NWS URL is a configured public points endpoint |
| Artwork | Host image-generation tool; approved private character/pet references and saved prompts |
| PDF | Python, WeasyPrint platform libraries, bundled licensed fonts and Poppler previews |
| Email | Attachment-capable authorized account, sent-message readback and attachment-byte verification |
| Printing | CUPS helper or equivalent platform adapter with the same physical-test/duplicate/deadline gates |
| Scheduling | Host scheduler tool; preserve existing job identity and unrelated fields |

Private adapters normalize records into the supplied contracts. They do not need access to the originating installation's Mac caches. Aeries can be used when it is the new user's school provider: authenticate normally through supported tools, read the selected students/gradebooks and term dates, and stop on authentication/structure failures. Do not bypass MFA/CAPTCHA or request passwords in chat.

Store `.local/`, `work/`, `outputs/`, and `deliverables/` outside the shareable skill. A source registry keeps discovery paths, observed dates, page assignments and access limits across runs. Retain raw portraits and school data privately. Share only the generic skill and fictional fixtures. Host memory updates use that user's memory controls and explicit preferences; no originating memory path is inherited.
