# Personal Newspaper in homelab-home

Source: Personal Newspaper v1.0.0 by Ted Tschopp, https://ai.tedt.org/skills/personal-newspaper/
Bundle: https://ai.tedt.org/bundles/personal-newspaper.zip

Copied here 2026-11-08 as the text files of the skill bundle only:
SKILL.md, agents/, scripts/, references/, and the text assets
(JSON fixtures, CSS/HTML, font license files).

## Binary assets omitted from this commit

The bundle's binary assets are not in this commit, because the
GitHub push used here is text-only:
- `assets/fonts/*.otf` and `*.ttf` (3.5 MB, bundled licensed fonts)
- `assets/demo-art/*.png` (5.9 MB, demo comic/lesson/back art)

They are only needed for PDF rendering and the demo artwork.
The digital-only daily email does not use them.

To restore the full bundle locally or on conductor:

```sh
./.agents/skills/personal-newspaper/scripts/fetch-assets.sh
```

That downloads the upstream bundle zip, extracts only the font and
demo-art files into this skill folder, and verifies the file list.
It does not overwrite any text files.

## Private config is NOT in this repo

No household profile, answers, names, email addresses, or delivery
authorization are committed here. Those live in the private
life-coach workspace. Configure a workspace with
`python3 scripts/newspaper.py configure --answers <answers.json> --workspace <path>`
following references/setup.md.
