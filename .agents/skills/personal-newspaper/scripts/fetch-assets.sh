#!/bin/sh
# Restore the binary assets omitted from the text-only GitHub copy:
# bundled fonts (assets/fonts/*.otf, *.ttf) and demo art (assets/demo-art/*.png).
# Downloads the upstream Personal Newspaper bundle and extracts only those files.
# Usage: run from anywhere; it resolves the skill folder from this script's path.
set -eu
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
echo "Downloading Personal Newspaper bundle..."
curl -fsSL -o "$TMP/personal-newspaper.zip" https://ai.tedt.org/bundles/personal-newspaper.zip
echo "Extracting fonts and demo art into $SKILL_DIR ..."
unzip -o -q "$TMP/personal-newspaper.zip" \
  'assets/fonts/*.otf' \
  'assets/fonts/*.ttf' \
  'assets/demo-art/*.png' \
  -d "$TMP/bundle"
cp "$TMP/bundle/assets/fonts/"*.otf "$TMP/bundle/assets/fonts/"*.ttf "$SKILL_DIR/assets/fonts/" 2>/dev/null || true
cp "$TMP/bundle/assets/demo-art/"*.png "$SKILL_DIR/assets/demo-art/" 2>/dev/null || true
echo "Fonts in $SKILL_DIR/assets/fonts:"
ls "$SKILL_DIR/assets/fonts" | grep -E '\.(otf|ttf)$' || echo "(none)"
echo "Demo art in $SKILL_DIR/assets/demo-art:"
ls "$SKILL_DIR/assets/demo-art" | grep -E '\.png$' || echo "(none)"
