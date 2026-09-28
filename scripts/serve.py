"""`python -m http.server`, but tells the browser not to cache, so edits show on reload."""

import sys
from http.server import SimpleHTTPRequestHandler, test


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


test(NoCache, port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
