# Codex runtime

Use the installed skill directory as the working directory for the documented
commands. Keep the newspaper's private workspace and generated output outside
that directory. The supplied `agents/openai.yaml` provides the skill's display
name and `$personal-newspaper` invocation prompt.

## Python and PDF output

When Codex exposes `load_workspace_dependencies`, use it to locate the bundled
Python interpreter. Otherwise discover an available Python 3.12+ interpreter.
Create an isolated environment in a writable workspace or temporary directory
and install `scripts/requirements.txt`; retain the selected interpreter for
every newspaper command. Locate Poppler's `pdftoppm` and WeasyPrint's native
libraries in the actual execution environment. On macOS, if installed
Pango/GLib libraries are not found, discover their library directory and set
`DYLD_FALLBACK_LIBRARY_PATH` for the rendering process. Keep machine-specific
interpreter and library paths out of the shareable profile.

Run `preflight --workspace <private-workspace>` and the fictional sample before
promising production. Follow any available host PDF-skill instructions for
artifact creation and page inspection. Return the checked PDF through Codex's
file handoff; use `record-local` only after that handoff is available.

## Map optional capabilities

- Read private sources through the session's authorized connectors or supported
  browser/computer tools. Public feeds use the bundled adapters. Record missing
  access as partial or unavailable coverage.
- Use the host image-generation tool when it is available. Follow the selected
  art/omission policy if it is unavailable; do not substitute invented asset
  paths or claim an image was generated.
- Use an attachment-capable mail connector only under the user's configured
  delivery authorization. It must support sent-message and attachment-byte
  verification. Otherwise offer a checked local PDF.
- Under a scheduling request, use the available Codex automation tool after
  the checked interactive sample. Reuse the existing job and its time zone.
  A CLI or cloud session without a scheduler cannot establish a scheduled run.
- Print only when the execution environment can reach the confirmed printer
  through CUPS or an equivalent adapter. Preserve the physical-test, delivery,
  freshness, deadline, and duplicate-attempt checks. A cloud session does not
  inherit access to a local printer.

Determine these capabilities during setup; a skill installation does not
install connectors, grant account access, or authorize external actions.
