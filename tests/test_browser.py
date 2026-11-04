"""The app's screens in a real (headless) browser: every page opens without errors, and dialogs open once and close.

Runs the real app on a free port with its own home folder, connects to the demo cluster and clicks through as a
person would. Needs Playwright and its Chromium (`pip install -e ".[browser]"`, then `playwright install chromium`);
skipped without them.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SETTINGS = "Inputs and settings"


def _start_app(home):
    """The real app on a free port with its own home folder, as `everyome` starts it."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    env = dict(os.environ, HOME=str(home))
    p = subprocess.Popen([sys.executable, "-m", "everyome", "--no-browser", "--port", str(port)], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=1); break
        except OSError:
            time.sleep(0.5)
    else:
        p.kill(); raise AssertionError("the app did not start:\n" + p.stdout.read())
    return p, url


def _stop_app(p):
    p.terminate()
    try:
        p.wait(10)
    except subprocess.TimeoutExpired:  # Intent: a demo job or session may still be winding down; don't hang the suite.
        p.kill(); p.wait(10)


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    p, url = _start_app(tmp_path_factory.mktemp("home"))
    yield url
    _stop_app(p)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as pw:
        try:
            b = pw.chromium.launch()
        except Exception as e:  # Intent: Playwright installed but its browser not downloaded yet.
            pytest.skip(f"Chromium for Playwright is not installed ({e.__class__.__name__}); run: playwright install chromium")
        yield b
        b.close()


@pytest.fixture()
def page(app, browser):
    """A fresh tab on the app, connected to the demo cluster with a project; collects any JavaScript errors."""
    ctx = browser.new_context(base_url=app)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(f"page error: {e}"))
    pg.on("console", lambda m: pg.errors.append(f"console: {m.text}") if m.type == "error" else None)
    # Intent: a project of its own per test; connecting again closes the open project.
    for url, body in (("/api/connect", {"mode": "demo"}), ("/api/project/create", {"name": f"browser {uuid.uuid4().hex[:8]}"})):
        r = ctx.request.post(url, data=body)
        assert r.ok, r.text()
    pg.goto("/")
    pg.wait_for_selector("#page h1")
    yield pg
    ctx.close()


def title(pg):
    return pg.locator("#page h1").inner_text()


def side(pg, label):
    """Click a step in the left-hand list, as a person would, and wait for its page to be drawn."""
    pg.locator("#side button").filter(has_text=label).first.click()
    pg.locator("#side button[aria-current=page]").filter(has_text=label).wait_for()
    pg.wait_for_selector("#page h1")


def start_run(pg, module_id):
    side(pg, "Choose an analysis")
    pg.locator(f"[data-pick='{module_id}']").click()
    pg.wait_for_function("t => document.querySelector('#page h1')?.textContent === t", arg=SETTINGS)


def dialogs(pg):
    return pg.locator(".modal").count()


def test_every_module_page_opens_without_errors(page):
    modules = page.request.get("/api/modules").json()["modules"]
    assert len(modules) >= 10
    for m in modules:
        start_run(page, m["id"])
        side(page, "Choose an analysis")
        page.locator(f"[data-man='{m['id']}']").click()
        page.wait_for_selector("#page h1")
        if m.get("playground"):
            side(page, "Choose an analysis")
            page.locator(f"[data-go='playground:{m['id']}']").click()
            page.wait_for_selector("#page h1")
            page.wait_for_timeout(300)  # Intent: let the playground's first toy analysis run.
    for label in ("Home", "Connect", "Project", SETTINGS):
        side(page, label)
    page.wait_for_timeout(300)
    assert page.errors == []


def test_browse_dialog_opens_once_and_closes(page):
    """The bug in 0.1.0a2: after N visits to the settings page, one Browse click opened N dialogs."""
    start_run(page, "tutorial.sequence_summary")
    for _ in range(3):  # Intent: leave and come back, as people do.
        side(page, "Choose an analysis")
        side(page, SETTINGS)
    field = page.locator("[name=fasta]")
    browse = page.locator("[data-browse=fasta]")

    browse.click(); page.wait_for_selector("#blist li")
    assert dialogs(page) == 1
    page.locator("#bcancel").click()
    assert dialogs(page) == 0

    browse.click(); page.wait_for_selector("#blist li")
    folder = page.locator("#bpath").input_value()
    page.locator("#bpath").fill(folder.rsplit("/", 1)[0])
    page.locator("#bgo").click()
    page.wait_for_selector("#blist li[data-name='tutorial.sequence_summary']")
    assert dialogs(page) == 1                                     # Go moves within the same dialog
    page.locator("#blist li[data-name='tutorial.sequence_summary']").click()
    page.locator("#blist li[data-name='sequences.fasta']").click()
    page.locator("#bok").click()
    assert dialogs(page) == 0
    assert field.input_value().endswith("tutorial.sequence_summary/sequences.fasta")

    browse.click(); page.wait_for_selector("#blist li")
    page.keyboard.press("Escape")
    assert dialogs(page) == 0
    assert page.errors == []


def test_submit_dialog_cancel_submits_nothing(page):
    """Jobs run only when the person confirms; Cancel must close the dialog and submit nothing."""
    start_run(page, "tutorial.sequence_summary")
    with page.expect_response("**/api/run/create") as created:
        page.locator("#save").click()
    assert created.value.ok
    side(page, "Run on the cluster")
    page.locator("#runall").click()
    page.wait_for_selector(".modal")
    assert dialogs(page) == 1
    page.locator(".modal button", has_text="Cancel").click()
    assert dialogs(page) == 0
    assert page.request.get("/api/state").json()["run"]["jobs"] == {}
    assert page.errors == []


def test_quit_asks_first_and_cancel_keeps_it_running(page):
    page.locator("#quit").click()
    page.wait_for_selector(".modal")
    page.locator(".modal button", has_text="Cancel").click()
    assert dialogs(page) == 0
    assert page.request.get("/api/health").ok
    assert page.errors == []


def test_quit_stops_the_app(browser, tmp_path):
    """Started from the icon there is no terminal; Quit in the app is how people stop it."""
    p, url = _start_app(tmp_path)
    try:
        ctx = browser.new_context(base_url=url)
        pg = ctx.new_page()
        pg.goto("/")
        pg.wait_for_selector("#page h1")
        pg.locator("#quit").click()
        pg.locator(".modal button", has_text="Quit Everyome").click()
        pg.wait_for_selector("text=Everyome has stopped")
        assert p.wait(15) == 0
        ctx.close()
    finally:
        if p.poll() is None:
            _stop_app(p)
