import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BASE_URL = "https://gaokao.chsi.com.cn/zyk/zybk/"
OUTPUT_DIR = Path("output")

LEVEL_NAMES = [
    "本科（普通教育）",
    "本科（职业教育）",
    "高职（专科）",
]

SAVE_DEBUG = os.getenv("SAVE_DEBUG", "0") == "1"
SCRAPE_DETAILS = os.getenv("SCRAPE_DETAILS", "1") == "1"
SCRAPE_SCHOOLS = os.getenv("SCRAPE_SCHOOLS", "1") == "1"

SCHOOL_NAME_RE = re.compile(
    r"(大学|学院|学校|职业大学|职业学院|高等专科学校|师范大学|师范学院|医学院|中医药大学)$"
)

NAV_BLACKLIST = {
    "首页", "高考资讯", "阳光志愿", "高招咨询", "招生动态", "试题评析", "院校库", "专业库",
    "院校满意度", "专业满意度", "专业推荐", "更多", "招生政策", "选科参考", "云咨询周",
    "成绩查询", "招生章程", "名单公示", "志愿参考", "咨询室", "录取结果", "高职招生",
    "工作动态", "心理测评", "直播安排", "批次线", "专业解读", "各地网站", "职业前景",
    "特殊类型招生", "志愿填报时间", "招办访谈", "登录", "注册", "搜索", "查看", "取消",
    "基本信息", "开设院校", "开设课程", "图解专业", "选科要求", "更多>"
}

SECTION_ORDER = [
    "专业介绍",
    "统计信息",
    "相近专业",
    "本专业推荐人数较多的高校",
    "该专业学生考研方向",
    "已毕业人员从业方向",
    "薪酬指数",
]

SATISFACTION_LABELS = [
    "综合满意度",
    "办学条件满意度",
    "教学质量满意度",
    "就业满意度",
]


def ensure_output():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat()


def clean_text(text):
    if text is None:
        return ""
    return " ".join(str(text).split()).strip()


def unique_keep_order(items):
    seen = set()
    out = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else item
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_debug(page, name: str):
    if not SAVE_DEBUG:
        return
    page.screenshot(path=str(OUTPUT_DIR / f"{name}.png"), full_page=True)
    (OUTPUT_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")


def wait_ready(page):
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#app", timeout=30000)
    page.wait_for_function(
        """() => {
            const t = document.body ? document.body.innerText : '';
            return t.includes('专业知识库')
                && t.includes('本科（普通教育）专业目录')
                && t.includes('本科（职业教育）专业目录')
                && t.includes('高职（专科）专业目录');
        }""",
        timeout=60000,
    )
    page.wait_for_selector(".index-cc-list", timeout=30000)
    page.wait_for_timeout(1500)


def get_level_locator(page):
    return page.locator(".index-cc-list li")


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


def click_level_by_text(page, level_name: str):
    items = get_level_locator(page)
    for i in range(items.count()):
        item = items.nth(i)
        txt = clean_text(item.inner_text())
        if txt == level_name:
            item.click()
            return
    raise RuntimeError(f"未找到培养层次：{level_name}")


def wait_table(page):
    page.wait_for_selector(".zyk-table-con .ivu-table-body tbody tr", timeout=30000)
    page.wait_for_timeout(1000)


def extract_spec_id(detail_href: str, school_href: str):
    for url in [detail_href, school_href]:
        if not url:
            continue
        m = re.search(r"specId=(\d+)", url)
        if m:
            return m.group(1)
        m = re.search(r"/detail/(\d+)", url)
        if m:
            return m.group(1)
        m = re.search(r"detail(\d+)", url)
        if m:
            return m.group(1)
    return ""


def extract_table_rows(page, level_name, discipline, major_class):
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

        if not major_name or "暂无" in major_name:
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

        spec_id = extract_spec_id(detail_href, school_href)
        if not school_href and spec_id:
            school_href = f"https://gaokao.chsi.com.cn/zyk/zybk/ksyxPage?specId={spec_id}"

        rows.append({
            "培养层次": level_name,
            "门类": discipline,
            "专业类": major_class,
            "专业名称": major_name,
            "专业代码": major_code,
            "专业满意度": satisfaction,
            "详情页": detail_href,
            "开设院校页": school_href,
            "specId": spec_id,
        })
    return rows


def normalize_lines(text):
    lines = [clean_text(x) for x in (text or "").splitlines()]
    return [x for x in lines if x]


def find_title_and_level(lines):
    for i, line in enumerate(lines):
        if line in LEVEL_NAMES:
            title = lines[i - 1] if i > 0 else ""
            return title, line
    return "", ""


def parse_field(text, label):
    m = re.search(rf"{re.escape(label)}[:：]\s*([^\n]+)", text)
    return clean_text(m.group(1)) if m else ""


def extract_section(lines, heading, all_headings):
    try:
        start = lines.index(heading)
    except ValueError:
        return {
            "raw_text": "",
            "lines": []
        }

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i] in all_headings:
            end = i
            break

    content_lines = lines[start + 1:end]
    return {
        "raw_text": "\n".join(content_lines).strip(),
        "lines": content_lines
    }


