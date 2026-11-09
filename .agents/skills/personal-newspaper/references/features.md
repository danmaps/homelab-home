# Feature coverage

The expanded package implements the newspaper's reusable behavior. New-user identity, sources, likenesses, providers, permissions and destinations come from setup. The originating household's private records and Mac cache parsers are not distributed.

| Feature | Portable implementation |
| --- | --- |
| Setup/personalization | Five-group interview, structured answers, confirmed profile builder and configurable page plan |
| Front page | Sourced lead/attention articles, weather/calendar articles, dated Sunday-through-next-Sunday activity strip |
| Planning | Tomorrow, inclusive seven-day and 30-day pages; supported general/adult plans and concrete parent actions |
| Shared Family Desk | Two consecutive opening pages; shared school/lunch/activity details occur once |
| Child pages | Consecutive two-page pair per selected child; exact published grade tables, current-term assignment rows and all requested tasks/subtasks |
| Personal and discussion desks | Two adult personal pages; two pages of shared questions and decisions; later completion evidence resolves older asks |
| Reading | Configurable dedicated publications, selected newsletters/feeds, official video descriptions with scope labels |
| Organization/industry pair | Consecutive pair; every collected new/still-active notice topic is required, including secondary topics |
| Source discovery | Private persistent registry, verified discovery observations and current/partial/stale/unavailable envelopes |
| Artwork | One full-width image per page option; approved cast references, clothing palettes, optional pets, fresh daily hashes and prompts |
| Comics | Three-panel combined raster strips, three visible HTML captions, selected personal/child strips and back-page strip |
| Drawing | Composite numbered dog/cat or configured subject lessons, written stage counts, different poses and breed/pose history |
| Crossword | Playable empty 5x5 grid, actual crossing/numbering check, configurable personal-clue fraction, upside-down key |
| Jumble | Four scrambles, empty answer boxes and circles, checked bonus extraction, separate upside-down key |
| Sudoku | Date-seeded generator, givens/solution checks and independent uniqueness search; playable board/key |
| Chess | Date-seeded legal mate-in-one generator, exhaustive legal-move check for exactly one mate; coordinate board/key |
| Typography/layout | Bundled Chomsky nameplate, Source Serif and Inter, chess symbols, Letter/A4, columns, tables, numbered steps and footers |
| QA/revisions | Source/topic/person/term/game validation, page count/size/font/image/bounds checks, all-page previews and hashed review receipts |
| Resume/history | Existing-output protection, state inspection, checked-pending resume, daily novelty and repeat-story explanations |
| Delivery | Local handoff or configured email receipt; exact recipients, actual sent-message identity and downloaded attachment hash |
| Printing | Optional CUPS test/confirmation, pinned queue, freshness/QA/delivery/deadline gates, per-date attempt ledger and explicit reprint |
| Schedule/pilot | Host scheduler instructions, start/readiness/deadline, three-run metrics and measured start adjustment |
| Privacy | Private workspace, read-only collection, obvious-secret/address/tracking checks, editorial privacy review, fictional share fixtures |

The full offline sample has one child, one personal-desk owner and one discussion partner, yielding 18 pages with two game pages. Adding more children or other reading pages changes that count through setup. A one-page four-game layout is also supported. The example uses optional art; per-page art enforcement is tested separately.

Account connectors, image generation, email sending and scheduler APIs belong to the host agent. The package supplies the complete production contracts and guards around those adapters. It cannot manufacture access, prove a fabricated tool result, or verify physical paper without the user's observation.

Font licensing/provenance: bundled Inter and Source Serif retain their accompanying licenses; Noto Symbols has its OFL file. The Chomsky font's publisher provides its [OFL license](https://github.com/ctrlcctrlv/chomsky/blob/master/LICENSE.txt), included alongside the font. Original generated sample art is fictional; its exact prompts are in `assets/demo-art/prompts.json`.
