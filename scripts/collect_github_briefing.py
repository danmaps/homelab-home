#!/usr/bin/env python3
"""Read-only GitHub evidence collector. Python stdlib + existing gh authentication."""
import argparse
from datetime import datetime, timedelta, timezone
import email.utils
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import urlencode, quote

VERSION = 1


def timestamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return dt.astimezone(timezone.utc)


def utc(dt):
    return dt.isoformat(timespec='seconds').replace('+00:00', 'Z')


def unique(items, key):
    # Stable conflict resolution independent of arrival order.
    return sorted({key(x): x for x in sorted(items, key=lambda x: json.dumps(x, sort_keys=True))}.values(), key=key)


class Failure(Exception):
    def __init__(self, kind):
        self.kind = kind
        super().__init__(kind)


class Gh:
    def __init__(self, run=subprocess.run, sleep=time.sleep, retries=2, max_wait=60):
        self.run, self.sleep, self.retries, self.max_wait = run, sleep, retries, max_wait

    def request(self, endpoint, graphql=None):
        args = ['gh', 'api', '--hostname', 'github.com', '--include', endpoint]
        if graphql is not None:
            args += ['-f', 'query=' + graphql]
        for attempt in range(self.retries + 1):
            try:
                result = self.run(args, capture_output=True, text=True, timeout=90)
            except (OSError, subprocess.TimeoutExpired):
                raise Failure('transport_unavailable')
            # Never propagate stderr or raw responses to logs/artifacts.
            raw = result.stdout.replace('\r\n', '\n')
            head, sep, body = raw.partition('\n\n')
            match = re.search(r'^HTTP/\S+ (\d+)', head)
            status = int(match[1]) if match else 0
            headers = dict((k.lower(), v.strip()) for k, v in
                           (line.split(':', 1) for line in head.splitlines()[1:] if ':' in line))
            rate = status == 429 or (status == 403 and (headers.get('x-ratelimit-remaining') == '0' or 'retry-after' in headers))
            if result.returncode == 0 and 200 <= status < 300 and sep:
                try:
                    data = json.loads(body)
                except ValueError:
                    raise Failure('invalid_response')
                if isinstance(data, dict) and data.get('errors'):
                    raise Failure('graphql_errors')
                return data
            retryable = rate or status >= 500
            delay = 2 ** attempt
            if 'retry-after' in headers:
                try:
                    delay = float(headers['retry-after'])
                except ValueError:
                    try:
                        delay = email.utils.parsedate_to_datetime(headers['retry-after']).timestamp() - time.time()
                    except (ValueError, TypeError):
                        raise Failure('invalid_retry_guidance')
            elif rate and 'x-ratelimit-reset' in headers:
                try:
                    delay = float(headers['x-ratelimit-reset']) - time.time()
                except ValueError:
                    raise Failure('invalid_retry_guidance')
            if not retryable or attempt == self.retries or delay > self.max_wait:
                kind = 'rate_limited' if rate else {401: 'unauthenticated', 403: 'access_denied', 404: 'unavailable', 409: 'unavailable'}.get(status, 'api_failure')
                raise Failure(kind)
            self.sleep(max(0, delay))