def parse_data_cutoff(text):
    m = re.search(r"数据统计截止日期[:：]\s*([^\n]+)", text)
    return clean_text(m.group(1)) if m else ""


def parse_graduates_scale(lines):
    for i, line in enumerate(lines):
        if "全国普通高校毕业生规模" in line:
            if i + 1 < len(lines):
                return clean_text(lines[i + 1])
    return ""


def parse_satisfaction_items(text):
    result = {}
    for label in SATISFACTION_LABELS:
        m = re.search(rf"{re.escape(label)}\s*([0-9.]+)\s*([0-9]+人)", text, re.S)
        result[label] = {
            "评分": clean_text(m.group(1)) if m else "",
            "人数": clean_text(m.group(2)) if m else "",
        }
    return result


def parse_links_from_page(page):
    anchors = page.locator("a")
    links = {
        "基本信息": "",
        "开设院校": "",
        "开设课程": "",
        "专业解读": "",
        "图解专业": "",
        "选科要求": "",
    }
    other_links = []

    for i in range(anchors.count()):
        a = anchors.nth(i)
        text = clean_text(a.inner_text())
        href = a.get_attribute("href") or ""
        if not text or not href:
            continue

        full = urljoin(page.url, href)
        if text in links and not links[text]:
            links[text] = full
        elif text not in NAV_BLACKLIST:
            other_links.append({"名称": text, "链接": full})

    return links, unique_keep_order(other_links)


def parse_nearby_majors(page, current_spec_id):
    anchors = page.locator("a")
    items = []
    for i in range(anchors.count()):
        a = anchors.nth(i)
        text = clean_text(a.inner_text())
        href = a.get_attribute("href") or ""
        if not text or not href:
            continue
        full = urljoin(page.url, href)
        if "/zyk/zybk/detail/" not in full:
            continue
        sid = ""
        m = re.search(r"/detail/(\d+)", full)
        if m:
            sid = m.group(1)
        if sid and sid == current_spec_id:
            continue
        items.append({
            "名称": text,
            "链接": full,
            "specId": sid,
        })
    return unique_keep_order(items)


def parse_postgraduate_links(page):
    anchors = page.locator("a")
    items = []
    for i in range(anchors.count()):
        a = anchors.nth(i)
        text = clean_text(a.inner_text())
        href = a.get_attribute("href") or ""
        if not text or not href:
            continue
        full = urljoin(page.url, href)
        if "yz.chsi.com.cn/zyk/specialityDetail.do" in full:
            parsed = urlparse(full)
            qs = parse_qs(parsed.query)
            items.append({
                "名称": text,
                "链接": full,
                "专业代码": qs.get("zydm", [""])[0],
                "层次键": qs.get("cckey", [""])[0],
            })
    return unique_keep_order(items)


def parse_recommended_schools(section_lines):
    schools = []
    i = 0
    while i < len(section_lines):
        name = section_lines[i]
        if SCHOOL_NAME_RE.search(name):
            score = section_lines[i + 1] if i + 1 < len(section_lines) else ""
            count = section_lines[i + 2] if i + 2 < len(section_lines) else ""
            if re.fullmatch(r"[0-9.]+", clean_text(score)) and re.fullmatch(r"\d+人", clean_text(count)):
                schools.append({
                    "学校名称": name,
                    "评分": clean_text(score),
                    "人数": clean_text(count),
                })
                i += 3
                continue
        i += 1
    return schools


def parse_employment_directions(section_lines):
    raw = "".join(section_lines).strip()
    if not raw:
        return []
    parts = re.split(r"[、，,；;\s]+", raw)
    return [x for x in [clean_text(p) for p in parts] if x]


