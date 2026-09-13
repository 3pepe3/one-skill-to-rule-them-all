from __future__ import annotations

import json
import fcntl
from pathlib import Path
import tempfile
import unittest

from test_task_observer import run_cli, write_record


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'state'
        run_cli('--state-root', str(self.root), 'init')
        (self.root / 'automation.json').write_text(json.dumps({'enabled': True, 'mode': 'root-review-and-install'}))

    def call(self, name='Stop', **fields):
        return run_cli('--state-root', str(self.root), 'lifecycle', event={
            'hook_event_name': name, 'session_id': 'fixture-session', **fields})

    def test_stop_requests_one_root_review_per_pending_fingerprint(self):
        write_record(self.root, 1)
        first = self.call()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)['decision'], 'block')
        reason = json.loads(first.stdout)['reason']
        self.assertIn('classify scope before choosing targets', reason)
        self.assertIn('project-specific fixes', reason)
        self.assertNotIn('decision', json.loads(self.call().stdout))
        write_record(self.root, 2)
        self.assertEqual(json.loads(self.call().stdout)['decision'], 'block')

    def test_empty_disabled_and_recursive_stop_do_not_continue(self):
        self.assertEqual(json.loads(self.call().stdout), {})
        write_record(self.root, 1)
        self.assertEqual(json.loads(self.call(stop_hook_active=True).stdout), {})
        (self.root / 'automation.json').unlink()
        self.assertEqual(json.loads(self.call().stdout), {})

    def test_exit_records_pending_without_claiming_applied_or_starting_agent(self):
        path = write_record(self.root, 1, body='PRIVATE_SENTINEL')
        before = path.read_bytes()
        result = self.call('SessionEnd', transcript_path='/PRIVATE_TRANSCRIPT')
        self.assertEqual(result.returncode, 0, result.stderr)
        pending = (self.root / 'pending-review.json').read_text()
        self.assertNotIn('PRIVATE', pending + result.stdout)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads(pending)['open'], 1)

    def test_plan_mode_leaves_state_exact_and_does_not_continue(self):
        write_record(self.root, 1)
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.call(permission_mode='plan')
        self.assertEqual(json.loads(result.stdout), {})
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_precompact_preserves_pending_and_allows_compaction(self):
        path = write_record(self.root, 1, body='PRIVATE_SENTINEL')
        before = path.read_bytes()
        for trigger in ('manual', 'auto'):
            result = self.call('PreCompact', trigger=trigger)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {})
            marker = (self.root / 'pending-review.json').read_text()
            self.assertEqual(json.loads(marker)['event'], 'PreCompact')
            self.assertNotIn('PRIVATE', marker)
            self.assertEqual(path.read_bytes(), before)
        resumed = run_cli('--state-root', str(self.root), 'session-start', event={
            'hook_event_name': 'SessionStart', 'source': 'compact'})
        self.assertIn('root-review-and-install', resumed.stdout)

    def test_precompact_plan_and_empty_state_do_not_checkpoint(self):
        self.assertEqual(json.loads(self.call('PreCompact').stdout), {})
        write_record(self.root, 1)
        self.assertEqual(json.loads(self.call('PreCompact', permission_mode='plan').stdout), {})
        self.assertFalse((self.root / 'pending-review.json').exists())

    def test_malformed_record_fails_closed(self):
        write_record(self.root, 1, siblings_checked=None)
        result = self.call()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'pending-review.json').exists())

    def test_clear_context_recovers_automatic_review_authority(self):
        write_record(self.root, 1)
        result = run_cli('--state-root', str(self.root), 'session-start', event={
            'hook_event_name': 'SessionStart', 'source': 'clear'})
        self.assertIn('root-review-and-install', result.stdout)

    def test_exit_does_not_wait_for_busy_writer(self):
        write_record(self.root, 1)
        with (self.root / '.observer.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            self.assertEqual(json.loads(self.call('SessionEnd').stdout), {})
        self.assertFalse((self.root / 'pending-review.json').exists())

    def test_malformed_policy_and_unsupported_event_do_not_apply(self):
        write_record(self.root, 1)
        (self.root / 'automation.json').write_text('invalid JSON')
        self.assertEqual(json.loads(self.call().stdout), {})
        self.assertNotEqual(self.call('Unexpected').returncode, 0)


if __name__ == '__main__':
    unittest.main()
