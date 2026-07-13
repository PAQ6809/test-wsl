import os
import tempfile
from pathlib import Path

HOME = Path(tempfile.mkdtemp(prefix="restoration-worker-tests-"))
os.environ["RESTORATION_WORKER_HOME"] = str(HOME)