def extract_detail(context, major_row):
    if not major_row["详情页"]:
        return {
            "error": "missing_detail_url"
        }

    current_spec_id = major_row.get("specId", "")
    detail_page = context.new_page()
    try:
        detail_page.goto(major_row["详情页"], wait_until="domcontentloaded", timeout=60000)
        detail_page.wait_for_timeout(1800)
        text = detail_page.locator("body").inner_text(timeout=30000)
        lines = normalize_lines(text)

        title_guess, level_guess = find_title_and_level(lines)
        code = parse_field(text, "专业代码")
        discipline = parse_field(text, "门类")
        major_class = parse_field(text, "专业类")

        link_map, other_links = parse_links_from_page(detail_page)

        section_map = {}
        for heading in SECTION_ORDER:
            section_map[heading] = extract_section(lines, heading, SECTION_ORDER)

        stats_lines = section_map["统计信息"]["lines"]
        salary_lines = section_map["薪酬指数"]["lines"]

        detail = {
            "标题": title_guess or major_row.get("专业名称", ""),
            "培养层次": level_guess or major_row.get("培养层次", ""),
            "专业代码": code or major_row.get("专业代码", ""),
            "门类": discipline or major_row.get("门类", ""),
            "专业类": major_class or major_row.get("专业类", ""),
            "链接": {
                "详情页": major_row["详情页"],
                "基本信息": link_map.get("基本信息", major_row["详情页"]),
                "开设院校": link_map.get("开设院校", major_row.get("开设院校页", "")),
                "开设课程": link_map.get("开设课程", ""),
                "专业解读": link_map.get("专业解读", ""),
                "图解专业": link_map.get("图解专业", ""),
                "选科要求": link_map.get("选科要求", ""),
            },
            "专业介绍": section_map["专业介绍"]["raw_text"],
            "统计信息": {
                "数据统计截止日期": parse_data_cutoff(section_map["统计信息"]["raw_text"]),
                "全国普通高校毕业生规模": parse_graduates_scale(stats_lines),
                "专业满意度": parse_satisfaction_items(section_map["统计信息"]["raw_text"] + "\n" + text),
                "原始文本": section_map["统计信息"]["raw_text"],
            },
            "相近专业": parse_nearby_majors(detail_page, current_spec_id),
            "本专业推荐人数较多的高校": {
                "原始文本": section_map["本专业推荐人数较多的高校"]["raw_text"],
                "学校列表": parse_recommended_schools(section_map["本专业推荐人数较多的高校"]["lines"]),
            },
            "考研方向": parse_postgraduate_links(detail_page),
            "已毕业人员从业方向": {
                "原始文本": section_map["已毕业人员从业方向"]["raw_text"],
                "列表": parse_employment_directions(section_map["已毕业人员从业方向"]["lines"]),
            },
            "薪酬指数": {
                "原始文本": section_map["薪酬指数"]["raw_text"],
                "列表": salary_lines,
            },
            "其他链接": other_links,
            "抓取时间": iso_now(),
        }
        return detail
    except Exception as e:
        return {
            "error": repr(e),
            "详情页": major_row["详情页"],
            "抓取时间": iso_now(),
        }
    finally:
        detail_page.close()


