import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('collector', Path(__file__).with_name('collect_github_briefing.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
END = '2026-10-26T14:03:11Z'


class Fake:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return value


class CollectorTests(unittest.TestCase):
    def test_query_records_timing_and_api_calls(self):
        api = Fake([[]])
        c = m.Collector(api, END)
        self.assertEqual(c.pages('timed', 'endpoint'), [])
        query = c.queries[0]
        self.assertEqual(query['api_calls'], 1)
        self.assertGreaterEqual(query['elapsed_seconds'], 0)
        self.assertRegex(query['observed_at'], r'Z$')

    def test_initial_artifact_survives_interruption(self):
        class Interrupted(Fake):
            def request(self, endpoint, **kwargs):
                raise KeyboardInterrupt
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'artifact.json'
            with self.assertRaises(KeyboardInterrupt):
                m.Collector(Interrupted([]), END, observed=END).collect(path)
            artifact = json.loads(path.read_text())
            self.assertEqual(artifact['window']['end'], END)
            self.assertEqual(artifact['status'], 'partial')
            self.assertEqual(artifact['counts']['completed_repositories'], 0)

    def test_same_window_resume_skips_completed_repository(self):
        repo = {'id': 1, 'full_name': 'a/b', 'html_url': 'https://github.com/a/b', 'default_branch': 'main'}

        class Dynamic:
            def __init__(self):
                self.calls = []
            def request(self, endpoint, **kwargs):
                self.calls.append(endpoint)
                if endpoint == 'user':
                    return {'login': 'danmaps'}
                if endpoint.startswith('user/repos'):
                    return [repo]
                if endpoint == 'graphql':
                    return {'data': {'viewer': {'repositoriesContributedTo': {'nodes': [], 'pageInfo': {'hasNextPage': False}}}}}
                if '/pulls' in endpoint or '/issues' in endpoint or '/branches' in endpoint:
                    return []
                if '/actions/runs' in endpoint:
                    return {'workflow_runs': []}
                raise AssertionError(endpoint)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'artifact.json'
            api = Dynamic()
            first = m.Collector(api, END, observed=END, max_workers=1).collect(path)
            first_calls = len(api.calls)
            self.assertEqual(first['counts']['completed_repositories'], 1)
            api.calls.clear()
            resumed = m.Collector(api, END, observed=END, max_workers=1).collect(path, first)
            self.assertEqual(resumed['counts']['completed_repositories'], 1)
            self.assertEqual(api.calls, ['user', 'user/repos?affiliation=owner%2Ccollaborator%2Corganization_member&per_page=100&page=1', 'graphql'])
            self.assertGreater(first_calls, len(api.calls))

    def test_exact_window_and_offsets(self):
        c = m.Collector(None, END)
        self.assertFalse(c.inside('2026-10-25T14:03:10Z'))
        self.assertTrue(c.inside('2026-10-25T14:03:11Z'))
        self.assertTrue(c.inside('2026-10-26T07:03:10-07:00'))
        self.assertFalse(c.inside(END))
        with self.assertRaises(ValueError):
            m.timestamp('2026-10-26T14:03:11')

    def test_pagination_and_partial_retains_evidence(self):
        api = Fake([[{'id': n} for n in range(100)], m.Failure('access_denied')])
        c = m.Collector(api, END)
        self.assertEqual(len(c.pages('q', 'endpoint')), 100)
        self.assertIn('page=2', api.calls[1][0])
        self.assertEqual(c.queries[0]['reason'], 'access_denied')

    def test_empty_and_truncated_are_distinct(self):
        c = m.Collector(Fake([[], list(range(100))]), END, max_pages=1)
        self.assertEqual(c.pages('empty', 'x'), [])
        c.pages('capped', 'x')
        self.assertEqual(c.queries[0]['status'], 'complete')
        self.assertEqual(c.queries[1]['reason'], 'truncated')

    def test_deterministic_dedup_preserves_lifecycle(self):
        items = [{'id': '1:opened'}, {'id': '1:closed'}, {'id': '1:opened'}]
        self.assertEqual(m.unique(items, lambda x: x['id']), m.unique(list(reversed(items)), lambda x: x['id']))
        self.assertEqual(len(m.unique(items, lambda x: x['id'])), 2)

    def test_scope_union_and_graphql_cursor(self):
        def graph(nodes, more=False, cursor=None):
            return {'data': {'viewer': {'repositoriesContributedTo': {'nodes': nodes, 'pageInfo': {'hasNextPage': more, 'endCursor': cursor}}}}}
        r = {'databaseId': 1, 'nameWithOwner': 'a/b', 'url': 'https://github.com/a/b', 'defaultBranchRef': {'name': 'main'}}
        api = Fake([[{'id': 1, 'full_name': 'a/b', 'html_url': r['url'], 'default_branch': 'main'}], graph([r], True, 'next'), graph([dict(r, databaseId=2, nameWithOwner='a/c')])])
        c = m.Collector(api, END)
        self.assertEqual(len(c.scope()), 2)
        self.assertIn('after:"next"', api.calls[-1][1]['graphql'])

    def test_repository_commits_across_sources_and_current_backlog(self):
        commit = {'sha': 'abc', 'html_url': 'https://github.com/a/b/commit/abc', 'commit': {'committer': {'date': '2026-10-25T14:03:11Z'}, 'message': 'hello\nbody'}}
        pr = {'id': 1, 'number': 1, 'created_at': '2026-10-20T00:00:00Z', 'closed_at': None, 'state': 'open', 'draft': True, 'requested_reviewers': [{'login': 'danmaps'}], 'html_url': 'https://github.com/a/b/pull/1', 'title': 'work', 'head': {'sha': 'abc'}}
        api = Fake([[pr], [commit, commit], [], [{'name': 'main', 'commit': {'sha': 'abc'}}], [commit], {'workflow_runs': []}, {'workflow_runs': []}, {'workflow_runs': []}])
        result = m.Collector(api, END).repository({'name': 'a/b', 'id': 1, 'default_branch': 'main'}, 'danmaps')
        self.assertEqual(len(result['commits']), 1)
        self.assertEqual(result['activity'], [])
        evidence = result['current_unfinished_evidence'][0]
        self.assertTrue(evidence['predates_window'])
        self.assertIn('review_requested', evidence['evidence'])

    def test_old_run_rerun_failure_and_recovery(self):
        failed = {'run_started_at': '2026-10-25T15:00:00Z', 'status': 'completed', 'conclusion': 'failure'}
        run = {'id': 12, 'run_attempt': 2, 'created_at': '2026-10-01T00:00:00Z', 'run_started_at': '2026-10-26T13:00:00Z', 'status': 'completed', 'conclusion': 'success', 'html_url': 'https://github.com/a/b/actions/runs/12', 'name': 'CI', 'head_branch': 'main', 'head_sha': 'abc'}
        api = Fake([[], [], [], {'workflow_runs': [run]}, {'workflow_runs': []}, {'workflow_runs': []}, failed])
        result = m.Collector(api, END).repository({'name': 'a/b', 'id': 1, 'default_branch': 'main'}, 'danmaps')
        self.assertEqual([a['conclusion'] for a in result['ci_attempts']], ['failure', 'success'])
        self.assertEqual(result['ci_attempts'][0]['latest_conclusion_observed'], 'success')
        self.assertNotIn('created=', api.calls[3][0])

    def test_failed_scope_still_writes_explicit_partial_artifact(self):
        api = Fake([m.Failure('transport_unavailable'), m.Failure('transport_unavailable'), m.Failure('transport_unavailable')])
        result = m.Collector(api, END, observed=END).collect()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['counts']['repositories'], 0)
        self.assertEqual(result['counts']['partial_queries'], 3)
        self.assertFalse(result['coverage']['rollout_ready'])

    def test_deterministic_complete_empty_collection(self):
        graph = {'data': {'viewer': {'repositoriesContributedTo': {'nodes': [], 'pageInfo': {'hasNextPage': False}}}}}
        def collect():
            return m.Collector(Fake([{'login': 'danmaps'}, [], graph]), END, observed=END).collect()
        self.assertEqual(json.dumps(collect(), sort_keys=True), json.dumps(collect(), sort_keys=True))

    def test_atomic_safe_rerun_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'artifact.json'
            m.write_atomic(path, {'b': 2, 'a': 1})
            first = path.read_bytes()
            m.write_atomic(path, {'a': 1, 'b': 2})
            self.assertEqual(path.read_bytes(), first)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(TypeError):
                m.write_atomic(path, {'bad': object()})
            self.assertEqual(path.read_bytes(), first)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def response(self, status, body, headers=''):
        return SimpleNamespace(returncode=int(status >= 400), stdout='HTTP/2 %s Test\n%s\n%s' % (status, headers, json.dumps(body)), stderr='TOKEN_DO_NOT_EXPOSE')

    def test_retry_after_and_recovery(self):
        responses = iter([self.response(429, {}, 'retry-after: 3\n'), self.response(200, [])])
        waits = []
        api = m.Gh(run=lambda *a, **k: next(responses), sleep=waits.append)
        self.assertEqual(api.request('user/repos'), [])
        self.assertEqual(waits, [3])

    def test_bounded_retry_and_no_raw_error(self):
        calls = []
        def run(*args, **kwargs):
            calls.append(args)
            return self.response(503, {'secret': 'TOKEN_DO_NOT_EXPOSE'})
        with self.assertRaises(m.Failure) as error:
            m.Gh(run=run, sleep=lambda n: None).request('user')
        self.assertEqual(len(calls), 3)
        self.assertNotIn('TOKEN', str(error.exception))

    def test_long_rate_reset_and_access_denied(self):
        for status, headers, reason in [(429, 'retry-after: 9999\n', 'rate_limited'), (403, '', 'access_denied'), (404, '', 'unavailable')]:
            with self.assertRaises(m.Failure) as error:
                m.Gh(run=lambda *a, **k: self.response(status, {}, headers), sleep=lambda n: self.fail('unexpected wait')).request('user')
            self.assertEqual(error.exception.kind, reason)

    def test_graphql_errors_not_empty(self):
        with self.assertRaises(m.Failure):
            m.Gh(run=lambda *a, **k: self.response(200, {'errors': [{'message': 'sensitive'}]})).request('graphql')


if __name__ == '__main__':
    unittest.main()
