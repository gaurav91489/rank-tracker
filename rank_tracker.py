from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
import csv
import time

# ── Constants ────────────────────────────────────────────────────────────────

# Each engine has a list of CSS selectors tried in order.
# If Google/Bing/DDG update their HTML, add the new selector at the front
# of the list without removing the old ones — older selectors act as fallbacks.
SEARCH_ENGINE_CONFIGS = {
    "google": {
        "url": "https://www.google.com",
        "selectors": [
            "div.yuRUbf a",
            "div.tF2Cxc a",
            "a[jsname='UWckNb']",
            "h3.LC20lb",
        ],
        "next_page_selectors": [
            "a#pnnext",
            "a[aria-label='Next']",
        ],
        "results_per_page": 10,
        "debug_file": "debug_google.html",
    },
    "bing": {
        "url": "https://www.bing.com",
        "selectors": [
            "li.b_algo h2 a",
            "#b_results .b_algo a",
            "h2 a[href]",
        ],
        "next_page_selectors": [
            "a.sb_pagN",
            "a[aria-label='Next page']",
        ],
        "results_per_page": 10,
        "debug_file": "debug_bing.html",
    },
    "duckduckgo": {
        "url": "https://duckduckgo.com",
        "selectors": [
            "a[data-testid='result-title-a']",
            "article[data-testid='result'] a[href]",
            "h2 a[href]",
        ],
        # DDG uses infinite scroll — clicking "More Results" loads the next batch
        "next_page_selectors": [
            "button#more-results",
            "button[data-testid='more-results']",
        ],
        "results_per_page": 10,
        "debug_file": "debug_ddg.html",
    },
}

WAIT_TIMEOUT = 15
MAX_PAGES = 5


# ── Driver setup ─────────────────────────────────────────────────────────────

def init_driver() -> webdriver.Chrome:
    """Prompt the user for a browser and return an initialised WebDriver."""
    while True:
        choice = input("Run script in Chrome or Firefox? ").lower().strip()
        if choice == "chrome":
            return webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        print("Please choose Chrome for now.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_domain(url: str) -> str:
    """Return the bare domain (no scheme, no www) for a given URL."""
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.removeprefix("www.")
    except Exception:
        return url.lower()


def clean_domain(raw: str) -> str:
    """Strip common prefixes from a user-supplied domain string."""
    for prefix in ("http://", "https://", "www."):
        raw = raw.replace(prefix, "")
    return raw.lower().strip()


def do_search(driver: webdriver.Chrome, url: str, phrase: str) -> None:
    """Navigate to *url* and submit *phrase* in the search box."""
    driver.get(url)
    box = driver.find_element(By.NAME, "q")
    box.clear()
    box.send_keys(phrase)
    box.send_keys(Keys.RETURN)


# ── Core logic ────────────────────────────────────────────────────────────────

def resolve_links(driver: webdriver.Chrome, selectors: list[str]) -> list | None:
    """
    Try each CSS selector in *selectors* in order.
    Return the first non-empty list of elements found, or None if all fail.
    The first selector is also used as the WebDriverWait target so we only
    block once; remaining selectors are tried immediately after.
    """
    # Wait for the page to have *any* of our known selectors present
    for selector in selectors:
        try:
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                return elements
        except Exception:
            continue  # selector not found — try the next one
    return None


def go_to_next_page(driver: webdriver.Chrome, next_page_selectors: list[str]) -> bool:
    """
    Click the next-page button using the first matching selector.
    Returns True if navigation succeeded, False if no button was found.
    """
    for selector in next_page_selectors:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, selector)
            btn.click()
            time.sleep(2)  # allow next page to begin loading
            return True
        except Exception:
            continue
    return False


def get_rank(
    driver: webdriver.Chrome,
    engine_name: str,
    config: dict,
    phrase: str,
    target_domain: str,
) -> int | str:
    """
    Search *phrase* on the given engine and return the 1-based rank of the
    first result whose domain contains *target_domain*, checking up to
    MAX_PAGES pages before returning "not found".
    Rank is absolute across pages (e.g. result #3 on page 2 = rank 13).
    """
    do_search(driver, config["url"], phrase)
    results_per_page = config.get("results_per_page", 10)

    for page in range(1, MAX_PAGES + 1):
        links = resolve_links(driver, config["selectors"])

        if links is None:
            print(f"[{engine_name}] No selectors matched on page {page} for '{phrase}' — saving debug HTML.")
            with open(config["debug_file"], "w", encoding="utf-8") as fh:
                fh.write(driver.page_source)
            return "not found"

        # Rank offset so page 2 starts at 11, page 3 at 21, etc.
        page_offset = (page - 1) * results_per_page

        for page_rank, link in enumerate(links, start=1):
            href = link.get_attribute("href") or ""
            if target_domain in normalize_domain(href):
                absolute_rank = page_offset + page_rank
                print(f"[{engine_name}] '{phrase}' found at rank {absolute_rank} (page {page})")
                return absolute_rank

        print(f"[{engine_name}] '{phrase}' not on page {page} — trying next page...")

        if page < MAX_PAGES:
            navigated = go_to_next_page(driver, config["next_page_selectors"])
            if not navigated:
                print(f"[{engine_name}] Could not find next-page button after page {page}.")
                break

    print(f"[{engine_name}] '{phrase}' not found in first {MAX_PAGES} pages.")
    return "not found"


def run_tracker(
    driver: webdriver.Chrome,
    engines: list[str],
    phrases: list[str],
    target_domain: str,
) -> dict[str, list[dict]]:
    """Return a nested dict: {engine_name: [{phrase: rank}, ...]}."""
    results: dict[str, list[dict]] = {}

    for engine in engines:
        engine_key = engine.lower().strip()
        config = SEARCH_ENGINE_CONFIGS.get(engine_key)

        if config is None:
            print(f"'{engine}' is not a supported search engine — skipping.")
            continue

        engine_results = [
            {phrase: get_rank(driver, engine_key.title(), config, phrase, target_domain)}
            for phrase in phrases
        ]
        results[engine_key.title()] = engine_results

    return results


# ── Output ────────────────────────────────────────────────────────────────────

def save_results(results: dict[str, list[dict]], phrases: list[str]) -> str:
    """Write results to a timestamped CSV and return the filename."""
    filename = f"{int(time.time())}.csv"

    with open(filename, "w", newline="") as fh:
        writer = csv.writer(fh)
        for engine, engine_results in results.items():
            writer.writerow([engine])
            for i, result in enumerate(engine_results):
                writer.writerow([phrases[i], result[phrases[i]]])

    return filename


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    driver = init_driver()

    engines = input(
        "Enter desired search engines, separated by commas (Google, Bing, DuckDuckGo): "
    ).split(",")

    phrases = [
        p.strip()
        for p in input(
            "Enter desired search terms or phrases, separated by commas: "
        ).split(",")
    ]

    target_domain = clean_domain(input("Enter domain to match: "))

    try:
        results = run_tracker(driver, engines, phrases, target_domain)
        filename = save_results(results, phrases)
        print("Results saved to:", filename)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()