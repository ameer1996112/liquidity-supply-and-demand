"""
TradingView Strategy Tester — Automated CSV Export

Opens a TradingView chart in the browser, ensures the Strategy Tester is visible,
switches to the "List of Trades" tab, clicks Download, and saves the CSV to a
chosen directory. Use this after updating your Pine script to pull a fresh export
without manual clicking.

Prerequisites:
  - pip install selenium webdriver-manager
  - Chrome or Chromium installed
  - TradingView account (Pro/Plus may be required for export)
  - Chart URL must have your strategy already applied and backtest range set
  - For your own chart layouts: use --chrome-profile. First run: a Chrome window
    opens; log in to TradingView when prompted. Later runs reuse that profile.

Usage:
  # Export from default chart URL, save to current directory
  python apps/ml/export_tv_backtest.py --url "https://www.tradingview.com/chart/YOUR_CHART_ID/"

  # Custom download folder and wait longer for backtest
  python apps/ml/export_tv_backtest.py --url "https://www.tradingview.com/chart/..." --output-dir ./exports --wait-backtest 120

  # REQUIRED for private charts: use dedicated profile (log in to TradingView on first run).
  python apps/ml/export_tv_backtest.py --url "..." --chrome-profile -o ./exports

  # Set backtest date range (1 Jan 2023 – 28 Feb 2026) and export multiple pairs
  python apps/ml/export_tv_backtest.py --url "..." --chrome-profile -o ./exports --from-date 2023-01-01 --to-date 2026-02-28 --symbols USDJPY,EURUSD,GBPUSD

  # Headless (no visible browser) — may fail if TradingView blocks headless
  python apps/ml/export_tv_backtest.py --url "..." --headless
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# Default chart URL — replace with your own chart that has SND_Strategy applied
DEFAULT_CHART_URL = "https://www.tradingview.com/chart/"

# Selectors — TradingView's DOM changes; adjust if export fails
# TradingView uses a bottom panel: "Strategy Report" opens it; tabs include "List of Trades"
SELECTORS = {
    "strategy_report_button": [
        "//*[contains(text(), 'Strategy Report')]",
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'strategy report')]",
        "//*[contains(., 'Strategy Report')]",
        "//span[contains(text(), 'Strategy Tester')]",
        "//*[contains(@class, 'strategy-tester') or contains(@class, 'backtesting') or contains(@class, 'report')]",
    ],
    "list_of_trades_tab": [
        "//*[contains(text(), 'List of Trades')]",
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'list of trades')]",
        "//span[contains(text(), 'List of Trades')]",
        "//*[@role='tab' and contains(., 'List of Trades')]",
        "//*[contains(@class, 'tab') and contains(., 'List of Trades')]",
    ],
    "download_button": [
        "//*[contains(., 'Download') and (self::button or self::a or self::span)]",
        "//button[contains(., 'Download')]",
        "//*[@aria-label and contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]",
        "//a[contains(., 'Download')]",
        "//*[contains(@class, 'download') and (self::button or self::a)]",
        "//*[@title='Download' or @data-title='Download']",
        "//*[contains(@class, 'export') or contains(@class, 'save')]",
    ],
    # Date range in Strategy Report (e.g. "Nov 17, 2025 – Feb 27, 2026"); click to open dropdown
    "date_range_trigger": [
        "//button[contains(., '2025') and contains(., '2026')]",
        "//*[@role='button' and contains(., '2025') and contains(., '2026')]",
        "//*[contains(@class, 'button') and contains(., '2025')]",
        "//*[contains(., '–') and contains(., '202')]",
        "//*[contains(., '—') and contains(., '202')]",
        "//*[contains(., ' - ') and contains(., '202')]",
        "//*[contains(@class, 'date') and contains(., '202')]",
    ],
    # In the date dropdown: "Custom date range..." opens the "Backtesting dates" modal
    "custom_date_range_option": [
        "//*[contains(text(), 'Custom date range')]",
        "//*[contains(., 'Custom date range')]",
    ],
    # In "Backtesting dates" modal: confirm button (inputs expect YYYY-MM-DD)
    "date_modal_select_button": [
        "//*[contains(text(), 'Select') and contains(@class, 'button')]",
        "//button[contains(., 'Select') and not(contains(., 'first available'))]",
        "//*[contains(., 'Backtesting dates')]//*[contains(., 'Select') and not(contains(., 'first'))]",
    ],
    # Symbol search at top of chart
    "symbol_search": [
        "//input[contains(@placeholder, 'Search') or contains(@placeholder, 'Symbol') or contains(@aria-label, 'Symbol')]",
        "//*[contains(@class, 'symbol') and contains(@class, 'search')]//input",
        "//*[@role='combobox' and contains(@aria-label, 'Symbol')]",
    ],
}


def _find_element(driver, xpaths, timeout=15):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    wait = WebDriverWait(driver, timeout)
    for xpath in xpaths:
        try:
            el = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            if el:
                return el
        except Exception:
            continue
    return None


def _set_date_range(driver, from_date: str, to_date: str, output_dir: Path | None = None) -> bool:
    """Click date range → Custom date range... → fill from/to. from_date/to_date: 2023-01-01, 2026-02-28."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    def _screenshot(name: str) -> None:
        if output_dir:
            try:
                path = Path(output_dir) / f"tv_date_debug_{name}.png"
                driver.save_screenshot(str(path))
                log.info("Screenshot: %s", path)
            except Exception:
                pass

    try:
        driver.switch_to.default_content()
        time.sleep(0.5)

        trigger = _find_element(driver, SELECTORS["date_range_trigger"], timeout=10)
        if not trigger:
            log.warning("Date range trigger not found (element showing current range).")
            return False
        log.info("Date range trigger found, clicking...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger)
        time.sleep(0.5)
        trigger.click()
        time.sleep(2)

        custom_opt = _find_element(driver, SELECTORS["custom_date_range_option"], timeout=8)
        if not custom_opt:
            log.warning("'Custom date range...' option not found in dropdown.")
            _screenshot("after_trigger_click")
            return False
        log.info("Clicking Custom date range...")
        custom_opt.click()
        time.sleep(3)
        _screenshot("after_custom_date_click")

        # Modal inputs use YYYY-MM-DD; find dialog then inputs
        dialog = None
        for xpath in ["//*[contains(., 'Backtesting dates')]", "//*[contains(@class, 'dialog') or contains(@class, 'modal')]"]:
            try:
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed() and "Backtesting" in (el.text or ""):
                        dialog = el
                        break
                if dialog:
                    break
            except Exception:
                continue
        search_root = dialog if dialog else driver
        inputs = search_root.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='date'], input") if dialog else driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='date'], input")
        visible = [inp for inp in inputs if inp.is_displayed()]
        log.info("Found %d visible date inputs in modal.", len(visible))

        filled = 0
        for inp in visible[:3]:
            try:
                val = from_date if filled == 0 else to_date
                inp.click()
                time.sleep(0.3)
                inp.send_keys(Keys.CONTROL + "a")
                inp.send_keys(val)
                # React often needs JS value + event to update state
                driver.execute_script(
                    "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', { bubbles: true })); arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                    inp, val
                )
                filled += 1
                if filled >= 2:
                    break
                time.sleep(0.5)
            except Exception as e:
                log.debug("Input fill attempt: %s", e)
                continue
        if filled == 0:
            log.warning("Could not fill any date input.")
            return False
        log.info("Filled %d date field(s).", filled)
        time.sleep(1)

        select_btn = _find_element(driver, SELECTORS["date_modal_select_button"], timeout=6)
        if select_btn:
            try:
                driver.execute_script("arguments[0].click();", select_btn)
                time.sleep(2)
                log.info("Clicked Select.")
            except Exception:
                select_btn.click()
                time.sleep(2)
        else:
            log.warning("Select button not found, sending Enter.")
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            time.sleep(2)
        return True
    except Exception as e:
        log.warning("Could not set date range: %s", e)
        _screenshot("error")
        return False


