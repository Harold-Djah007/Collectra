"""Back up processor positions and replay retained events without skipping failures."""

import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from pillowtop.models import DjangoPillowCheckpoint, KafkaCheckpoint
from pillowtop.utils import get_pillow_by_name

from corehq.apps.change_feed.connection import get_kafka_consumer
from corehq.pillows.collectra import (
    MANAGED_PILLOWS, checkpoint_after_rebuild, processor_lock, replay_changes, replay_start,
)
from corehq.pillows.collectra_rebuild import REBUILDABLE, rebuild_from_source


class Command(BaseCommand):
    help = 'Back up checkpoints, then replay selected inactive managed processors. No messaging pipelines.'

    def add_arguments(self, parser):
        parser.add_argument('--backup-dir', required=True)
        parser.add_argument('--only', required=True,
                            help='Comma-separated managed processor names; stop them first.')
        parser.add_argument('--replay-ahead', action='store_true',
                            help='Replay earliest retained events when a checkpoint is ahead of its source.')
        parser.add_argument('--rebuild-expired', action='store_true',
                            help='Rebuild supported derived state before replaying retained events.')

    def handle(self, backup_dir, only, replay_ahead, rebuild_expired, **options):
        names = only.split(',')
        if not names or any(name not in MANAGED_PILLOWS for name in names):
            raise CommandError('Recovery only supports explicitly selected managed processors.')
        with processor_lock():
            root = Path(backup_dir).resolve()
            root.mkdir(parents=True, exist_ok=True)
            backup = root / ('checkpoints-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
            with backup.open('x') as stream:
                json.dump({
                    'selected': names,
                    'django': list(DjangoPillowCheckpoint.objects.values()),
                    'kafka': list(KafkaCheckpoint.objects.values()),
                }, stream, default=str, indent=2)
            self.stdout.write(f'Checkpoint backup: {backup}')
            plans = []
            expired = set()
            # Take the replay decisions before producers append new source events.
            with get_kafka_consumer() as consumer:
                for name in names:
                    pillow = get_pillow_by_name(name)
                    checkpoint = pillow.get_checkpoint()
                    since = checkpoint.wrapped_sequence
                    if checkpoint.sequence_format == 'json':
                        partitions = list(since)
                        first = consumer.beginning_offsets(partitions)
                        last = consumer.end_offsets(partitions)
                        try:
                            if any(since[tp] < first[tp] for tp in partitions):
                                if not rebuild_expired or name not in REBUILDABLE:
                                    raise ValueError('Source retention passed the checkpoint; rebuild required.')
                                expired.add(name)
                                since = first
                            else:
                                since = replay_start(since, first, last, replay_ahead)
                        except ValueError as exc:
                            raise CommandError(f'{name}: {exc}') from exc
                    plans.append((name, pillow, since))
            if expired:
                checkpoint_after_rebuild(
                    plans, expired,
                    lambda: rebuild_from_source(expired, backup.with_suffix(''), self.stdout.write),
                )
            for name, pillow, since in plans:
                self.stdout.write(f'REPLAY {name}')
                count = replay_changes(pillow, since,
                                       report=lambda count: self.stdout.write(f'{name}: {count} processed'))
                self.stdout.write(f'COMPLETE {name}: {count} events')
