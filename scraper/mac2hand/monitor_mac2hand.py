"""Read-only terminal monitor for the current Mac2Hand raw collection."""
import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_RAW = Path(__file__).resolve().parents[2] / 'data/raw/mac2hand_20261006T172805_252838_Asia-Bangkok'


def snapshot(raw):
    state = json.loads((raw / 'collection_progress.json').read_text())
    manifest = json.loads((raw / 'details/manifest.json').read_text())
    counts = Counter(entry.get('status') for entry in manifest.values())
    total, cached = state['total'], len(manifest)
    percent = cached / total * 100 if total else 0
    filled = min(30, int(percent * .3))
    pid = state.get('collector_pid')
    process = 'ไม่พบ PID จากระบบนี้; ดูเวลาและ log ประกอบ'
    try:
        command = (Path('/proc') / str(pid) / 'cmdline').read_bytes().replace(b'\0', b' ').decode()
        if 'collect_mac2hand.py' in command and str(raw) in command:
            process = 'กำลังรัน'
    except PermissionError:
        process = 'ไม่มีสิทธิ์ตรวจ process; ดูเวลาและ log ประกอบ'
    except FileNotFoundError:
        pass
    log = raw / 'collection.log'
    lines = log.read_text(errors='replace').splitlines() if log.exists() else []
    last = next((line for line in reversed(lines) if re.fullmatch(r'Details \d+ / \d+', line)), 'ยังไม่มีบันทึกจำนวนประมวลผล')
    now = datetime.now(ZoneInfo('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')
    return '\n'.join([
        f'Mac2Hand — {now} (เวลาไทย)',
        f'ตัวเก็บ: {process} | PID {pid} | สถานะที่บันทึก: {state["status"]}',
        f'[{"#" * filled}{"-" * (30 - filled)}] {percent:.1f}%',
        f'มีผลเก็บแล้ว: {cached:,} / {total:,} | ยังไม่มีผล: {max(0, total - cached):,}',
        f'อ่านสำเร็จ: {counts["ok"]:,} | ล้มเหลว: {counts["failed"]:,}',
        f'อัปเดตสถานะล่าสุด: {state["updated_at"]}',
        f'ประมวลผลรอบนี้ล่าสุด: {last}',
        '', 'ตัวเลขประมวลผลรอบนี้รวมการอ่าน cache เดิม จึงต่างจากจำนวนที่เก็บแล้ว',
        'Ctrl+C ปิด monitor เท่านั้น ตัวเก็บข้อมูลยังทำงานต่อ',
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=DEFAULT_RAW)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--interval', type=float, default=5)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error('--interval must be positive')
    try:
        while True:
            try:
                display = snapshot(args.raw.resolve())
            except (OSError, ValueError, KeyError) as error:
                display = f'ยังอ่านสถานะไม่ได้: {error}'
            if sys.stdout.isatty() and not args.once:
                print('\033[2J\033[H', end='')
            print(display, flush=True)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