def _set_chart_symbol(driver, symbol: str) -> bool:
    """Change chart symbol via TradingView's '/' search shortcut."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        driver.switch_to.default_content()

        # Press Escape first to dismiss any open panels, then focus body
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ESCAPE)
        time.sleep(0.5)
        body.click()
        time.sleep(0.3)

        # Press "/" — TradingView's universal symbol search shortcut
        body.send_keys("/")
        time.sleep(1.5)

        # The search popup input appears — find it
        search_input = None
        for xpath in [
            "//input[contains(@class,'search') and @type='text']",
            "//div[contains(@class,'searchBar') or contains(@class,'search-bar')]//input",
            "//input[@placeholder]",
            "//input[@data-role='search']",
        ]:
            try:
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed() and el.is_enabled():
                        search_input = el
                        break
                if search_input:
                    break
            except Exception:
                continue

        if not search_input:
            log.warning("Symbol search input not found after '/' — trying click on ticker text")
            # Fallback: click the symbol name text in the top-left legend
            for xpath in [
                "//*[contains(@class,'pane-legend') or contains(@class,'legend')]//span[1]",
                "//*[contains(@class,'symbol-edit')]",
                "//div[contains(@class,'chart-toolbar')]//span[contains(@class,'symbol')]",
            ]:
                try:
                    el = driver.find_element(By.XPATH, xpath)
                    if el.is_displayed():
                        el.click()
                        time.sleep(1.5)
                        # Now look for the search input again
                        for s_xpath in ["//input[@placeholder]", "//input[contains(@class,'search')]"]:
                            els = driver.find_elements(By.XPATH, s_xpath)
                            for inp in els:
                                if inp.is_displayed() and inp.is_enabled():
                                    search_input = inp
                                    break
                            if search_input:
                                break
                        break
                except Exception:
                    continue

        if not search_input:
            log.warning("Could not open symbol search for %s", symbol)
            return False

        # Clear and type symbol
        search_input.send_keys(Keys.CONTROL + "a")
        search_input.send_keys(Keys.DELETE)
        time.sleep(0.2)
        search_input.send_keys(symbol)
        log.info("Typed symbol '%s' into search", symbol)
        time.sleep(2.5)

        # Click the best matching result — prefer exact symbol name match
        result = None
        for xpath in [
            # Exact ticker match in search results
            f"//span[translate(text(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ')='{symbol.upper()}']/..",
            f"//em[text()='{symbol.upper()}']/..",
            f"//*[contains(@class,'item') or contains(@class,'row') or contains(@class,'result')][.//span[text()='{symbol.upper()}'] or .//em[text()='{symbol.upper()}']]",
            # Broader fallback
            f"//*[contains(@class,'item') or contains(@class,'result')][contains(.,'{symbol.upper()}')]",
        ]:
            try:
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed():
                        result = el
                        break
                if result:
                    break
            except Exception:
                continue

        if result:
            driver.execute_script("arguments[0].click();", result)
            log.info("Clicked result for %s", symbol)
        else:
            log.warning("No result found for %s — pressing Enter", symbol)
            search_input.send_keys(Keys.RETURN)

        time.sleep(3)
        return True

    except Exception as e:
        log.warning("Could not set symbol %s: %s", symbol, e)
        return False


def run_export(
    chart_url: str,
    output_dir: str | Path,
    headless: bool = False,
    chrome_profile: bool = False,
    wait_backtest_sec: float = 90,
    timeout_page_sec: int = 60,
    from_date: str | None = None,
    to_date: str | None = None,
    symbols: list[str] | None = None,
    pause_for_dates_sec: float = 0,
    exchange: str = "VANTAGE",
) -> list[Path]:
    """
    Open TradingView chart, optionally set date range and/or loop over symbols,
    open Strategy Tester → List of Trades, click Download. Returns list of paths to downloaded CSVs.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        log.error("Install: pip install selenium webdriver-manager")
        return None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    # Reduce "Chrome is being controlled by automated test software" and automation detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # Ensure downloads go to our folder
    prefs = {
        "download.default_directory": str(output_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)

    profile_dir = None
    if chrome_profile:
        # Use a dedicated profile dir so we don't lock the user's main Chrome.
        profile_dir = Path(__file__).resolve().parent / ".chrome_tv_export_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")
        log.info("Using dedicated profile: %s (log in to TradingView on first run)", profile_dir)

    if not chrome_profile:
        log.warning("Running without --chrome-profile. If the chart is private, TradingView will show 'We can't open this chart layout' — use --chrome-profile.")

    service = Service(ChromeDriverManager().install())

    def _launch(options_to_use):
        return webdriver.Chrome(service=service, options=options_to_use)

    try:
        driver = _launch(options)
    except Exception as e:
        session_failed = "session not created" in str(e).lower() or "chrome instance exited" in str(e).lower() or "cannot parse" in str(e).lower()
        if session_failed and chrome_profile:
            log.warning("Chrome failed with profile (often locked/corrupted). Retrying without profile — log in to TradingView when the browser opens.")
            # Retry without profile: rebuild options without user-data-dir
            options_no_profile = Options()
            options_no_profile.add_experimental_option("excludeSwitches", ["enable-automation"])
            options_no_profile.add_experimental_option("useAutomationExtension", False)
            options_no_profile.add_argument("--disable-blink-features=AutomationControlled")
            if headless:
                options_no_profile.add_argument("--headless=new")
            options_no_profile.add_argument("--no-sandbox")
            options_no_profile.add_argument("--disable-dev-shm-usage")
            options_no_profile.add_argument("--disable-gpu")
            options_no_profile.add_experimental_option("prefs", prefs)
            try:
                driver = _launch(options_no_profile)
            except Exception as e2:
                log.error(
                    "Chrome still failed. Try: 1) Close all Chrome windows. "
                    "2) Delete profile and retry: rm -rf apps/ml/.chrome_tv_export_profile "
                    "3) Run without --chrome-profile and log in when the browser opens."
                )
                raise e2
        else:
            if session_failed:
                log.error(
                    "Chrome session failed. Try: 1) Update Chrome to latest. "
                    "2) Delete profile if you use it: rm -rf apps/ml/.chrome_tv_export_profile "
                    "3) Run without --chrome-profile, then log in when the browser opens."
                )
            raise
    driver.set_page_load_timeout(timeout_page_sec)

    try:
        log.info("Opening chart: %s", chart_url[:80] + "..." if len(chart_url) > 80 else chart_url)
        driver.get(chart_url)

        log.info("Waiting for page to load...")
        time.sleep(8)

        # If Strategy Report isn't in main page, try chart iframe(s)
        report_btn = _find_element(driver, SELECTORS["strategy_report_button"], timeout=5)
        if not report_btn:
            try:
                from selenium.webdriver.common.by import By
                for iframe in driver.find_elements(By.XPATH, "//iframe")[:5]:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(iframe)
                    report_btn = _find_element(driver, SELECTORS["strategy_report_button"], timeout=3)
                    if report_btn:
                        log.info("Switched to chart iframe for Strategy Tester")
                        break
                if not report_btn:
                    driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()
                report_btn = None

        # Open Strategy Report / Strategy Tester panel (bottom toolbar or tab)
        report_btn = _find_element(driver, SELECTORS["strategy_report_button"], timeout=25)
        if report_btn:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", report_btn)
                time.sleep(0.5)
                report_btn.click()
                log.info("Opened Strategy Report / Strategy Tester panel")
                time.sleep(3)
            except Exception as e:
                log.warning("Could not click Strategy Report: %s", e)
        else:
            log.warning("Strategy Report button not found; panel may already be open")

        # Optional: set backtest date range (e.g. 2023-01-01 to 2026-02-28)
        if from_date and to_date:
            log.info("Setting date range: %s to %s", from_date, to_date)
            if _set_date_range(driver, from_date, to_date, output_dir):
                time.sleep(5)
            else:
                log.warning("Could not set date range automatically; set it manually in the Strategy Report if needed.")
            if pause_for_dates_sec > 0:
                log.info("Pausing %s seconds — set the date range manually in the Strategy Report, then wait for backtest to finish.", pause_for_dates_sec)
                time.sleep(pause_for_dates_sec)

        # Wait for backtest to finish (use full wait_backtest_sec — 3+ years can take 1–2 min)
        if wait_backtest_sec > 0:
            log.info("Waiting up to %.0fs for backtest to finish...", wait_backtest_sec)
            time.sleep(wait_backtest_sec)
        # Scroll so bottom panel is in view
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        symbols_list = symbols if symbols else [None]
        results: list[Path] = []

        for idx, symbol in enumerate(symbols_list):
            if symbol:
                log.info("Switching to symbol: %s", symbol)
                # Use URL navigation — most reliable; preserves chart layout + date range.
                # TradingView accepts ?symbol=EXCHANGE:TICKER on any saved chart URL.
                # If symbol already contains ":" (e.g. "FX:EURUSD"), use it as-is.
                full_symbol = symbol if ":" in symbol else f"{exchange}:{symbol}"
                sym_url = f"{chart_url.rstrip('/')}?symbol={full_symbol}"
                try:
                    log.info("Navigating to: %s", sym_url)
                    driver.get(sym_url)
                    time.sleep(10)  # wait for chart + strategy to reload
                except Exception as e:
                    log.error("URL navigation failed for %s: %s — skipping.", symbol, e)
                    continue
                log.info("Waiting %.0fs for backtest to recalculate on %s...", wait_backtest_sec, symbol)
                time.sleep(wait_backtest_sec)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

            # Click "List of Trades" tab
            list_tab = _find_element(driver, SELECTORS["list_of_trades_tab"], timeout=15)
            if list_tab:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", list_tab)
                    time.sleep(0.5)
                    list_tab.click()
                    time.sleep(2)
                except Exception as e:
                    log.warning("Could not click List of Trades: %s", e)

            # Click Download
            download_btn = _find_element(driver, SELECTORS["download_button"], timeout=15)
            if not download_btn:
                log.error("Download button not found.")
                if not results:
                    driver.save_screenshot(str(output_dir / "tv_export_debug.png"))
                continue

            existing = set(output_dir.glob("*.csv"))
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", download_btn)
                time.sleep(0.5)
                download_btn.click()
            except Exception as e:
                driver.execute_script("arguments[0].click();", download_btn)
            log.info("Download clicked for %s; waiting for file...", symbol or "chart")

            # Wait for new CSV
            out_file = None
            for _ in range(35):
                time.sleep(1)
                current = set(output_dir.glob("*.csv"))
                new_files = current - existing
                if new_files:
                    out_file = next(iter(new_files))
                    if out_file.suffix == ".csv":
                        break
                csvs = sorted(output_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
                if csvs and (time.time() - csvs[0].stat().st_mtime) < 8:
                    out_file = csvs[0]
                    break

            if out_file and out_file.suffix == ".csv":
                if symbol:
                    dest = output_dir / f"{symbol}_trades.csv"
                    try:
                        out_file.rename(dest)
                        out_file = dest
                    except Exception as e:
                        log.warning("Could not rename to %s: %s", dest, e)
                results.append(out_file)
                log.info("Saved: %s", out_file)
            else:
                log.warning("No new CSV for %s within 35s", symbol or "chart")

        if not results:
            driver.save_screenshot(str(output_dir / "tv_export_debug.png"))
        return results

    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automate TradingView Strategy Tester → List of Trades → Export CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_CHART_URL,
        help="Full TradingView chart URL (with strategy applied)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=".",
        help="Directory to save the exported CSV (default: current directory)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--chrome-profile",
        action="store_true",
        help="Use your default Chrome profile (stay logged in to TradingView)",
    )
    parser.add_argument(
        "--wait-backtest",
        type=float,
        default=90,
        help="Seconds to wait for backtest to finish (default: 90; use 120–180 for 3+ year backtests)",
    )
    parser.add_argument(
        "--pause-for-dates",
        type=float,
        default=0,
        metavar="SECONDS",
        help="If date range is set but auto-set failed: pause this many seconds so you can set dates manually and let backtest run (e.g. 120)",
    )
    parser.add_argument(
        "--timeout-page",
        type=int,
        default=60,
        help="Page load timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--from-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Backtest start date (e.g. 2023-01-01). Set in Strategy Report if possible.",
    )
    parser.add_argument(
        "--to-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Backtest end date (e.g. 2026-02-28). Set in Strategy Report if possible.",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        metavar="SYM1,SYM2,...",
        help="Comma-separated forex pairs to export (e.g. USDJPY,EURUSD,GBPUSD). Exports one CSV per symbol.",
    )
    parser.add_argument(
        "--exchange",
        default="VANTAGE",
        metavar="EXCHANGE",
        help="TradingView exchange prefix for symbol URL (default: VANTAGE). E.g. OANDA, FX, VANTAGE.",
    )
    args = parser.parse_args()

    if args.url == DEFAULT_CHART_URL:
        log.error("Provide your chart URL with --url (chart must have your strategy applied)")
        exit(1)

    symbols_list = None
    if args.symbols:
        symbols_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    results = run_export(
        chart_url=args.url,
        output_dir=args.output_dir,
        headless=args.headless,
        chrome_profile=args.chrome_profile,
        wait_backtest_sec=args.wait_backtest,
        timeout_page_sec=args.timeout_page,
        from_date=args.from_date,
        to_date=args.to_date,
        symbols=symbols_list,
        pause_for_dates_sec=args.pause_for_dates,
        exchange=args.exchange,
    )

    if results:
        log.info("Exported %s file(s). Next: ingest and retrain", len(results))
        for p in results:
            sym = p.stem.replace("_trades", "").upper()
            log.info("  python apps/ml/ingest_tv_export.py --csv %s --symbol %s", p, sym)
        log.info("  python apps/ml/train_v1.py")
    else:
        exit(1)


if __name__ == "__main__":
    main()
