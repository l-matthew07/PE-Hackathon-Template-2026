import os
import shutil

# Clean stale multiprocess prometheus files on startup
prom_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
if prom_dir:
    shutil.rmtree(prom_dir, ignore_errors=True)
    os.makedirs(prom_dir, exist_ok=True)

from app import create_app

app = create_app()
