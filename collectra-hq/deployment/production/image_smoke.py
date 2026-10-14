"""Verify native imports and compiled assets inside the production image."""
import importlib
import json
import os
import shutil
import subprocess
from pathlib import Path


def main():
    if os.geteuid() == 0:
        raise RuntimeError("The production image must run as a non-root user")
    if os.environ.get("UV_NO_SYNC") != "1":
        raise RuntimeError("Runtime uv commands must not install build/dev dependencies")
    for module in ("django", "gevent", "psycopg2", "xmlsec", "lxml.etree", "celery"):
        importlib.import_module(module)
    for command in (["node", "--version"], ["java", "-version"], ["google-chrome", "--version"]):
        subprocess.run(command, check=True, capture_output=True, timeout=30)
    if shutil.which("gcc") or shutil.which("g++"):
        raise RuntimeError("Compiler binaries should remain in the builder stage")
    root = Path(__file__).resolve().parents[2]
    for name, directory in (("manifest.json", "webpack"), ("manifest_b3.json", "webpack_b3")):
        manifest = json.loads((root / "webpack/_build" / name).read_text())
        if not manifest:
            raise RuntimeError(f"Empty webpack manifest: {name}")
        for entry, assets in manifest.items():
            if not assets:
                raise RuntimeError(f"Webpack entry has no assets: {entry}")
            for asset in assets:
                if not (root / "staticfiles" / directory / asset).is_file():
                    raise RuntimeError(f"Compiled asset missing for {entry}")
    print("Production image native imports, runtime tools, user, and compiled assets passed.")


if __name__ == "__main__":
    main()
