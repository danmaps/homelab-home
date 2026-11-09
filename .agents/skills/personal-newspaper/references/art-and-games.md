# Artwork, cast, lessons and games

## Artwork and cast

The agent uses its supported image-generation tool; scripts never call a model API. Follow host image/PDF instructions. New daily images use `origin: generated`, `generated_for_date`, meaningful `alt`, a local relative `path` under the edition input directory, and `generation_evidence` containing actual tool/reference and exact prompt. PNG/JPEG/WebP are supported. Source/licensed images retain provenance URLs. Raw family/pet photos stay private. Never turn grades, medical details, work records or private difficulties into an image prompt.

`artwork.mode: one_per_page` requires exactly one image per physical page; `optional` permits selected illustrations; `none` disables illustrated modules. Images span printable width with original aspect ratio. A three-panel strip is one raster, replacing the page illustration. `comic` contains a fresh `premise`, configured `cast_ids`, their approved `reference_ids`, and exactly three visible `captions`. Keep readable captions outside the raster. Simple silent visual humor with a clear setup/payoff works for school-age readers on child, adult and back-page strips. Clothing palettes and grayscale/accent rules come from setup, not from the example household.

The profile can retain approved style/likeness references and precise appearance details. Inspect actual references and latest direct user corrections. Reuse likeness references, not prior daily artwork. Optional pets use actual approved markings without guessing breed/age/sex and without a daily appearance quota. A fictional scene does not establish a real event. Save all generation attempts, exact prompts and selected file hashes privately.

A same-date revision may reuse that date's art. Across dates, history rejects repeated art hashes and exact comic premises. The agent must also check semantic repetition, which a hash cannot detect. Retry an asset once; when still unavailable, disclose it and recut to a user-approved layout, updating art mode only under that user's preference. Do not substitute code-drawn art for a requested generated illustration.

## Drawing lessons

`lesson_person_id` selects a child's second page; the first retains that child's requested comic. The second uses one composite tutorial image and `drawing_lesson.subjects`. Each subject has `species`, `breed`, `pose`, `illustrated_step_count`, and visible `steps`. The count must match the written steps. The selected species set (default dog/cat) must be complete, with different poses for the two subjects. Inspect the actual artwork for correct stage numbering, pose consistency and agreement with text; metadata cannot prove that.

Rotate breeds and viewpoints against dated history. A revisited breed needs `revisit_reason` and a different pose. Distinguish educational breed examples from likenesses of real household pets. The shipped fictional example has a seated beagle and a stretching domestic shorthair, each in four stages. Its generation prompts, including a color correction to the adult comic, are in `assets/demo-art/prompts.json`.

## Playable games

Top-level `puzzles` holds selected `crossword`, `jumble`, `sudoku` and `chess` objects. Profile `games.enabled` chooses games; `games.pages: 1|2` controls compact or roomy placement. Every selected game appears exactly once. Solving grids/boxes stay empty except Sudoku givens and crossword blocks/numbers. Answer keys are separate and upside down.

- **Crossword:** `grid` is five five-character strings of A-Z/#. Every white run is at least three letters and checked in both directions. Each clue has actual `direction`, numbered start, `answer`, visible `clue`, `personalized` flag and a low-sensitivity `personal_context` when personalized. Grid crossings, numbering, clue coverage and the configured personalized ratio (default one half) are validated. The agent must supply real words and fair, accurate clues; a mechanically valid square alone is insufficient.
- **Jumble:** `intro`, four `words` each with uppercase `answer`, changed `scrambled` anagram and zero-based `circles` positions in the SOLVED answer; `bonus` and `bonus_clue`. Circled extracted solution letters must anagram exactly to the bonus. The renderer prints the scramble beside empty, correctly circled answer boxes.
- **Sudoku:** nine nine-digit `grid` strings (0 for blank), nine solution strings and `instructions`. Validation checks rows/columns/boxes/givens and searches for uniqueness. `puzzles --date ... --output ...` generates a date-varied puzzle and checks it before saving.
- **Chess:** legal `fen`, `solution_uci`, matching `solution_san`, `instructions`, `explanation`. Validation enumerates every legal move and requires exactly one immediate mate. The generator produces a checked problem; the board renders actual pieces with rank/file coordinates and the side to move. Check that the explanation fits the actual position.

The `puzzles` command generates Sudoku and chess, while the agent authors crossword/Jumble from low-sensitivity interests using the validated schema. Do not reuse the shipped example crossword/Jumble as a daily generator. All four actual validators ship in `scripts/games.py`; failures stop rendering.
