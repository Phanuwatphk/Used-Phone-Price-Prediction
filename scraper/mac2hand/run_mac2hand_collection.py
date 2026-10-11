"""Resume raw Mac2Hand details without preparing data or reviewing ENNXO."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = ROOT / 'data/raw/mac2hand_20261006T172805_252838_Asia-Bangkok'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=DEFAULT_RAW)
    args = parser.parse_args()
    raw = args.raw.resolve()
    manifest_path = raw / 'details/manifest.json'
    state_path = raw / 'collection_progress.json'
    log_path = raw / 'collection.log'
    state = {'started_at': datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
             'timezone': 'Asia/Bangkok', 'status': 'collecting', 'date_cutoff': None,
             'mode': 'raw_collection_only', 'wrapper_pid': os.getpid(),
             'total': json.loads((raw / 'mac2hand_summary.json').read_text())['records'],
             'log': str(log_path)}
    process = None

    def progress(**extra):
        manifest = json.loads(manifest_path.read_text())
        state.update(cached=len(manifest), ok=sum(e.get('status') == 'ok' for e in manifest.values()),
                     failed=sum(e.get('status') == 'failed' for e in manifest.values()),
                     updated_at=datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(), **extra)
        temp = state_path.with_suffix('.tmp')
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
        temp.replace(state_path)

    try:
        with log_path.open('a') as log:
            process = subprocess.Popen([sys.executable, '-u', '-B', str(Path(__file__).resolve().parent / 'collect_mac2hand.py'),
                                        '--resume', str(raw), '--details', '--all-dates', '--continue-on-error'],
                                       stdout=log, stderr=subprocess.STDOUT)
            progress(collector_pid=process.pid)
            while process.poll() is None:
                time.sleep(30)
                progress()
            if process.returncode:
                raise RuntimeError(f'Collector exited {process.returncode}; inspect {log_path}')
        progress(status='collection_finished_with_failures' if state['failed'] else 'collection_finished')
    except BaseException as error:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        progress(status='stopped' if isinstance(error, KeyboardInterrupt) else 'failed', error=str(error))
        raise


if __name__ == '__main__':
    main()
