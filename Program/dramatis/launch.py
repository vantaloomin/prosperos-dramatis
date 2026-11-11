"""Start Dramatis on this computer: `python -m dramatis [--port N] [--no-browser] [--stub]`."""
import argparse
import threading
import webbrowser

import uvicorn

# Port 8815 keeps Dramatis clear of Study (8765), Companion (8775), Dungeon (8785), Worldsmith (8795) and Adventure
# (8805), so they can all run together.
PORT = 8815


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Start Prospero's Dramatis.")
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--stub', action='store_true',
                        help='answer every model call with a fixed reply, in a throwaway library (dramatis/stub.py)')
    args = parser.parse_args(argv)
    if args.stub:
        from dramatis import stub
        print(f'Stand-in model; the library is {stub.install()}.')
    url = f'http://127.0.0.1:{args.port}'
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, [url]).start()
    print(f"Prospero's Dramatis is running at {url}. Close this window to stop it.")
    uvicorn.run('dramatis.main:app', host='127.0.0.1', port=args.port, log_level='warning')
