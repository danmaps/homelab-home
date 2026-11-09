# Delivery, state and operations

Run from this skill directory with the target environment's Python. Quote paths containing spaces. The workspace is a private directory separate from the skill; examples below use `/private-work` as a placeholder to replace.

```sh
python scripts/newspaper.py setup-questions
python scripts/newspaper.py configure --workspace /private-work --answers /private-work/answers.json
python scripts/newspaper.py preflight --workspace /private-work
python scripts/newspaper.py state --workspace /private-work
python scripts/newspaper.py collect --workspace /private-work --date 2026-10-24
python scripts/newspaper.py source-import --workspace /private-work --snapshot /private-work/work/2026-10-24/snapshot.json --input /private-work/source-envelope.json
python scripts/newspaper.py public-refresh --workspace /private-work --snapshot /private-work/work/2026-10-24/snapshot.json
python scripts/newspaper.py record-discovery --workspace /private-work --input /private-work/discovery.json
python scripts/newspaper.py puzzles --date 2026-10-24 --output /private-work/work/puzzles.json
python scripts/newspaper.py validate --workspace /private-work --profile /private-work/.local/profile.json --snapshot /private-work/work/2026-10-24/snapshot.json --edition /private-work/work/edition.json
python scripts/newspaper.py render --workspace /private-work --profile /private-work/.local/profile.json --snapshot /private-work/work/2026-10-24/snapshot.json --edition /private-work/work/edition.json --output /private-work/outputs/2026-10-24-r001
python scripts/newspaper.py review /private-work/outputs/2026-10-24-r001 --workspace /private-work --note 'Actual observations from every page preview.'
```

`collect` creates empty/unavailable envelopes and preserves an existing snapshot; it does not silently claim account coverage. Configure/import actual source access. `record-discovery` accepts a selected source ID, discovery path, page IDs, scope, actual observation time and evidence; keep newest issue identity and limits. Public refresh reads only explicitly configured public URLs; it never searches private messages on the public web.

`state` identifies checked-pending versus delivered artifacts for the selected date. Resume the checked PDF at its reported stage. Revisions require a new output directory. Keep the original checked PDF and checksum if email fails. The private history records sources, issue IDs, comic premises, lessons, artwork hashes and actual handoff, and supports novelty checks. Run one production operation at a time; an interrupted operation lock must be inspected/resolved before retrying.

## Local and email delivery

For a user who selected local PDF, return the checked file and run `record-local <folder> --workspace ...`. This records local readiness. For a user who selected email, a local link remains supplemental.

Before an email send, check existing Sent/Outbox and production state for edition/date/ID to prevent duplicate mail. Use only that user's authorized exact recipients and sending tool; the profile must retain the new authorization. Attach the actual reviewed PDF. State gaps, omitted artwork and lateness. Respect attachment limits using a reviewed email-sized revision; do not upload private content publicly as a workaround.

After sending, retrieve the real sent message and PDF attachment. Save downloaded attachment bytes in the private workspace. A verified receipt has:

```json
{
  "status": "sent",
  "edition_id": "actual receipt edition_id",
  "provider": "actual service",
  "to": ["authorized-new-user@example.org"],
  "message_id": "actual stable sent-message ID",
  "sent_at": "actual offset-bearing timestamp",
  "attachment": {"readback_path": "/private-work/sent-attachment.pdf", "sha256": "checked PDF SHA-256"},
  "verification": {
    "method": "sent_message_readback", "tool": "actual tool", "reference": "actual readback result",
    "message_id": "same actual sent-message ID", "to": ["authorized-new-user@example.org"],
    "attachment_sha256": "checked PDF SHA-256", "verified_at": "actual offset-bearing timestamp"
  }
}
```

Run `record-email <folder> --workspace ... --input <receipt.json>`. It validates recipients, PDF bytes, message ID and readback evidence. It does not send email. Receipt structure cannot prove a fabricated connector result. A draft/outbox/send acceptance is pending. After an ambiguous send, inspect Sent/Outbox once and stop automatic resend; resolve that same attempt later. Sent verification establishes sending, not inbox receipt or reading.

## Printing

The bundled printing path uses CUPS `lp`/`lpstat`. Other hosts use their supported printer adapter with the same gates. Never silently switch to a different queue.

```sh
python scripts/newspaper.py printer-test --workspace /private-work
python scripts/newspaper.py printer-test --workspace /private-work --submit
python scripts/newspaper.py printer-confirm --workspace /private-work --job-id ACTUAL-JOB-ID --user-confirmation 'The user actually confirmed the scale, legibility and duplex orientation.'
python scripts/newspaper.py printing --workspace /private-work on
python scripts/newspaper.py printing --workspace /private-work off
python scripts/newspaper.py print /private-work/outputs/2026-10-24-r001 --workspace /private-work --scheduled
```

Generating a test does not submit it. Submit only under the user's printing request; record physical confirmation only from the user's actual observation. A passed test is bound to the pinned queue; a queue change needs another test. The helper prints one copy at actual size with selected paper/color/duplex. It checks QA/PDF integrity, preferred delivery, current complete source coverage and the scheduled local deadline. Incomplete coverage or a late run skips printing without changing the preference. Demo editions are not automatically printed.

The per-date ledger is saved before submission. An ambiguous response remains `unverified`; repeated automatic submission is blocked across revisions. `--reprint` requires the user's explicit request for another copy. Queue acceptance, queue completion and physically observed output remain separate claims. A manual newspaper revision does not automatically print.

## Schedule and pilot

Use the host's supported scheduler after the reviewed sample under the user's scheduling request. Reuse an existing newspaper job and retain its identity/fields. The setup profile distinguishes `requested` from `enabled`; after successful scheduler creation/update, record the actual job ID, time zone and enabled state. Do not edit scheduler databases or unrelated briefings. Preserve the user's meaningful-change notification preference.

The pilot command records a JSON run with `date`, `started_at`, `finished_at`, `delivery_status`, boolean `coverage_complete`, `print_status`, and actual `delivered_at` for a delivered run. It computes the local deadline outcome from that verified delivery time. After three runs, report elapsed times, deadline outcomes and acceptance gaps. A delivered partial or late run is distinct from full acceptance. The helper calculates `max(0, elapsed_minutes - 45)`; adjust the existing start through the scheduler tool only under the user's requested scheduling scope, while retaining the delivery deadline. An interactive run is not an unattended pilot run.
