# scripts/gaokao_zyk.py
import csv
import re
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://gaokao.chsi.com.cn/zyk/zybk/"
OUTPUT_DIR = Path("output")

TARGET_DISCIPLINES = [
    "哲学", "经济学", "法学", "教育学", "文学", "历史学",
    "理学", "工学", "农学", "医学", "管理学", "艺术学",
]

SCHOOL_NAME_RE = re.compile(
    r"(大学|学院|学校|职业大学|职业学院|高等专科学校|师范大学|师范学院|医学院|中医药大学)$"
)

NAV_BLACKLIST = {
    "首页", "高考资讯", "阳光志愿", "高招咨询", "招生动态", "试题评析", "院校库", "专业库",
    "院校满意度", "专业满意度", "专业推荐", "更多", "招生政策", "选科参考", "云咨询周",
    "成绩查询", "招生章程", "名单公示", "志愿参考", "咨询室", "录取结果", "高职招生",
    "工作动态", "心理测评", "直播安排", "批次线", "专业解读", "各地网站", "职业前景",
    "特殊类型招生", "志愿填报时间", "招办访谈", "登录", "注册", "搜索", "查看", "取消"
}


def ensure_output():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(text):
    if text is None:
        return ""
    return " ".join(str(text).split()).strip()


def write_csv(path: Path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def save_debug(page, name: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUTPUT_DIR / f"{name}.png"), full_page=True)
    (OUTPUT_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")


def wait_ready(page):
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#app", timeout=30000)
    page.wait_for_function(
        """() => {
            const t = document.body ? document.body.innerText : '';
            return t.includes('专业知识库')
                && t.includes('专业名称')
                && t.includes('专业代码')
                && t.includes('开设院校')
                && t.includes('专业满意度');
        }""",
        timeout=60000,
    )
    page.wait_for_selector(".spec-list .zyk-lb-ul-con", timeout=30000)
    page.wait_for_timeout(3000)


def click_if_needed(locator):
    cls = locator.get_attribute("class") or ""
    if "selected" not in cls:
        locator.click()
        return True
    return False


def get_group(page, idx: int):
    return page.locator(".spec-list .zyk-lb-ul-con").nth(idx)


def get_group_items_texts(group):
    items = group.locator("ul.zyk-lb-ul > li")
    texts = []
    for i in range(items.count()):
        txt = clean_text(items.nth(i).inner_text())
        if txt:
            texts.append(txt)
    return texts


def click_group_item_by_text(group, text: str):
    items = group.locator("ul.zyk-lb-ul > li")
    for i in range(items.count()):
        item = items.nth(i)
        txt = clean_text(item.inner_text())
        if txt == text:
            item.click()
            return
    raise RuntimeError(f"未找到分组项：{text}")


def wait_table(page):
    page.wait_for_selector(".zyk-table-con .ivu-table-body tbody tr", timeout=30000)
    page.wait_for_timeout(1500)


def extract_table_rows(page, discipline, major_class):
    rows = []
    tr_list = page.locator(".zyk-table-con .ivu-table-body tbody tr")
    for i in range(tr_list.count()):
        tr = tr_list.nth(i)
        tds = tr.locator("td")
        if tds.count() < 4:
            continue

        major_name = clean_text(tds.nth(0).inner_text())
        major_code = clean_text(tds.nth(1).inner_text())
        school_text = clean_text(tds.nth(2).inner_text())
        satisfaction = clean_text(tds.nth(3).inner_text())

        if not major_name or "暂无筛选结果" in major_name:
            continue

        detail_href = ""
        school_href = ""

        a1 = tds.nth(0).locator("a")
        if a1.count() > 0:
            href = a1.first.get_attribute("href")
            if href:
                detail_href = urljoin(BASE_URL, href)

        a2 = tds.nth(2).locator("a")
        if a2.count() > 0:
            href = a2.first.get_attribute("href")
            if href:
                school_href = urljoin(BASE_URL, href)

        rows.append({
            "门类": discipline,
            "专业类": major_class,
            "专业名称": major_name,
            "专业代码": major_code,
            "开设院校": school_text,
            "专业满意度": satisfaction,
            "详情页": detail_href,
            "开设院校页": school_href,
            "specId": extract_spec_id(detail_href, school_href),
        })
    return rows


def extract_spec_id(detail_href: str, school_href: str):
    for url in [detail_href, school_href]:
        if not url:
            continue
        m = re.search(r"specId=(\\d+)", url)
        if m:
            return m.group(1)
        m = re.search(r"detail(\\d+)", url)
        if m:
            return m.group(1)
    return ""


def extract_school_rows(context, major_row):
    if not major_row["开设院校页"]:
        return []

    page = context.new_page()
    school_rows = []
    seen = set()

    try:
        page.goto(major_row["开设院校页"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)

        page_no = 1
        while True:
            anchors = page.locator("a")
            for i in range(anchors.count()):
                a = anchors.nth(i)
                text = clean_text(a.inner_text())
                href = a.get_attribute("href") or ""

                if not text or text in NAV_BLACKLIST:
                    continue
                if not SCHOOL_NAME_RE.search(text):
                    continue

                key = (major_row["specId"], text)
                if key in seen:
                    continue
                seen.add(key)

                school_rows.append({
                    "specId": major_row["specId"],
                    "门类": major_row["门类"],
                    "专业类": major_row["专业类"],
                    "专业名称": major_row["专业名称"],
                    "专业代码": major_row["专业代码"],
                    "学校名称": text,
                    "学校链接": urljoin(major_row["开设院校页"], href) if href else "",
                    "来源页": major_row["开设院校页"],
                    "页码": page_no,
                })

            next_btn = page.locator(".ivu-page-next:not(.ivu-page-disabled)")
            if next_btn.count() == 0:
                break

            next_btn.first.click()
            page.wait_for_timeout(1800)
            page_no += 1

    finally:
        page.close()

    return school_rows


def run():
    ensure_output()
    majors = []
    schools = []
    seen_major = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
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
            wait_ready(page)
            save_debug(page, "01_ready")

            # 如果“本科（普通教育）”可点击，则显式点一次
            try:
                level_items = page.locator(".index-cc-list li")
                for i in range(level_items.count()):
                    li = level_items.nth(i)
                    txt = clean_text(li.inner_text())
                    if txt == "本科（普通教育）":
                        click_if_needed(li)
                        page.wait_for_timeout(1500)
                        break
            except Exception:
                pass

            discipline_group = get_group(page, 0)
            class_group = get_group(page, 1)

            discipline_texts = [
                x for x in get_group_items_texts(discipline_group)
                if x in TARGET_DISCIPLINES
            ]

            for discipline in discipline_texts:
                click_group_item_by_text(discipline_group, discipline)
                page.wait_for_timeout(1800)

                class_texts = get_group_items_texts(class_group)
                for major_class in class_texts:
                    click_group_item_by_text(class_group, major_class)
                    wait_table(page)

                    rows = extract_table_rows(page, discipline, major_class)
                    for row in rows:
                        key = row["specId"] or (row["门类"], row["专业类"], row["专业名称"], row["专业代码"])
                        if key in seen_major:
                            continue
                        seen_major.add(key)
                        majors.append(row)

                        try:
                            school_rows = extract_school_rows(context, row)
                            schools.extend(school_rows)
                        except Exception:
                            schools.append({
                                "specId": row["specId"],
                                "门类": row["门类"],
                                "专业类": row["专业类"],
                                "专业名称": row["专业名称"],
                                "专业代码": row["专业代码"],
                                "学校名称": "",
                                "学校链接": "",
                                "来源页": row["开设院校页"],
                                "页码": "",
                            })

            save_debug(page, "02_done")

        except PlaywrightTimeoutError:
            save_debug(page, "timeout")
            raise
        except Exception:
            save_debug(page, "error")
            raise
        finally:
            context.close()
            browser.close()

    write_csv(
        OUTPUT_DIR / "majors.csv",
        majors,
        ["门类", "专业类", "专业名称", "专业代码", "开设院校", "专业满意度", "详情页", "开设院校页", "specId"],
    )
    write_csv(
        OUTPUT_DIR / "schools.csv",
        schools,
        ["specId", "门类", "专业类", "专业名称", "专业代码", "学校名称", "学校链接", "来源页", "页码"],
    )

    print(f"majors: {len(majors)}")
    print(f"schools: {len(schools)}")


if __name__ == "__main__":
    run()
