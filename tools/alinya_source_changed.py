#!/usr/bin/env python3
"""Return 0 for changed source content, 1 for check-only changes (git HEAD baseline)."""
import json
from pathlib import Path
import subprocess
import sys
from alinya_reading_freshness import fingerprint


def changed(path):
    path=Path(path)
    previous=subprocess.run(['git','show','HEAD:'+path.as_posix()],capture_output=True)
    if previous.returncode:
        return path.exists()
    if not path.exists():
        raise FileNotFoundError(path)
    before=json.loads(previous.stdout)
    after=json.loads(path.read_text())
    # Alternative candidates do not change the selected observation.
    if path.name=='current_surface_temperature.json':
        before=before.get('selected',{})
        after=after.get('selected',{})
    return fingerprint(before)!=fingerprint(after)

if __name__=='__main__':
    raise SystemExit(0 if changed(sys.argv[1]) else 1)
