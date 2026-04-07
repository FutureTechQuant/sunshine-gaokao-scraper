# scripts/gaokao_zyk.py
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://gaokao.chsi.com.cn/zyk/zybk/"


def dump_debug(page, output_dir: Path, name: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output_dir / f"{name}.png"), full_page=True)
    (output_dir / f"{name}.html").write_text(page.content(), encoding="utf-8")


def wait_for_real_page(page, timeout_ms=20000):
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    body_text = page.locator("body").inner_text(timeout=5000)

    # 只有出现真实业务文本，才继续
    real_markers = ["专业知识库", "本科", "搜索", "专业目录"]
    if any(x in body_text for x in real_markers):
        return True

    return False


def find_search_box(page):
    selectors = [
        'input[placeholder*="搜索"]',
        'input[placeholder*="专业"]',
        'input[type="search"]',
        'input.el-input__inner',
        'input',
    ]
    for selector in selectors:
        loc = page.locator(selector)
        if loc.count() > 0:
            for i in range(min(loc.count(), 5)):
                item = loc.nth(i)
                try:
                    if item.is_visible():
                        return item
                except Exception:
                    pass
    return None


def run(keyword="计算机科学与技术"):
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            ok = wait_for_real_page(page)
            dump_debug(page, output_dir, "01_after_open")

            if not ok:
                raise RuntimeError("未进入真实业务页，当前很可能是前置保护页。请检查 output/01_after_open.png 和 html。")

            search_box = find_search_box(page)
            if not search_box:
                dump_debug(page, output_dir, "02_no_search_box")
                raise RuntimeError("已进入页面，但仍未找到可见搜索框。请根据 artifact 调整选择器。")

            search_box.click()
            search_box.fill(keyword)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

            dump_debug(page, output_dir, "03_after_search")

            body_text = page.locator("body").inner_text()
            (output_dir / "result.txt").write_text(body_text[:8000], encoding="utf-8")

        except PlaywrightTimeoutError:
            dump_debug(page, output_dir, "timeout")
            raise
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    run()
