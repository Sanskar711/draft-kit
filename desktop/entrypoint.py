import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).parents[1]))


def main():
    # Windows windowed executables have no standard streams. Uvicorn logging
    # still inspects them; retain real pipes in the console worker.
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        import os
        for name, mode in (("stdin", "r"), ("stdout", "w"), ("stderr", "w")):
            if getattr(sys, name) is None:
                setattr(sys, name, open(os.devnull, mode, encoding="utf-8"))
    if len(sys.argv) > 1 and sys.argv[1] == "--resume-worker":
        from companion.resume_worker import main as worker
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        worker()
    elif "--self-test" in sys.argv:
        from desktop.self_test import main as test
        test()
    elif sys.platform == "win32":
        from desktop.windows_tray import main as tray
        tray()
    else:
        if sys.platform != "darwin":
            raise SystemExit("The menu-bar app requires macOS. For local development, run python -m companion.")
        from desktop.menubar import main as menu
        menu()


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    main()