def extract_school_rows(context, major_row):
    if not major_row["开设院校页"]:
        return {
            "来源页": "",
            "学校数量": 0,
            "学校列表": [],
            "error": "missing_school_url",
        }

    page = context.new_page()
    school_rows = []
    seen = set()

    try:
        page.goto(major_row["开设院校页"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

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

                key = text
                if key in seen:
                    continue
                seen.add(key)

                school_rows.append({
                    "学校名称": text,
                    "学校链接": urljoin(page.url, href) if href else "",
                    "页码": page_no,
                })

            next_btn = page.locator(".ivu-page-next:not(.ivu-page-disabled)")
            if next_btn.count() == 0:
                break

            next_btn.first.click()
            page.wait_for_timeout(1200)
            page_no += 1

        return {
            "来源页": major_row["开设院校页"],
            "学校数量": len(school_rows),
            "学校列表": school_rows,
        }
    except Exception as e:
        return {
            "来源页": major_row["开设院校页"],
            "学校数量": len(school_rows),
            "学校列表": school_rows,
            "error": repr(e),
        }
    finally:
        page.close()


def build_hierarchy(levels_data, flat_rows):
    level_map = {}

    for row in flat_rows:
        level_name = row["培养层次"]
        discipline_name = row["门类"]
        class_name = row["专业类"]

        if level_name not in level_map:
            level_map[level_name] = {
                "名称": level_name,
                "门类列表": {}
            }

        level_obj = level_map[level_name]
        if discipline_name not in level_obj["门类列表"]:
            level_obj["门类列表"][discipline_name] = {
                "门类": discipline_name,
                "专业类列表": {}
            }

        discipline_obj = level_obj["门类列表"][discipline_name]
        if class_name not in discipline_obj["专业类列表"]:
            discipline_obj["专业类列表"][class_name] = {
                "专业类": class_name,
                "专业列表": []
            }

        major_obj = deepcopy(row)
        discipline_obj["专业类列表"][class_name]["专业列表"].append(major_obj)

    final_levels = []
    for level_name in levels_data:
        if level_name not in level_map:
            final_levels.append({
                "名称": level_name,
                "门类列表": []
            })
            continue

        level_obj = level_map[level_name]
        disciplines = []
        for discipline_name, discipline_obj in level_obj["门类列表"].items():
            class_list = []
            for class_name, class_obj in discipline_obj["专业类列表"].items():
                class_list.append({
                    "专业类": class_name,
                    "专业列表": class_obj["专业列表"]
                })
            disciplines.append({
                "门类": discipline_name,
                "专业类列表": class_list
            })

        final_levels.append({
            "名称": level_name,
            "门类列表": disciplines
        })

    return final_levels


def run():
    ensure_output()

    flat_majors = []
    levels_found = []
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

            level_items = get_level_locator(page)
            all_level_texts = []
            for i in range(level_items.count()):
                txt = clean_text(level_items.nth(i).inner_text())
                if txt:
                    all_level_texts.append(txt)

            for level_name in LEVEL_NAMES:
                if level_name in all_level_texts:
                    levels_found.append(level_name)

            for level_name in levels_found:
                click_level_by_text(page, level_name)
                page.wait_for_timeout(1500)

                discipline_group = get_group(page, 0)
                class_group = get_group(page, 1)

                discipline_texts = get_group_items_texts(discipline_group)

                for discipline in discipline_texts:
                    click_group_item_by_text(discipline_group, discipline)
                    page.wait_for_timeout(1200)

                    class_texts = get_group_items_texts(class_group)
                    for major_class in class_texts:
                        click_group_item_by_text(class_group, major_class)
                        wait_table(page)

                        rows = extract_table_rows(page, level_name, discipline, major_class)
                        for row in rows:
                            key = row["specId"] or (row["培养层次"], row["门类"], row["专业类"], row["专业名称"], row["专业代码"])
                            if key in seen_major:
                                continue
                            seen_major.add(key)

                            if SCRAPE_DETAILS:
                                row["详情"] = extract_detail(context, row)
                            else:
                                row["详情"] = {}

                            if SCRAPE_SCHOOLS:
                                row["开设院校"] = extract_school_rows(context, row)
                            else:
                                row["开设院校"] = {
                                    "来源页": row.get("开设院校页", ""),
                                    "学校数量": 0,
                                    "学校列表": [],
                                }

                            flat_majors.append(row)

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

    all_json = {
        "抓取时间": iso_now(),
        "来源": BASE_URL,
        "培养层次列表": build_hierarchy(levels_found, flat_majors),
    }

    flat_json = {
        "抓取时间": iso_now(),
        "来源": BASE_URL,
        "数量": len(flat_majors),
        "专业列表": flat_majors,
    }

    meta_json = {
        "抓取时间": iso_now(),
        "来源": BASE_URL,
        "培养层次": levels_found,
        "专业总数": len(flat_majors),
        "是否抓详情": SCRAPE_DETAILS,
        "是否抓院校": SCRAPE_SCHOOLS,
    }

    save_json(OUTPUT_DIR / "all.json", all_json)
    save_json(OUTPUT_DIR / "majors-flat.json", flat_json)
    save_json(OUTPUT_DIR / "meta.json", meta_json)

    print(f"levels: {len(levels_found)}")
    print(f"majors: {len(flat_majors)}")
    print(f"detail: {SCRAPE_DETAILS}")
    print(f"schools: {SCRAPE_SCHOOLS}")


if __name__ == "__main__":
    run()
