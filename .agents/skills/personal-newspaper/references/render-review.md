# Render and review

Use Python 3.12+, packages in `scripts/requirements.txt`, WeasyPrint's platform libraries and Poppler `pdftoppm`. Run `preflight` in the receiving environment and follow host artifact-start instructions before PDF authoring. Install only needed dependencies using that host's documented method. This package makes no image/model API calls from scripts.

The full fictional layout check is:

```sh
python scripts/newspaper.py validate --profile assets/full.profile.json --snapshot assets/full.snapshot.json --edition assets/full.edition.json
python scripts/newspaper.py render --profile assets/full.profile.json --snapshot assets/full.snapshot.json --edition assets/full.edition.json --output /private-work/full-demo-r001
```

Replace the output placeholder with an actual unused writable path. Full live production additionally requires `--workspace` for real history. The sample has 18 pages and optional art, including two combined comic strips, one numbered two-animal drawing lesson, exact family tables and all four playable games. Every sample page is visibly fictional. Never promote it into live evidence. `scripts/make_demo.py` rebuilds the fictional JSON fixtures only; it is not a daily collector or production runner.

Inspect every rendered page PNG at readable resolution. Check masthead, page order/pairs, local windows, body readability, whitespace, source attribution, footers, tables, individual identity, clipped content, missing glyphs and image aspect ratios. Verify actual likeness/style/color requirements, age suitability, comic captions, drawing poses/stage numbers, playable grids/boxes, correct chess orientation and upside-down answer keys. Read all factual copy against sources and confirm mandatory folder/message/topic completeness separately from the normalized IDs.

Short sample pages intentionally leave white space; a live person desk should contain substantial useful current material without invented filler. Fit real content by editing lower-priority copy, reducing duplicate information and recutting optional material. Preserve all mandatory topics and tasks. Do not globally shrink body type or clip overflow.

After all pages pass, run `review <folder> --workspace ... --note '<actual specific observations>'`. The helper checks PDF/input/preview hashes before recording visual approval; it cannot prove somebody looked. Full coverage, local readiness, sent email and print outcomes remain separate states.

Repair and rerender into a new revision directory, up to two repair attempts. Do not approve a defective PDF. The copied inputs/artwork make each result inspectable; delivered bytes stay immutable. Follow [operations](operations.md) for local handoff, verified email, state/history and printing.
