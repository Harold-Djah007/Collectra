import tarfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from django.core.management import BaseCommand

from corehq.blobs import get_blob_db
from corehq.util.log import with_progress_bar

USAGE = "Usage: ./manage.py run_blob_import <filename>"
NUM_WORKERS = 5


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, filename, **options):
        import_blobs_from_tgz(filename)


def import_blobs_from_tgz(filename):
    print(f"Inspecting the size of {filename}.")
    print("This can take ~8 minutes for a 30G file.")
    with tarfile.open(filename, 'r|gz', stream=True) as archive:
        total = sum(1 for _ in archive)

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        func = partial(worker, filename, total // NUM_WORKERS)
        futures = executor.map(func, range(NUM_WORKERS))
        return list(futures)  # Resolves results and exceptions from workers


def worker(filename, length, worker_number):
    """
    Each worker claims the ``worker_number``th file in the ``filename``
    tar.gz file, and copies it to blob_db.

    Iterated file handles for blobs cannot be passed to coroutines or
    futures, because as soon as the caller iterates to the next blob,
    the previous handle is closed. We could read the data and pass that,
    but blobs can be too big to read at once.

    So threaded workers all need to read the same tar.gz file and
    iterate the files inside it, picking out the ones that belong to
    them.
    """
    # ^^^ Yeah, not great. Maybe filesystem caching helps.
    blob_db = get_blob_db()
    # Do not retain every TarInfo or seek backwards through compressed data.
    # Each worker reads forward and copies its current member before advancing.
    with tarfile.open(filename, 'r|gz', stream=True) as tgzfile:
        iterable = (tarinfo for i, tarinfo in enumerate(tgzfile)
                    if i % NUM_WORKERS == worker_number)
        prefix = f"Worker {worker_number}"
        for tarinfo in with_progress_bar(iterable, length, prefix=prefix, oneline=False):
            key = tarinfo.name
            fileobj = tgzfile.extractfile(tarinfo)
            blob_db.copy_blob(fileobj, key)