class Collector:
    def __init__(self, api, end, observed=None, max_pages=1000):
        self.api, self.end = api, timestamp(end)
        self.start = self.end - timedelta(hours=24)
        self.observed = observed or utc(datetime.now(timezone.utc))
        self.max_pages = max_pages
        self.queries = []

    def inside(self, value):
        return bool(value) and self.start <= timestamp(value) < self.end

    def pages(self, label, endpoint, field=None, params=None):
        rows = []
        record = {'query': label, 'status': 'complete', 'pages': 0}
        self.queries.append(record)
        try:
            for page in range(1, self.max_pages + 1):
                data = self.api.request(endpoint + '?' + urlencode(dict(params or {}, per_page=100, page=page)))
                batch = data[field] if field else data
                if not isinstance(batch, list):
                    raise Failure('invalid_response')
                rows.extend(batch)
                record['pages'] = page
                if len(batch) < 100:
                    break
            else:
                raise Failure('truncated')
        except (Failure, KeyError, TypeError) as exc:
            record.update(status='partial', reason=exc.kind if isinstance(exc, Failure) else 'invalid_response')
        record['items'] = len(rows)
        return rows

    def one(self, label, endpoint):
        record = {'query': label, 'status': 'complete'}
        self.queries.append(record)
        try:
            return self.api.request(endpoint)
        except Failure as exc:
            record.update(status='partial', reason=exc.kind)
            return None

    def scope(self):
        repos = self.pages('scope:affiliations', 'user/repos', params={'affiliation': 'owner,collaborator,organization_member'})
        record = {'query': 'scope:contributions', 'status': 'complete', 'pages': 0}
        self.queries.append(record)
        cursor = None
        try:
            for page in range(self.max_pages):
                query = 'query { viewer { repositoriesContributedTo(first:100, includeUserRepositories:true, after:%s, contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY,PULL_REQUEST_REVIEW]) { nodes { databaseId nameWithOwner url defaultBranchRef { name } } pageInfo { hasNextPage endCursor } } } }' % json.dumps(cursor)
                data = self.api.request('graphql', graphql=query)['data']['viewer']['repositoriesContributedTo']
                for r in data['nodes']:
                    repos.append({'id': r['databaseId'], 'full_name': r['nameWithOwner'], 'html_url': r['url'], 'default_branch': (r['defaultBranchRef'] or {}).get('name')})
                record['pages'] = page + 1
                if not data['pageInfo']['hasNextPage']:
                    break
                next_cursor = data['pageInfo']['endCursor']
                if not next_cursor or next_cursor == cursor:
                    raise Failure('pagination_stalled')
                cursor = next_cursor
            else:
                raise Failure('truncated')
        except (Failure, KeyError, TypeError) as exc:
            record.update(status='partial', reason=exc.kind if isinstance(exc, Failure) else 'invalid_response')
        return unique([{'id': r['id'], 'name': r['full_name'], 'url': r['html_url'], 'default_branch': r.get('default_branch')} for r in repos], lambda r: str(r['id']))

    def repository(self, repo, login):
        start_query = len(self.queries)
        name = repo['name']
        base = 'repos/' + name
        events, unfinished, commits = [], [], []
        def event(kind, item, at):
            if self.inside(at):
                events.append({'id': '%s:%s:%s' % (name, kind, item['id']), 'kind': kind, 'at': at, 'url': item['html_url'], 'title': item.get('title', '')})
        prs = unique(self.pages(name + ':pulls', base + '/pulls', params={'state': 'all'}), lambda p: str(p['id']))
        for pr in prs:
            event('pr_opened', pr, pr['created_at'])
            event('pr_merged' if pr.get('merged_at') else 'pr_closed_unmerged', pr, pr.get('merged_at') or pr.get('closed_at'))
            if pr['state'] == 'open':
                evidence = []
                if pr.get('draft'):
                    evidence.append('draft_pr')
                if any(u['login'] == login for u in pr.get('requested_reviewers', [])):
                    evidence.append('review_requested')
                evidence.append('open_pr')
                unfinished.append({'id': 'pr:' + str(pr['id']), 'url': pr['html_url'], 'title': pr['title'], 'created_at': pr['created_at'], 'predates_window': timestamp(pr['created_at']) < self.start, 'evidence': evidence})
            # All available histories, including closed PRs/deleted source branches.
            history = self.pages(name + ':pr_commits:' + str(pr['number']), base + '/pulls/%s/commits' % pr['number'])
            if len(history) >= 250:
                self.queries.append({'query': name + ':pr_commits:' + str(pr['number']), 'status': 'partial', 'reason': 'github_pr_commit_ceiling'})
            commits.extend(history)
        issues = self.pages(name + ':issues', base + '/issues', params={'state': 'all'})
        for issue in unique(issues, lambda i: str(i['id'])):
            if 'pull_request' in issue:
                continue
            event('issue_opened', issue, issue['created_at'])
            event('issue_closed', issue, issue.get('closed_at'))
            if issue['state'] == 'open' and issue.get('assignees'):
                unfinished.append({'id': 'issue:' + str(issue['id']), 'url': issue['html_url'], 'title': issue['title'], 'evidence': ['assigned_open_issue'], 'assignees': sorted(u['login'] for u in issue['assignees']), 'predates_window': timestamp(issue['created_at']) < self.start})
        branches = self.pages(name + ':branches', base + '/branches')
        pr_branches = {p.get('head', {}).get('ref') for p in prs if p['state'] == 'open' and (p.get('head', {}).get('repo') or {}).get('full_name') == name}
        for branch in unique(branches, lambda b: b['name']):
            commits.extend(self.pages(name + ':commits:' + branch['name'], base + '/commits', params={'sha': branch['name'], 'since': utc(self.start), 'until': utc(self.end)}))
            if repo['default_branch'] and branch['name'] != repo['default_branch'] and branch['name'] not in pr_branches:
                comparison = self.one(name + ':compare:' + branch['name'], base + '/compare/' + quote(repo['default_branch'], safe='') + '...' + quote(branch['name'], safe=''))
                if comparison and comparison.get('ahead_by', 0) > 0:
                    unfinished.append({'id': 'branch:' + branch['name'], 'branch': branch['name'], 'url': repo['url'] + '/tree/' + quote(branch['name'], safe=''), 'evidence': ['non_default_branch_ahead_without_observed_open_pr'], 'ahead_by': comparison['ahead_by']})
        runs = self.pages(name + ':window_runs', base + '/actions/runs', 'workflow_runs', {})
        active = self.pages(name + ':active_runs', base + '/actions/runs', 'workflow_runs', {'status': 'in_progress'})
        queued = self.pages(name + ':queued_runs', base + '/actions/runs', 'workflow_runs', {'status': 'queued'})
        ci = []
        for run in unique(runs + active + queued, lambda r: str(r['id'])):
            if run['status'] != 'completed':
                unfinished.append({'id': 'run:' + str(run['id']), 'url': run['html_url'], 'evidence': ['run_' + run['status']]})
            for number in range(1, run.get('run_attempt', 1) + 1):
                attempt = run if number == run.get('run_attempt', 1) else self.one(name + ':attempt:%s:%s' % (run['id'], number), base + '/actions/runs/%s/attempts/%s' % (run['id'], number))
                if attempt and self.inside(attempt.get('run_started_at')):
                    ci.append({'id': '%s:%s' % (run['id'], number), 'run_id': run['id'], 'attempt': number, 'url': run['html_url'], 'workflow': run.get('name'), 'branch': run.get('head_branch'), 'sha': run.get('head_sha'), 'started_at': attempt['run_started_at'], 'status': attempt['status'], 'conclusion': attempt.get('conclusion'), 'latest_conclusion_observed': run.get('conclusion')})
        selected = []
        for commit in commits:
            at = commit['commit']['committer']['date']
            if self.inside(at):
                selected.append({'sha': commit['sha'], 'url': commit['html_url'], 'committed_at': at, 'title': commit['commit']['message'].split('\n')[0]})
        queries = self.queries[start_query:]
        return {'repository_id': repo['id'], 'name': name, 'status': 'partial' if any(q['status'] != 'complete' for q in queries) else 'complete_with_documented_limits', 'activity': unique(events, lambda e: e['id']), 'commits': unique(selected, lambda c: c['sha']), 'ci_attempts': unique(ci, lambda r: r['id']), 'current_unfinished_evidence': unique(unfinished, lambda e: e['id']), 'queries': queries}

    def collect(self):
        user = self.one('viewer', 'user')
        repos = self.scope()
        results = [self.repository(r, user['login'] if user else '') for r in repos]
        return {'schema_version': VERSION, 'coverage': {'implementation': 'bounded_local_slice', 'rollout_ready': False, 'historical_state_reconstruction': False, 'linked_issue_pr_relationships': 'not_collected', 'team_review_requests': 'not_collected', 'lifecycle_reopens': 'latest_timestamps_only'}, 'window': {'start': utc(self.start), 'end': utc(self.end), 'bounds': '[start,end)', 'commit_time': 'committer date; not push time', 'ci_time': 'attempt run_started_at'}, 'collected_at': self.observed, 'current_state_as_of': self.observed, 'scope': repos, 'scope_queries': [q for q in self.queries if q['query'].startswith('scope:') or q['query'] == 'viewer'], 'status': 'partial' if any(q['status'] != 'complete' for q in self.queries) else 'complete_with_documented_limits', 'counts': {'repositories': len(repos), 'events': sum(len(r['activity']) for r in results), 'commits_per_repository': sum(len(r['commits']) for r in results), 'partial_queries': sum(q['status'] != 'complete' for q in self.queries)}, 'repositories': results, 'limitations': ['Current state is observed now, not reconstructed at window end.', 'Contribution discovery is limited to GitHub viewer repositoriesContributedTo visibility/history.', 'Deleted branches without available PR history and unreachable commits cannot be recovered.', 'Issue/PR REST timestamps expose latest lifecycle state, not every reopen/close transition.', 'REST PR commits endpoint has a documented 250-commit ceiling; histories at that size require follow-up.', 'CI scans available run history and filters attempt start times; deleted/expired runs remain unavailable. Later success is observed per run, not inferred across separate runs.', 'Linked PR relationships and requested team reviews are not resolved in this slice.']}


def write_atomic(path, artifact):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(artifact, stream, sort_keys=True, separators=(',', ':'))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--end', help='UTC/offset timestamp; defaults to one captured UTC now')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    end = args.end or utc(datetime.now(timezone.utc))
    artifact = Collector(Gh(), end).collect()
    write_atomic(args.output, artifact)
    return 2 if artifact['status'] == 'partial' else 0


if __name__ == '__main__':
    raise SystemExit(main())
