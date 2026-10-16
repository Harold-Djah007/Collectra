"""The non-overlapping processors used by the Collectra runtime."""

from contextlib import contextmanager
from pathlib import Path


# Producers precede their consumers. Messaging and optional reporting pipelines
# are deliberately excluded: replaying those can trigger business actions.
MANAGED_PILLOWS = (
    'AppDbChangeFeedPillow', 'DomainDbKafkaPillow', 'UserGroupsDbKafkaPillow',
    'CaseToElasticsearchPillow', 'XFormToElasticsearchPillow',
    'UserPillow', 'group-pillow', 'ApplicationToElasticsearchPillow',
    'KafkaDomainPillow', 'UpdateUserSyncHistoryPillow',
    'FormSubmissionMetadataTrackerPillow', 'UnknownUsersPillow',
    'CacheInvalidatePillow', 'UserCacheInvalidatePillow',
)

OPTIONAL_REASONS = {
    'case-pillow': 'Combined case/reporting/messaging pipeline; basic case indexing runs separately.',
    'xform-pillow': 'Combined form pipeline; indexing and metadata processors run separately.',
    'user-pillow': 'Combined user/custom-report pipeline; user indexing runs separately.',
    'GroupPillow': 'Replaced by group-pillow in the Collectra runtime.',
    'GroupToUserPillow': 'Group membership processing is included in group-pillow.',
    'kafka-ucr-main': 'Optional custom-report pipeline.',
    'kafka-ucr-static': 'Optional static-report pipeline.',
    'location-ucr-pillow': 'Optional location-report pipeline.',
    'CaseSearchToElasticsearchPillow': 'Optional case-search pipeline.',
    'LedgerToElasticsearchPillow': 'Optional stock-ledger pipeline.',
    'SqlSMSPillow': 'Optional SMS indexing pipeline.',
    'case_messaging_sync_pillow': 'Messaging-rule replay requires separate configuration.',
}


def processor_selection(name, runtime=None):
    return {
        'managed': name in MANAGED_PILLOWS,
        'selection_note': ('Selected for the Collectra runtime.' if name in MANAGED_PILLOWS
                           else OPTIONAL_REASONS.get(name, 'Not selected for this runtime.')),
        'runtime_state': (runtime or {}).get(name, 'unknown'),
    }


def processor_state_path():
    from django.conf import settings
    return Path(settings.SHARED_DRIVE_ROOT) / 'collectra-processors.json'


def runtime_states(state, now):
    """Treat absent, malformed or stale heartbeat evidence as unknown."""
    if not isinstance(state, dict) or not isinstance(state.get('updated'), (int, float)):
        return {}
    if not 0 <= now - state['updated'] <= 30:
        return {name: 'stopped' for name in MANAGED_PILLOWS}
    workers = state.get('workers')
    if not isinstance(workers, dict):
        return {}
    return {name: ('running' if workers.get(name) is True else 'stopped') for name in MANAGED_PILLOWS}


def read_processor_states():
    import json
    import time
    try:
        state = json.loads(processor_state_path().read_text())
    except (OSError, ValueError):
        return {}
    return runtime_states(state, time.time())


def write_processor_states(workers):
    import json
    import os
    import tempfile
    import time
    target = processor_state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as stream:
            temporary = stream.name
            json.dump({'updated': time.time(), 'workers': workers}, stream)
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def replay_start(since, first, last, replay_ahead=False):
    """Never fast-forward across expired or inconsistent source history."""
    if any(since[tp] < first[tp] for tp in since):
        raise ValueError('Source retention passed the checkpoint; an authoritative rebuild is required.')
    if any(since[tp] > last[tp] for tp in since):
        if not replay_ahead:
            raise ValueError('Checkpoint ahead of source; inspect the backup before choosing replay.')
        return dict(first)
    return dict(since)


def checkpoint_after_rebuild(plans, expired, rebuild):
    """Do not acknowledge expired history until its derived state is rebuilt."""
    rebuild()
    for name, pillow, since in plans:
        if name in expired:
            pillow.checkpoint.update_to(since)


@contextmanager
def processor_lock():
    """Prevent a recovery and the managed supervisor from running together."""
    import fcntl

    # Respect an in-flight recovery from the earlier local-lock location while
    # migrating to the shared-volume lock used across production containers.
    legacy = Path.home() / '.local/state/collectra/processors.lock'
    if legacy.exists():
        with legacy.open('a') as previous:
            try:
                fcntl.flock(previous, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('An earlier Collectra recovery is still running.')
            fcntl.flock(previous, fcntl.LOCK_UN)
    # Shared by web/worker containers, so maintenance cannot race the supervisor.
    root = processor_state_path().parent
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'collectra-processors.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Collectra processors are already running; stop their supervisor first.')
        try:
            yield lock
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def replay_changes(pillow, since, report=lambda count: None):
    """Replay retained events, stopping before checkpointing a failed event.

    A crash can replay successful events, but never skips an unsuccessful event.
    This is only used with the idempotent managed processors above.
    """
    count = 0
    last_sequence = None
    feed = pillow.change_feed
    try:
        for change in feed.iter_changes(since=since, forever=False):
            if change is None:
                continue
            pillow.process_change(change)
            last_sequence = (feed.get_current_checkpoint_offsets()
                             if feed.sequence_format == 'json' else change.sequence_id)
            count += 1
            if count % 100 == 0:
                pillow.checkpoint.update_to(last_sequence)
                report(count)
        if last_sequence is not None:
            pillow.checkpoint.update_to(last_sequence)
        return count
    finally:
        consumer = getattr(feed, '_consumer', None)
        if consumer is not None:
            consumer.close()
