from playwright.sync_api import sync_playwright
from urllib.parse import urljoin, urlparse
import time

from .dom_fingerprint import compute_dom_fingerprint
from .page_classifier import classify_page
from .screenshot_manager import get_screenshot_path
from .js_helper import GET_SELECTOR_JS
from .model_handler import dismiss_overlays
from .interaction_discover import discover_interactions
from .auth_handler import find_login_form, attempt_login

from .diagnostics_collector import attach_diagnostics, detach_diagnostics
from .expandable_handler import expand_collapsed_content
from .scroll_handler import smart_scroll

class SiteMap:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.pages = {}
        self.api_endpoints = set()
        self.visited = set()          # {(url, auth_state)}
        self.navigation_graph = {}
        self.state_graph = {}
        self.fingerprint_index = {}   # fingerprint -> canonical page key
        self.login_forms_found = []   # [(url, form_dict)]

    @staticmethod
    def page_key(url: str, auth_state: str) -> str:
        return f"{auth_state}::{url}"

    @staticmethod
    def state_key(url: str, auth_state: str, dom_fingerprint: str) -> str:
        """A state is a unique (url, auth, DOM-shape) combination -- so a
        modal-open and modal-closed view of the same URL count as distinct
        states, capturing SPA behavior a pure URL graph misses."""
        return f"{auth_state}::{url}::{dom_fingerprint[:12]}"

    def add_navigation(self, from_key: str, to_key: str):
        self.navigation_graph.setdefault(from_key, [])
        if to_key not in self.navigation_graph[from_key]:
            self.navigation_graph[from_key].append(to_key)

    def add_state_transition(self, from_state: str, to_state: str):
        self.state_graph.setdefault(from_state, [])
        if to_state not in self.state_graph[from_state]:
            self.state_graph[from_state].append(to_state)

    def add_page(self, url: str, auth_state: str, data: dict, fingerprint: str) -> str:
        key = self.page_key(url, auth_state)
        if fingerprint in self.fingerprint_index:
            data["template_of"] = self.fingerprint_index[fingerprint]
        else:
            self.fingerprint_index[fingerprint] = key
        self.pages[key] = data
        return key

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "navigation_graph": self.navigation_graph,
            "state_graph": self.state_graph,
            "pages": self.pages,
            "api_endpoints": list(self.api_endpoints),
            "login_forms_found": [{"url": u, "form": f} for u, f in self.login_forms_found],
        }


def is_same_origin(url: str, base_domain: str) -> bool:
    try:
        return urlparse(url).netloc == base_domain
    except Exception:
        return False


