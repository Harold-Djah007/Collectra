from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from corehq.pillows.collectra import (
    MANAGED_PILLOWS, checkpoint_after_rebuild, processor_selection, replay_changes, replay_start, runtime_states,
)


class RecoveryTests(SimpleTestCase):
    @patch('corehq.pillows.user.get_checkpoint_for_elasticsearch_pillow')
    def test_user_index_ignores_domain_removal_audit_without_username(self, checkpoint):
        from corehq.pillows.user import get_user_pillow_old
        change = MagicMock()
        change.deleted = False
        change.get_document.return_value = {'doc_type': 'DomainRemovalRecord', '_id': 'audit'}
        with patch('corehq.pillows.user.user_adapter') as adapter:
            get_user_pillow_old().process_change(change)
        adapter.index.assert_not_called()

    def make_pillow(self):
        pillow = MagicMock()
        pillow.change_feed.sequence_format = 'text'
        pillow.change_feed._consumer = None
        pillow.change_feed.iter_changes.return_value = iter([
            SimpleNamespace(sequence_id='1'), SimpleNamespace(sequence_id='2'),
        ])
        return pillow

    def test_failure_never_advances_past_failed_change(self):
        pillow = self.make_pillow()
        pillow.process_change.side_effect = [None, RuntimeError('processing failed')]
        with self.assertRaisesRegex(RuntimeError, 'processing failed'):
            replay_changes(pillow, '0')
        pillow.checkpoint.update_to.assert_not_called()

    def test_complete_pass_checkpoints_last_success(self):
        pillow = self.make_pillow()
        self.assertEqual(replay_changes(pillow, '0'), 2)
        pillow.checkpoint.update_to.assert_called_once_with('2')

    def test_ahead_requires_explicit_replay_from_earliest_not_end(self):
        with self.assertRaises(ValueError):
            replay_start({'topic': 100}, {'topic': 0}, {'topic': 10})
        self.assertEqual(replay_start({'topic': 100}, {'topic': 0}, {'topic': 10}, True), {'topic': 0})

    def test_expired_source_history_is_not_silently_skipped(self):
        with self.assertRaisesRegex(ValueError, 'authoritative rebuild'):
            replay_start({'topic': 0}, {'topic': 5}, {'topic': 10}, True)

    def test_messaging_replay_is_not_allowed_by_basic_recovery(self):
        with self.assertRaises(CommandError):
            call_command('recover_collectra_processors', backup_dir='unused', only='case_messaging_sync_pillow')

    def test_duplicate_processors_are_not_selected_together(self):
        self.assertEqual(len(MANAGED_PILLOWS), len(set(MANAGED_PILLOWS)))
        self.assertTrue(processor_selection('UserPillow')['managed'])
        self.assertFalse(processor_selection('user-pillow')['managed'])
        self.assertFalse(processor_selection('case-pillow')['managed'])

    def test_failed_authoritative_rebuild_never_moves_checkpoint(self):
        pillow = self.make_pillow()
        rebuild = MagicMock(side_effect=RuntimeError('source missing'))
        with self.assertRaises(RuntimeError):
            checkpoint_after_rebuild([('worker', pillow, '10')], {'worker'}, rebuild)
        pillow.checkpoint.update_to.assert_not_called()

    def test_completed_rebuild_allows_only_selected_expired_checkpoint(self):
        pillow = self.make_pillow()
        other = self.make_pillow()
        checkpoint_after_rebuild([('worker', pillow, '10'), ('other', other, '20')], {'worker'}, lambda: None)
        pillow.checkpoint.update_to.assert_called_once_with('10')
        other.checkpoint.update_to.assert_not_called()

    def test_stale_supervisor_heartbeat_does_not_claim_workers_are_running(self):
        state = {'updated': 0, 'workers': {name: True for name in MANAGED_PILLOWS}}
        self.assertEqual(set(runtime_states(state, 31).values()), {'stopped'})

    def test_only_boolean_true_is_live_worker_evidence(self):
        state = {'updated': 0, 'workers': {'UserPillow': 'false'}}
        self.assertEqual(runtime_states(state, 1)['UserPillow'], 'stopped')
        self.assertEqual(runtime_states({}, 1), {})
