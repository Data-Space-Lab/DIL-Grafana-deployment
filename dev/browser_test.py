"""Run against the disposable compose fixture; never a production Grafana."""
import os
from playwright.sync_api import sync_playwright, expect

BASE_URL = os.getenv("GRAFANA_TEST_URL", "http://127.0.0.1:13000").rstrip("/")


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    # Fresh Grafana installations may display their first-login feature tour.
    page.add_locator_handler(page.get_by_role("dialog"), lambda dialog: dialog.press("Escape"))
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(BASE_URL + "/login")
    page.get_by_placeholder("email or username").fill("admin")
    page.get_by_placeholder("password", exact=True).fill("local-demo-only")
    page.get_by_role("button", name="Log in", exact=True).click()
    page.wait_for_url(BASE_URL + "/", timeout=30000)
    server = page.request.get(BASE_URL + "/api/health").json()
    health = page.request.get(BASE_URL + "/api/datasources/uid/dil-fixture/health")
    assert health.status == 200, health.text()
    assert health.json()["status"] == "OK", health.text()
    page.goto(BASE_URL + "/connections/datasources/edit/dil-fixture")
    expect(page.get_by_text("Consumer dataplane URL", exact=True)).to_be_visible(timeout=30000)
    page.get_by_role("button", name="Import shared dashboard", exact=True).click()
    link = page.get_by_role("link", name="Open imported dashboard", exact=True)
    expect(link).to_be_visible(timeout=30000)
    page.screenshot(path="/tmp/dil-grafana-config.png", full_page=True)
    link.click()
    expect(page.get_by_text("Temperature", exact=True).first).to_be_visible(timeout=30000)
    page.wait_for_timeout(3000)
    assert page.locator("canvas").count() > 0, "Grafana did not render a graph"
    page.screenshot(path="/tmp/dil-grafana-dashboard.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.get_by_text("Temperature", exact=True).first).to_be_visible(timeout=30000)
    expect(page.locator("canvas").first).to_be_visible(timeout=30000)
    page.wait_for_timeout(1500)
    page.screenshot(path="/tmp/dil-grafana-mobile.png", full_page=True)
    assert not errors, errors
    print(f"Grafana {server['version']}: plugin health OK, dashboard import and desktop/mobile frames OK")
    browser.close()
