"""Supervise the processors required by the Collectra runtime."""

import multiprocessing
import signal
import time

from django.core.management.base import BaseCommand

from pillowtop.run_pillowtop import start_pillow
from pillowtop.utils import get_pillow_by_name

from corehq.pillows.collectra import MANAGED_PILLOWS, processor_lock, replay_start, write_processor_states


def run_worker(name, lock_fd, ready):
    # Initialize Django/Kafka connections in the child, not before the fork.
    import os
    from django.db import connections
    os.close(lock_fd)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    connections.close_all()
    pillow = get_pillow_by_name(name)
    checkpoint = pillow.get_checkpoint()
    if checkpoint.sequence_format == 'json':
        from corehq.apps.change_feed.connection import get_kafka_consumer
        since = checkpoint.wrapped_sequence
        with get_kafka_consumer() as consumer:
            partitions = list(since)
            replay_start(since, consumer.beginning_offsets(partitions), consumer.end_offsets(partitions))
    ready.set()
    start_pillow(pillow)


class Command(BaseCommand):
    help = 'Run the non-overlapping Collectra indexing, metadata and cache processors.'

    def handle(self, **options):
        workers = {}
        readiness = {}
        stopping = False

        def stop(signum, frame):
            nonlocal stopping
            stopping = True

        with processor_lock() as lock:
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            try:
                while not stopping:
                    for name in MANAGED_PILLOWS:
                        worker = workers.get(name)
                        if worker is not None and worker.is_alive():
                            continue
                        if worker is not None:
                            worker.join()
                            self.stderr.write(f'Restarting {name}, exit={worker.exitcode}')
                        # Share imported code pages on memory-constrained local hosts.
                        # The child closes the inherited lock and DB connections.
                        from django.db import connections
                        connections.close_all()
                        context = multiprocessing.get_context('fork')
                        ready = context.Event()
                        worker = context.Process(target=run_worker, args=(name, lock.fileno(), ready))
                        worker.start()
                        workers[name] = worker
                        readiness[name] = ready
                    write_processor_states({name: worker.is_alive() and readiness[name].is_set()
                                            for name, worker in workers.items()})
                    time.sleep(5)
            finally:
                for worker in workers.values():
                    if worker.is_alive():
                        worker.terminate()
                deadline = time.monotonic() + 15
                for worker in workers.values():
                    worker.join(timeout=max(0, deadline - time.monotonic()))
                    if worker.is_alive():
                        worker.kill()
                        worker.join()
                write_processor_states({name: False for name in workers})