def _wait_for_spa_ready(page, max_wait_ms: int = 8000, stable_checks: int = 3, idle_threshold_ms: int = 500):
    """
    Waits for both DOM text stability AND network idle before considering
    a page ready. SPAs often finish rendering visually before their data
    fetches complete, or vice versa -- checking both catches more cases
    than either alone.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=idle_threshold_ms * 10)
    except Exception:
        pass  # networkidle can time out on pages with polling/websockets - don't block on it

    last_len, stable_count, elapsed, interval = -1, 0, 0, 500
    while elapsed < max_wait_ms:
        page.wait_for_timeout(interval)
        elapsed += interval
        try:
            current_len = page.evaluate("document.body.innerText.length")
        except Exception:
            current_len = last_len
        if current_len == last_len and current_len > 0:
            stable_count += 1
            if stable_count >= stable_checks:
                return
        else:
            stable_count = 0
        last_len = current_len


EXTRACT_JS = """
(baseDomain) => {
    """ + GET_SELECTOR_JS + """

    const findLabel = (inputEl) => {
        if (!inputEl.id) return "";
        const label = document.querySelector(`label[for="${CSS.escape(inputEl.id)}"]`);
        return label ? label.innerText.trim() : "";
    };

    const forms = [];
    document.querySelectorAll("form").forEach(form => {
        const fields = [];
        form.querySelectorAll("input, textarea, select").forEach(inp => {
            fields.push({
                name: inp.getAttribute("name") || "",
                type: inp.getAttribute("type") || inp.tagName.toLowerCase(),
                label: findLabel(inp),
                placeholder: inp.getAttribute("placeholder") || "",
                required: inp.hasAttribute("required"),
                selector: getSelector(inp)
            });
        });
        const submitBtn = form.querySelector("button[type=submit], input[type=submit]") ||
                           form.querySelector("button");
        forms.push({
            action: form.getAttribute("action") || "",
            method: (form.getAttribute("method") || "GET").toUpperCase(),
            fields: fields,
            submit_button_text: submitBtn ? (submitBtn.innerText || submitBtn.value || "").trim() : "",
            submit_selector: submitBtn ? getSelector(submitBtn) : null
        });
    });

    const buttons = [];
    const seenSelectors = new Set();
    document.querySelectorAll(
        "button, input[type=button], input[type=submit], a, [role=button], [onclick], [class*='btn'], [class*='button']"
    ).forEach(el => {
        const text = (el.innerText || el.value || el.getAttribute("aria-label") || "").trim();
        if (!text || text.length > 60) return;
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const style = window.getComputedStyle(el);
        const isClickable = style.cursor === "pointer" || el.tagName === "BUTTON" ||
                             el.hasAttribute("onclick") || el.getAttribute("role") === "button" ||
                             (el.tagName === "A" && el.hasAttribute("href"));
        if (!isClickable) return;
        const sel = getSelector(el);
        if (seenSelectors.has(sel)) return;
        seenSelectors.add(sel);
        const href = el.tagName === "A" ? el.getAttribute("href") : null;
        buttons.push({ text, selector: sel, tag: el.tagName.toLowerCase(), href });
    });

    const links = [];
    const anchors = [];
    document.querySelectorAll("a[href]").forEach(a => {
        const href = a.getAttribute("href");
        if (!href || href.startsWith("javascript:") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
        if (href.startsWith("#")) {
            const text = a.innerText.trim();
            if (text) anchors.push({ text, target: href, selector: getSelector(a) });
            return;
        }
        try {
            const fullUrl = new URL(href, window.location.href);
            if (fullUrl.host === baseDomain) {
                const cleanUrl = fullUrl.href.split('#')[0];
                if (!links.includes(cleanUrl)) links.push(cleanUrl);
            }
        } catch (e) {}
    });

    const headings = Array.from(document.querySelectorAll("h1, h2, h3")).map(h => h.innerText.trim());
    return { title: document.title, headings, forms, buttons, links, anchors };
}
"""


def extract_page_data(page, base_domain: str) -> dict:
    return page.evaluate(EXTRACT_JS, base_domain)


def _crawl_phase(page, sitemap: SiteMap, seed: list, auth_state: str,
                  max_pages: int, timeout_seconds: int, screenshot_dir: str,
                  start_time: float, run_interactions: bool):
    """
    Runs BFS over `seed` tagged with `auth_state`, mutating `sitemap` in
    place. Shared across the anonymous and authenticated passes so both can
    reuse the same page/context (and therefore session cookies).
    """
    local_queue = list(seed)
    queued_urls = {u for u, _ in seed}
    pages_this_phase = 0

    while local_queue and len(sitemap.visited) < max_pages and pages_this_phase < max_pages:
        if time.time() - start_time > timeout_seconds:
            break

        url, referrer = local_queue.pop(0)
        key = sitemap.page_key(url, auth_state)
        if key in sitemap.visited:
            if referrer:
                sitemap.add_navigation(sitemap.page_key(referrer, auth_state), key)
            continue

        page_record_shell = {}
        diag_handles = attach_diagnostics(page, page_record_shell)

        try:
            page.goto(url, wait_until="load", timeout=15000)
            _wait_for_spa_ready(page)
            dismiss_overlays(page)
            smart_scroll(page)
            expand_collapsed_content(page)
        except Exception as e:
            detach_diagnostics(page, diag_handles)
            sitemap.pages[key] = {"url": url, "auth_state": auth_state, "error": str(e), "reachable": False}
            sitemap.visited.add(key)
            pages_this_phase += 1
            continue

        sitemap.visited.add(key)
        if referrer:
            sitemap.add_navigation(sitemap.page_key(referrer, auth_state), key)

        try:
            page_data = extract_page_data(page, sitemap.base_domain)
            dom_fp = compute_dom_fingerprint(page.content())
            page_type = classify_page(url, page_data["title"], page_data)
            screenshot_path = get_screenshot_path(f"{auth_state}_{url}", screenshot_dir)
            page.screenshot(path=screenshot_path, full_page=True)

            login_form = find_login_form(page_data)
            if login_form:
                sitemap.login_forms_found.append((url, login_form))

            interaction_edges = []
            state_before = sitemap.state_key(url, auth_state, dom_fp)

            if run_interactions:
                interaction_edges = discover_interactions(page, url, sitemap.base_domain, page_data["buttons"])
                for edge in interaction_edges:
                    if edge["result_type"] == "state_change":
                        state_after = sitemap.state_key(url, auth_state, edge["result"])
                        sitemap.add_state_transition(state_before, state_after)
                    elif edge["result_type"] == "navigation" and edge["result"] not in queued_urls:
                        local_queue.append((edge["result"], url))
                        queued_urls.add(edge["result"])

            record = {
                "url": url,
                "auth_state": auth_state,
                "title": page_data["title"],
                "classification": page_type,
                "dom_fingerprint": dom_fp,
                "screenshot_path": screenshot_path,
                "headings": page_data["headings"],
                "forms": page_data["forms"],
                "buttons": page_data["buttons"],
                "anchors": page_data["anchors"],
                "interaction_edges": interaction_edges,
                "reachable": True,
                "console_errors": page_record_shell.get("console_errors", []),
                "console_warnings": page_record_shell.get("console_warnings", []),
                "failed_requests": page_record_shell.get("failed_requests", []),
            }
            detach_diagnostics(page, diag_handles)
            sitemap.add_page(url, auth_state, record, dom_fp)

            for link in page_data["links"]:
                if link not in queued_urls:
                    local_queue.append((link, url))
                    queued_urls.add(link)

        except Exception as e:
            detach_diagnostics(page, diag_handles)
            sitemap.pages[key] = {"url": url, "auth_state": auth_state,
                                   "error": f"Extraction failed: {str(e)}", "reachable": True}

        pages_this_phase += 1


def crawl(base_url: str, max_pages: int = 30, timeout_seconds: int = 120,
          screenshot_dir: str = "screenshots", run_interactions: bool = True,
          credentials: dict = None) -> dict:
    """
    credentials: optional {"username": ..., "password": ...} test account.
    When supplied, after the anonymous pass finds a login form, the crawler
    authenticates once and continues crawling in the same session, tagging
    every subsequent page auth_state="authenticated" -- that's how dashboards,
    account pages, and other gated routes get captured at all.
    """
    sitemap = SiteMap(base_url)
    start_time = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,args=["--disable-web-security", "--disable-features=IsolateOrigins,site-per-process"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.add_init_script("window.__aegisHadError=false; window.onerror=()=>{window.__aegisHadError=true;}")

        def on_request(request):
            try:
                if request.resource_type in ("xhr", "fetch") and is_same_origin(request.url, sitemap.base_domain):
                    sitemap.api_endpoints.add(f"{request.method} {request.url}")
            except Exception:
                pass

        page.on("request", on_request)

        # Phase 1: anonymous crawl
        _crawl_phase(
            page, sitemap, seed=[(base_url, None)], auth_state="anonymous",
            max_pages=max_pages, timeout_seconds=timeout_seconds,
            screenshot_dir=screenshot_dir, start_time=start_time,
            run_interactions=run_interactions,
        )

        # Phase 2: authenticate (if credentials given and a login form was found),
        # then keep crawling in the same session -- previously unreachable
        # gated pages now resolve normally.
        if credentials and sitemap.login_forms_found:
            login_url, login_form = sitemap.login_forms_found[0]
            try:
                page.goto(login_url, wait_until="load", timeout=15000)
                _wait_for_spa_ready(page)
                success = attempt_login(page, login_form, credentials.get("username"), credentials.get("password"))
            except Exception:
                success = False

            if success:
                post_login_url = page.url
                _crawl_phase(
                    page, sitemap, seed=[(post_login_url, None)], auth_state="authenticated",
                    max_pages=max_pages, timeout_seconds=timeout_seconds,
                    screenshot_dir=screenshot_dir, start_time=start_time,
                    run_interactions=run_interactions,
                )
            else:
                sitemap.pages["__login_attempt__"] = {
                    "auth_state": "authenticated", "reachable": False,
                    "error": "Login attempted but success could not be verified.",
                }

        browser.close()

    return sitemap.to_dict()