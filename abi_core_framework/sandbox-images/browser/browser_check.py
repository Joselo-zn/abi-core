"""Open a web deliverable in headless Chromium and report what breaks.

Runs inside the sandbox: `python /opt/abi-sandbox/browser_check.py index.html`,
in /workspace, with the deliverable's files. Serves them on loopback, opens the
page, waits, presses the visible buttons, simulates a click, Space and the
arrows, and keeps watching. Leaves in .result.json the uncaught JavaScript
errors (each with its phase: "load" before the simulated input, "interaction"
after), the local files that don't exist and the external resources the page
asked for (refused: no network here).

An exit code other than 0 with no result means the check itself failed, which
says nothing about the page.
"""

import functools
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

RESULT_FILE = ".result.json"
LOAD_TIMEOUT_MS = 20_000
SETTLE_MS = 3_000
KEYS = ("Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight")
# What a person would press first ("Start"): visible buttons, in page order.
BUTTONS = "button:visible, input[type=button]:visible, input[type=submit]:visible, [role=button]:visible"
MAX_BUTTONS = 5
BUTTON_TIMEOUT_MS = 1_000
# Sandboxed already, with no user namespaces to give Chromium its own.
CHROMIUM_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
# Browsers ask for it on their own: no page breaks without one.
IGNORED_MISSING = {"favicon.ico"}


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _serve() -> ThreadingHTTPServer:
    handler = functools.partial(_Quiet, directory=".")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def check(entry: str) -> dict:
    server = _serve()
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    result = {"js_errors": [], "missing": [], "external": [], "load_timeout": False, "crashed": False}
    phase = {"now": "load"}

    def local(url: str) -> bool:
        return url.startswith(origin + "/") or url == origin

    def on_route(route):
        url = route.request.url
        if local(url) or urlparse(url).scheme in ("data", "blob"):
            route.continue_()
        else:
            result["external"].append(url)
            route.abort()

    def on_response(response):
        path = response.url[len(origin) + 1:].split("?")[0]
        if local(response.url) and response.status == 404 and path not in IGNORED_MISSING:
            result["missing"].append(path)

    def on_page_error(error):
        stack = (error.stack or "").replace(origin + "/", "")
        result["js_errors"].append({"message": error.message, "stack": stack, "phase": phase["now"]})

    def on_websocket(socket):
        if urlparse(socket.url).hostname != "127.0.0.1":
            result["external"].append(socket.url)

    def on_crash(_page):
        result["crashed"] = True

    with sync_playwright() as p:
        browser = p.chromium.launch(args=CHROMIUM_ARGS)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.route("**/*", on_route)
        page.on("response", on_response)
        page.on("pageerror", on_page_error)
        page.on("websocket", on_websocket)
        page.on("crash", on_crash)
        page.on("dialog", lambda dialog: dialog.dismiss())
        try:
            page.goto(f"{origin}/{entry}", wait_until="load", timeout=LOAD_TIMEOUT_MS)
        except PlaywrightError:
            result["load_timeout"] = True
        try:
            page.wait_for_timeout(SETTLE_MS)
            phase["now"] = "interaction"
            for button in page.locator(BUTTONS).all()[:MAX_BUTTONS]:
                try:
                    if button.is_visible():
                        button.click(timeout=BUTTON_TIMEOUT_MS)
                        page.wait_for_timeout(500)
                except PlaywrightError:
                    # Covered, disabled or gone after an earlier press.
                    pass
            page.mouse.click(640, 360)
            for key in KEYS:
                page.keyboard.press(key)
                page.wait_for_timeout(200)
            page.wait_for_timeout(SETTLE_MS)
        except PlaywrightError:
            # The page went away under the simulated input.
            pass
        browser.close()
    server.shutdown()
    return result


if __name__ == "__main__":
    report = check(sys.argv[1])
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f)
