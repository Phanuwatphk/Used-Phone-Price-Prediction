"""Launch the local browser form from any working directory."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description='เปิดฟอร์มประเมินราคามือถือในเครื่องนี้')
    parser.add_argument('--port', type=int, default=8501, help='พอร์ต local (ค่าเริ่มต้น 8501)')
    parser.add_argument('--headless', action='store_true', help='เปิดเซิร์ฟเวอร์โดยไม่เปิดเบราว์เซอร์อัตโนมัติ')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    command = [sys.executable, '-m', 'streamlit', 'run', str(Path(__file__).with_name('app.py')),
               '--server.address', '127.0.0.1', '--server.port', str(args.port),
               '--browser.gatherUsageStats', 'false', '--server.headless', str(args.headless).lower()]
    print(f'เปิด http://localhost:{args.port} เพื่อใช้งาน กด Ctrl+C เพื่อหยุด', flush=True)
    try:
        return subprocess.call(command, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
