"""Exercise the calculator through a real browser; fail on any broken result."""

import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


html = Path(os.environ.get("CALCULATOR_HTML", "index.html")).resolve()
if not html.is_file():
    raise FileNotFoundError(html)

handler = partial(QuietHandler, directory=str(html.parent))
server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
Thread(target=server.serve_forever, daemon=True).start()

try:
    with sync_playwright() as playwright:
        browser_options = {"headless": True}
        if executable_path := os.environ.get("CHROMIUM_EXECUTABLE"):
            browser_options["executable_path"] = executable_path
        browser = playwright.chromium.launch(**browser_options)
        try:
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(f"http://127.0.0.1:{server.server_port}/{html.name}")
            assert response is not None and response.status == 200

            first = page.get_by_label("첫 번째 숫자")
            second = page.get_by_label("두 번째 숫자")
            button = page.get_by_role("button", name="계산하기")
            for a, b, expected in (("10", "20", "30"), ("-4", "1.5", "-2.5"), ("0.1", "0.2", "0.3")):
                first.fill(a)
                second.fill(b)
                button.click()
                actual = page.locator("#answer").inner_text()
                assert actual == expected, f"{a} + {b}: expected {expected}, got {actual}"

            first.fill("")
            button.click()
            assert not first.evaluate("element => element.validity.valid")
            assert page.locator("#answer").inner_text() == "0.3"
            assert not errors, errors
            print("Calculator browser checks passed")
        finally:
            browser.close()
finally:
    server.shutdown()
