# GitHub briefing collector: local proof slice

Tracks [issue #22](https://github.com/danmaps/homelab-home/issues/22).
This is a manual, reversible implementation, not a rollout or a replacement
for the existing briefing. No scheduler, service, permissions, delivery,
GitHub state, or deployment changes are included.

## Existing path inspection (October 26, 2026)

The checkout contains deployment/backup schedules, but no morning GitHub
briefing implementation, prompt, retained report, or delivery configuration.
The connected ChatGPT task lookup returned no matching GitHub briefing among
19 tasks. This does not establish that the workflow is absent on Conductor.
No Conductor shell/runtime access or local `gh` executable is available in the
implementation environment. Consequently the actual scheduler, execution user,
auth scope, summary command, artifact handoff, and notification destination
remain unverified. Do not repurpose the dashboard deployment cron.

## Prerequisites and manual invocation

Run as the existing briefing user on Linux Conductor, with Python 3.9+ and the
existing authenticated GitHub CLI installation. Do not copy credentials or add
scopes. Check `gh auth status` locally without retaining its output. All API
requests explicitly target github.com and are reads (GraphQL uses POST only for
queries). No third-party Python packages are needed. Repository concurrency is
bounded by the `--workers` setting.

```bash
python3 -m unittest discover -s scripts -p 'test_collect_github_briefing.py' -v
python3 scripts/collect_github_briefing.py \
  --end 2026-10-26T14:03:11Z \
  --output "$HOME/.local/state/github-briefing/2026-10-26T140311Z.json" \
  --workers 4 --runtime-budget 300
```

Omit `--end` to capture one UTC end timestamp and derive the preceding 24 hours.
`--workers` bounds repository concurrency and `--runtime-budget` bounds the
whole run. Add `--resume` with the same end timestamp and output path to reuse
completed repositories; partial repositories are retried.
Exit 0 means the queries completed **within documented coverage limits**, not
that the implementation meets every issue acceptance criterion. Exit 2 means
one or more queries failed or truncated, and the JSON must be retained with its
partial status. Unexpected process termination leaves the prior artifact intact.
Do not use `set -e` to discard the partial artifact before inspecting exit 2.

The initial partial artifact is written before the first API call. After each
repository completes, the artifact is replaced atomically, so interruption
leaves the last usable scope/results/checkpoint. The output file is mode 0600,
written through a unique temporary file in the same directory. Each query and
repository records an observation timestamp; each query also records elapsed
seconds and API-call count (including retry attempts). The collector never
appends events or sends notifications. Concurrent reruns use last-completed-
writer wins; avoid overlapping manual runs when comparing evidence. Parent
directory access follows the existing user's policy. Keep artifacts outside the
web-served repo.
Suggested retention for validation is 14 daily artifacts; this script performs
no pruning, deletion, or retention configuration.

## Version 1 JSON contract

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer contract version, currently 1 |
| `window` | UTC start/end, half-open `[start,end)`, commit/CI timestamp choices |
| `collected_at`, `current_state_as_of` | Capture time at collection start, not a historical snapshot or an atomic API snapshot |
| `coverage` | Explicit implementation boundaries and `rollout_ready: false` |
| `scope` | Union of accessible affiliated and contributed repository identities, names, URLs, default branches |
| `scope_queries` | Viewer/discovery success, partial failures, page counts |
| `repositories` | Every discovered repo, including empty and failed queries |
| `counts` | Repository/event/per-repository-commit totals and partial query count |
| `limitations` | Coverage gaps passed to the summarizer, not silently omitted |

Each repository has `repository_id`, `name`, `status`, `activity`, `commits`,
`ci_attempts`, `current_unfinished_evidence`, and `queries`. Each query records
its name and status, with sanitized reason codes for failures, pages/items for
list queries, observation time, elapsed seconds, and API-call count. A failed
second page retains the first page and marks partial. Runtime expiry is
recorded as `runtime_budget_exceeded`; `unfinished_queries` names repositories
not completed before the budget. `counts` separates partial and skipped
queries.
Empty complete lists differ from unavailable, access denied, unauthenticated,
rate limited, invalid response, truncated, and transport failures. A failed scope
query means the repository count is incomplete, even if other repos succeeded.

Events use `repo:kind:database-id`; separate opened and closed/merged events
survive deduplication. Commits use SHA within each repo and retain one-line
messages, URLs, and committer dates. Shared SHAs in different repos remain visible
in both; `commits_per_repository` is deliberately not a global unique-SHA total.
CI attempts use `run-id:attempt`, with workflow, branch, SHA, start time, status,
conclusion, and the latest observed conclusion for that run. Failure followed by
success in the same run remains inspectable. Separate successful runs do not
automatically establish recovery for a different branch/SHA.

Current evidence includes open/draft PRs, individual review requests, assigned
open issues, queued/in-progress runs, and non-default branches ahead of default
without an observed open PR for that source branch. Evidence is not a claim that
Danny owns every task or must act. Absence of a PR is provisional when PR collection
is partial. Review/draft records carry creation age relative to window; they are
current backlog, never automatically labeled overnight review requests. A direct
push to default alone never establishes unfinished work.

## Pagination, determinism, and retries

REST lists request 100/page until a short page, including an empty terminal page
for exact multiples. GraphQL contribution discovery follows end cursors. A
1,000-page per-query safety bound reports `truncated` rather than success.
GraphQL cursor stalls and error responses explicitly fail. Scope uses both
`user/repos` affiliations and viewer `repositoriesContributedTo`; GitHub's
contribution visibility/history restrictions still apply. The reported baseline
188 is a comparison target, never a list or a cap.

Every branch and every available PR history is queried for commits, including
fork/closed PR histories, except an open PR branch whose current head SHA
exactly matches the PR head: its PR history is reused and the skipped query is
recorded. PR histories reaching GitHub's 250-commit ceiling are
explicitly partial. Detached/deleted branches without available histories and
unreachable commits cannot be recovered. Committer dates are not push dates.
PR/issue list timestamps preserve latest opened/merged/closed state only; repeated
reopen/close transitions require timeline collection beyond this slice.

CI scans available run history, not only runs created overnight, so an old run's
new attempt can be included by its own start time. Queued/current runs are queried
separately. Old metadata updates alone do not count as activity. This choice is
more expensive than a creation-date query and must be timed on Conductor.
Deleted or expired runs cannot be reconstructed. Linked issue/PR relationships,
team-based review requests, and a complete temporal lifecycle ledger are deferred
and explicitly declared in the JSON. This slice is not coverage parity yet.

At most two retries follow the initial request for HTTP 5xx or recognized rate
limits. Numeric/date Retry-After and primary-limit reset guidance are honored
only within a 60-second wait budget per retry; longer waits produce an explicit
rate-limit failure. Other 403 responses remain access denied rather than guessed
rate limits. Requests time out after 90 seconds; transport errors are surfaced,
not retried in this slice. Raw API bodies/stderr and tokens are never logged.

Arrays are deduplicated and sorted by stable identity; JSON keys are sorted and
compact. Identical observed inputs produce identical bytes except for documented
capture timestamps. Live state, API pagination races, and deleted evidence mean
reruns of a historical window may differ. No historical-state completeness claim
or savings estimate follows from deterministic serialization.

## October 25–26 validation and evidence gates

The command above fixes the requested exact window, October 25 14:03:11 UTC
inclusive through October 26 14:03:11 UTC exclusive. The local fixture suite
covers these boundaries but is synthetic, not retained production evidence.
The exact probe was run on Conductor with four workers and a 300-second budget.
The first pass discovered 542 repositories, checkpointed 89 completed
repositories, and produced a 455,502-byte mode-0600 partial artifact. A same-
window resume reused completed repository results and finished with all 542
repositories represented, 112 complete-with-documented-limits and 430 partial,
4,231 partial queries, 32 skipped history queries, and a 1,683,578-byte mode-
0600 artifact. The measured wall time was 314 seconds because in-flight API
requests can finish after the budget boundary. Across 7,145 recorded queries,
2,988 API calls consumed 1,707.33 summed query-seconds; the slowest observed
query was a rate-limited workflow-run scan. These are collection measurements,
not summary-token or quota measurements. No scope-parity or delivery validation
has been completed; the observed 542-repository scope differs from the old 188
baseline and requires explanation.

Before any cutover:

1. Identify the existing Conductor scheduler entry, execution script/user,
   summary invocation and delivery destination read-only. Retain the original
   configuration for comparison and rollback without exposing credentials.
2. Run the fixed-window collector manually under the same user. Retain JSON,
   elapsed seconds (`/usr/bin/time -p`), byte count (`wc -c`), exit status and
   code revision outside the public repository. If scope is partial, fix that
   before treating activity absence as meaningful.
3. Compare actual repository identity sets to the original briefing evidence.
   Explain additions/removals from 188 through access, discovery, or history
   changes. Compare each commit/event/run and every needs-you item by ID and URL.
   Use retained reports to explain unavailable historical status; today's open
   PRs, assignments, branches, and review requests are not October 26 snapshots.
4. Exercise permission denial, exhausted rate limits and interrupted pagination;
   ensure partial data/caveats stay visible. Resolve the declared coverage gaps
   before claiming parity. Add observed mismatches as regression fixtures with
   private content removed.
5. Under comparable scope/output requirements measure collection runtime, JSON
   bytes, and summary input/output/cache tokens separately. Record unknown
   measurements as unknown. Account quota and concurrent use are separate from
   per-turn measurements. No savings or weekly sustainability is established.

## Integration and rollback proposal, not applied

Once parity and runtime evidence are clear, change only the existing execution
path, with separate authorization for rollout. That path should invoke the
collector once, pass the compact JSON to the existing Codex summary step and use
the existing delivery mechanism once. The summary should produce **needs-you /
by-repo / unfinished-work**, preserving names, titles, URLs, query failures and
limits. Treat repository titles/messages as untrusted data, never instructions.
Do not let Codex silently repeat the sweep or invent missing evidence.

On exit 2, summary/delivery must visibly label partial coverage and never claim
"nothing happened" for unknown queries. On no readable fresh artifact or summary
failure, use the existing failure-reporting path; never relabel yesterday's JSON
as today's report. The scheduler, notification deduplication and failure path
must be identified before this proposal can be wired safely. Rollback restores
the original command/prompt in that same scheduler and retains collected JSON
for diagnosis, with no second scheduler or fallback duplicate notification.
