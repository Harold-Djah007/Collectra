"""Record a deterministic source identity for images without Git history."""
import hashlib
import json
import os
from pathlib import Path


def write_metadata(root):
    root = Path(root)
    digest = hashlib.sha256()
    ignored = {'.git', '.venv', 'node_modules', 'staticfiles', 'sharedfiles',
               '__pycache__', '.pytest_cache', 'log'}
    for directory, children, filenames in os.walk(root):
        children[:] = sorted(name for name in children if name not in ignored)
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if filename == '.collectra-build.json' or path.is_symlink():
                continue
            if path.suffix not in {'.py', '.js', '.html', '.xml', '.xsl', '.css',
                                   '.scss', '.json', '.yaml', '.yml', '.toml', '.lock'}:
                continue
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b'\0')
            with path.open('rb') as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
            digest.update(b'\0')
    snapshot = {'current_branch': 'container', 'commits': [{
        'sha': digest.hexdigest(), 'subject': 'Collectra source image',
        'author': 'Collectra build', 'date': '', 'message': '',
        'commit_url': '', 'compare_master': '',
    }]}
    (root / '.collectra-build.json').write_text(json.dumps(snapshot), encoding='utf-8')
    return snapshot


if __name__ == '__main__':
    write_metadata(Path(__file__).resolve().parents[2])
