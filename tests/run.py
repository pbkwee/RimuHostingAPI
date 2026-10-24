"""Run all offline regression suites."""
from pathlib import Path
import subprocess
import sys

for test in sorted(Path(__file__).resolve().parent.glob('test-*.py')):
    print('Running ' + test.name, flush=True)
    result = subprocess.run([sys.executable, '-B', str(test)])
    if result.returncode:
        sys.exit(result.returncode)

print('All offline tests passed (no live API calls).')
