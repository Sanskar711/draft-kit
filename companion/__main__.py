import argparse
import os
from pathlib import Path

import uvicorn

from .app import Settings, create_app
from .storage import default_data_dir
from .process_lock import AlreadyRunning, ProcessLock


def main():
    parser = argparse.ArgumentParser(description="draft-kit local companion")
    parser.add_argument("--demo", action="store_true", help="Offline UI demo; no ChatGPT requests")
    parser.add_argument("--port", type=int, default=1455)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535.")
    data_dir = Path(os.environ.get("CAREER_COMPOSER_DATA_DIR", str(default_data_dir()))).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        guard = ProcessLock(data_dir / "process.lock")
    except AlreadyRunning as error:
        parser.error(str(error))
    with guard:
        serve(args, data_dir)


def serve(args, data_dir):
    try:
        app = create_app(Settings(data_dir, args.port, args.demo))
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    print("\ndraft-kit — " + ("OFFLINE DEMO" if args.demo else "ChatGPT plan connection"))
    print(f"Local address: http://127.0.0.1:{args.port}")
    print("Pairing code: " + app.state.pair_code)
    print("The code expires in 10 minutes. Paired extensions stay paired after restart.")
    print("Protected storage: " + app.state.vault.key_storage)
    print("Leave this terminal running. Press Ctrl+C to stop.\n", flush=True)
    # Callback URLs contain authorization codes: never enable access logging.
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning", workers=1)


if __name__ == "__main__":
    main()
