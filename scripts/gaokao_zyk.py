# scripts/gaokao_zyk.py
import csv
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://gaokao.chsi.com.cn/zyk/zybk/"
OUTPUT_DIR = Path("output")

TARGET_DISCIPLINES = [
    "哲学",
    "经济学",
    "法学",
    "教育学",
    "文学",
    "历史学",
    "理学",
    "工学",
    "农学",
    "医学",
    "管理学",
    "艺术学",
]

SCHOOL_NAME_RE = re.compile(
    r"(大学|学院|学校|职业大学|职业学院|高等专科学校|师范大学|师范学院|医学院|中医药大学)$"
)

NAV_BLACKLIST = {
    "首页", "高考资讯", "阳光志愿", "高招咨询", "招生动态", "试题评析", "院校库", "专业库",
    "院校满意度", "专业满意度", "专业推荐", "更多", "招生政策", "选科参考", "云咨询周",
    "成绩查询", "招生章程", "名单公示", "志愿参考", "咨询室", "录取结果", "高职招生",
    "工作动态", "心理测评", "直播安排", "批次线", "专业解读", "各地网站", "职业前景",
    "特殊类型招生", "志愿填报时间", "招办访谈", "登录", "注册", "搜索", "查看"
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


def get_label(item: dict):
    for key in ("value", "label", "name", "text", "title"):
        if item.get(key):
            return clean_text(item[key])
    return ""


def get_key(item: dict):
    for key in ("key", "id", "value", "code"):
        if item.get(key) is not None and item.get(key) != "":
            return item[key]
    return None


def api_get(page, endpoint, *args):
    result = page.evaluate(
        """
        async ({endpoint, args}) => {
            const res = await window.api.syncAjaxget(endpoint, ...args);
            return JSON.parse(JSON.stringify(res));
        }
        """,
        {"endpoint": endpoint, "args": list(args)},
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"{endpoint} 返回异常：{result}")
    if result.get("flag") is not True:
        raise RuntimeError(f"{endpoint} 调用失败：{result}")
    return result.get("msg") or []


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def wait_ready(page):
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_function("window.api && window.api.syncAjaxget", timeout=30000)
    page.locator("#app").wait_for(timeout=20000)
    page.wait_for_timeout(2500)


def open_school_page(context, url):
    p = context.new_page()
    p.goto(url, wait_until="domcontentloaded", timeout=60000)
    p.wait_for_timeout(1800)
    return p


def extract_school_rows(page, major):
    rows = []
    seen = set()
    page_no = 1

    while True:
        anchors = page.evaluate(
            """
            () => {
                const root = document.querySelector('#app') || document.body;
                return Array.from(root.querySelectorAll('a')).map(a => ({
                    text: (a.textContent || '').trim(),
                    href: a.href || ''
                }));
            }
            """
        )

        for item in anchors:
            name = clean_text(item.get("text", ""))
            href = clean_text(item.get("href", ""))

            if not name or name in NAV_BLACKLIST:
                continue
            if not SCHOOL_NAME_RE.search(name):
                continue

            key = (major["specId"], name)
            if key in seen:
                continue
            seen.add(key)

            rows.append({
                "specId": major["specId"],
                "专业代码": major["专业代码"],
                "专业名称": major["专业名称"],
                "门类": major["门类"],
                "专业类": major["专业类"],
                "学校名称": name,
                "学校链接": href,
                "来源页": major["开设院校页"],
                "页码": page_no,
            })

        next_btn = page.locator(".ivu-page-next:not(.ivu-page-disabled)")
        if next_btn.count() == 0:
            break

        next_btn.first.click()
        page.wait_for_timeout(1500)
        page_no += 1

    return rows


def run():
    ensure_output()

    majors = []
    schools = []
    raw_dump = {
        "cc_list": [],
        "ml_list": {},
        "xk_list": {},
        "majors_by_xk": {},
    }

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
            page.screenshot(path=str(OUTPUT_DIR / "01_home.png"), full_page=True)

            cc_list = api_get(page, "zykzybkccCategory")
            raw_dump["cc_list"] = cc_list

            cc_item = None
            for item in cc_list:
                if "本科（普通教育）" in get_label(item):
                    cc_item = item
                    break
            if cc_item is None and cc_list:
                cc_item = cc_list[0]
            if cc_item is None:
                raise RuntimeError("未获取到培养层次列表。")

            cc_name = get_label(cc_item)
            cc_key = get_key(cc_item)

            ml_list = api_get(page, "zykzybkmlCategory", cc_key)
            raw_dump["ml_list"][str(cc_key)] = ml_list

            filtered_ml = []
            for ml in ml_list:
                ml_name = get_label(ml)
                if ml_name in TARGET_DISCIPLINES:
                    filtered_ml.append(ml)

            for ml in filtered_ml:
                ml_name = get_label(ml)
                ml_key = get_key(ml)

                xk_list = api_get(page, "zykzybkxkCategory", ml_key)
                raw_dump["xk_list"][str(ml_key)] = xk_list

                for xk in xk_list:
                    xk_name = get_label(xk)
                    xk_key = get_key(xk)

                    major_rows = api_get(page, "zykzybkspecialityesByCategory", xk_key)
                    raw_dump["majors_by_xk"][str(xk_key)] = major_rows

                    for row in major_rows:
                        spec_id = clean_text(row.get("specId"))
                        major_name = clean_text(row.get("zymc"))
                        major_code = clean_text(row.get("zydm"))
                        satisfaction = clean_text(row.get("zymyd"))

                        detail_url = (
                            urljoin(BASE_URL, f"zykzybkdetail{spec_id}") if spec_id else ""
                        )
                        school_url = (
                            urljoin(BASE_URL, f"zykzybkksyxPage?specId={spec_id}") if spec_id else ""
                        )

                        major_record = {
                            "培养层次": cc_name,
                            "门类": ml_name,
                            "专业类": xk_name,
                            "专业名称": major_name,
                            "专业代码": major_code,
                            "specId": spec_id,
                            "专业满意度": satisfaction,
                            "详情页": detail_url,
                            "开设院校页": school_url,
                        }
                        majors.append(major_record)

                        if school_url:
                            try:
                                school_page = open_school_page(context, school_url)
                                school_rows = extract_school_rows(school_page, major_record)
                                schools.extend(school_rows)
                                school_page.close()
                            except Exception:
                                schools.append({
                                    "specId": spec_id,
                                    "专业代码": major_code,
                                    "专业名称": major_name,
                                    "门类": ml_name,
                                    "专业类": xk_name,
                                    "学校名称": "",
                                    "学校链接": "",
                                    "来源页": school_url,
                                    "页码": "",
                                })

            page.screenshot(path=str(OUTPUT_DIR / "02_done.png"), full_page=True)

        except PlaywrightTimeoutError:
            page.screenshot(path=str(OUTPUT_DIR / "timeout.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()

    majors_fields = [
        "培养层次", "门类", "专业类", "专业名称", "专业代码",
        "specId", "专业满意度", "详情页", "开设院校页"
    ]
    schools_fields = [
        "specId", "专业代码", "专业名称", "门类", "专业类",
        "学校名称", "学校链接", "来源页", "页码"
    ]

    write_csv(OUTPUT_DIR / "majors.csv", majors, majors_fields)
    write_csv(OUTPUT_DIR / "schools.csv", schools, schools_fields)
    save_json(OUTPUT_DIR / "raw_api_dump.json", raw_dump)

    print(f"majors: {len(majors)}")
    print(f"schools: {len(schools)}")


if __name__ == "__main__":
    run()
