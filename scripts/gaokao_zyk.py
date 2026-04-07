# scripts/gaokao_zyk.py
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def run(keyword="计算机科学与技术"):
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=200)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        try:
            page.goto("https://gaokao.chsi.com.cn/zyk/zybk/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            candidate_selectors = [
                'input[placeholder*="搜索"]',
                'input[placeholder*="专业"]',
                'input[type="search"]',
                'input.el-input__inner',
                'input'
            ]

            search_box = None
            for selector in candidate_selectors:
                try:
                    loc = page.locator(selector).first
                    if loc.is_visible():
                        search_box = loc
                        break
                except Exception:
                    pass

            if not search_box:
                raise RuntimeError("没有找到可见的搜索输入框，请检查页面结构是否变化。")

            search_box.click()
            search_box.fill(keyword)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

            try:
                btn = page.get_by_role("button", name="搜索").first
                if btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(3000)
            except Exception:
                pass

            page.screenshot(path=str(output_dir / "gaokao_zyk_demo.png"), full_page=True)

            text = page.locator("body").inner_text()
            (output_dir / "result.txt").write_text(text[:5000], encoding="utf-8")

        except PlaywrightTimeoutError:
            (output_dir / "error.txt").write_text("页面加载超时。", encoding="utf-8")
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    run()
