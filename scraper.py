"""
阳光高考爬虫 - 完整版

支持两种模式：
1. Playwright 模式：自动爬取（绕过阿里云盾）
2. 手动模式：提供数据接口，可手动导入数据

增强反检测措施：
- 使用真实浏览器指纹
- 随机延迟和人类行为模拟
- 完整的 WebDriver 隐藏
"""
import json
import asyncio
import os
import random
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup

from config import (
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    SPECIALTY_CATALOG_URL,
    SPECIALTY_DETAIL_URL,
    SPECIALTY_SCHOOLS_URL,
)

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass


@dataclass
class Specialty:
    """专业信息"""
    specialty_id: str
    name: str
    level: str  # 本科/专科
    category: str  # 学科门类
    description: str = ""
    training_objective: str = ""
    main_courses: str = ""
    employment_direction: str = ""
    more_info_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SchoolSpecialty:
    """院校开设专业信息"""
    specialty_id: str
    school_name: str
    school_id: str = ""
    province: str = ""
    level: str = ""
    feature: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class GaokaoScraper:
    """阳光高考爬虫"""

    def __init__(self, use_playwright: bool = False):
        self.use_playwright = use_playwright
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.specialties = []
        self.schools = []

        if not use_playwright:
            # 简单的 HTTP 会话（会被阿里云盾拦截，仅供测试）
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })

    def check_waf(self) -> bool:
        """检查是否被 WAF 拦截"""
        try:
            resp = self.session.get(SPECIALTY_CATALOG_URL, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 412:
                print("⚠️  被阿里云盾拦截 (HTTP 412)")
                print("   建议使用 Playwright 模式")
                return True
            return resp.status_code != 200
        except Exception as e:
            print(f"连接错误: {e}")
            return True

    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """随机延迟，模拟人类行为"""
        time.sleep(random.uniform(min_sec, max_sec))

    async def scrape_with_playwright(self) -> Dict:
        """使用 Playwright 爬取（增强反检测）"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("请先安装: pip install playwright && playwright install chromium")

        print("🚀 启动 Playwright 浏览器...")

        async with async_playwright() as p:
            # 反检测配置 - 使用真实浏览器环境
            browser = await p.chromium.launch(
                headless=True,  # GitHub Actions 需要 headless
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--disable-extensions',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                ]
            )

            # 创建隐身上下文，模拟真实浏览器
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                permissions=["geolocation"],
                geolocation={"latitude": 39.9042, "longitude": 116.4074},  # 北京
                color_scheme="light",
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False,
                java_script_enabled=True,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Cache-Control': 'max-age=0',
                    'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                }
            )

            # 注入强力反检测脚本
            await context.add_init_script("""
                // 隐藏 webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // 伪造 Chrome 对象
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };

                // 伪造 plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // 伪造 languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });

                // 伪造 platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });

                // 伪造 hardwareConcurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });

                // 伪造 deviceMemory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });

                // 覆盖 permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // 伪造 canvas 指纹
                const getImageData = CanvasRenderingContext2D.prototype.getImageData;
                CanvasRenderingContext2D.prototype.getImageData = function() {
                    const imageData = getImageData.apply(this, arguments);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] = imageData.data[i] ^ 1;
                    }
                    return imageData;
                };

                // 伪造 WebGL 指纹
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine';
                    }
                    return getParameter.apply(this, arguments);
                };
            """)

            page = await context.new_page()

            result = {
                "specialties": [],
                "schools": [],
                "scrape_time": datetime.now().isoformat(),
                "method": "playwright"
            }

            try:
                # 访问专业目录页
                print(f"📄 正在访问专业目录页...")

                response = await page.goto(SPECIALTY_CATALOG_URL, wait_until="networkidle", timeout=60000)
                status_code = response.status
                print(f"调试: HTTP 状态码 = {status_code}")

                # 检查是否被 WAF 拦截
                if status_code == 412:
                    print("\n" + "="*60)
                    print("⚠️  阿里云盾 WAF 拦截 (HTTP 412)")
                    print("="*60)
                    print("即使使用 Playwright 反检测，该网站的 WAF 仍然拦截了请求。")
                    print("\n可能的解决方案：")
                    print("1. 使用代理服务器（需要配置 PROXY_HTTP/PROXY_HTTPS）")
                    print("2. 在本地真实浏览器中手动访问，然后使用 --template 生成模板")
                    print("3. 使用 --import 导入手动收集的数据")
                    print("4. 联系网站管理员获取官方 API")
                    print("\n生成数据模板命令：")
                    print("  python main.py --template")
                    print("\n导入数据命令：")
                    print("  python main.py --import data/template.json --format json")
                    print("="*60 + "\n")

                    await browser.close()
                    return result

                # 等待页面完全加载 - 增加等待时间
                print("⏳ 等待页面加载...")
                await asyncio.sleep(10)  # 等待 10 秒让 JS 完全执行

                # 尝试等待特定元素出现
                try:
                    await page.wait_for_selector('body', timeout=10000)
                    print("✓ body 元素已加载")
                except:
                    print("⚠️  等待 body 元素超时")

                # 截图用于调试
                screenshot_file = self.data_dir / "debug_screenshot.png"
                await page.screenshot(path=str(screenshot_file), full_page=True)
                print(f"调试: 页面截图已保存到 {screenshot_file}")

                # 获取页面内容用于调试
                content = await page.content()
                print(f"调试: 页面内容长度 = {len(content)} 字符")

                # 保存页面内容用于调试
                debug_file = self.data_dir / "debug_page.html"
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"调试: 页面内容已保存到 {debug_file}")

                # 尝试多种可能的选择器解析专业列表
                print("🔍 正在解析专业列表...")
                specialty_links = await page.query_selector_all('a[href*="specialtyDetail"]')

                if not specialty_links:
                    # 方案2: 尝试查找包含专业的列表项
                    specialty_links = await page.query_selector_all('.specialty-item a, .major-item a, li a[href*="zyk"]')

                if not specialty_links:
                    # 方案3: 使用 BeautifulSoup 手动解析
                    soup = BeautifulSoup(content, 'lxml')

                    # 查找所有可能的专业链接
                    links = soup.find_all('a', href=lambda x: x and ('specialty' in x.lower() or 'zyk' in x))

                    print(f"✓ 通过 BeautifulSoup 找到 {len(links)} 个潜在专业链接")

                    # 如果还是没找到，尝试查找所有链接
                    if len(links) == 0:
                        all_links = soup.find_all('a', href=True)
                        print(f"调试: 页面共有 {len(all_links)} 个链接")

                        # 打印前 10 个链接用于调试
                        print("调试: 前 10 个链接:")
                        for i, link in enumerate(all_links[:10], 1):
                            print(f"  {i}. {link.get_text(strip=True)[:50]} -> {link.get('href')[:80]}")

                        # 尝试查找包含"专业"的链接
                        links = [link for link in all_links if '专业' in link.get_text() or 'major' in link.get('href', '').lower()]
                        print(f"调试: 找到 {len(links)} 个包含'专业'的链接")

                    for link in links[:50]:  # 限制数量，避免过多
                        try:
                            name = link.get_text(strip=True)
                            href = link.get('href', '')

                            if not name or len(name) > 50:
                                continue

                            # 提取专业ID
                            specialty_id = ""
                            if 'specialtyId=' in href:
                                specialty_id = href.split('specialtyId=')[1].split('&')[0]

                            specialty = Specialty(
                                specialty_id=specialty_id or f"unknown_{len(result['specialties'])}",
                                name=name,
                                level="本科",  # 默认
                                category="未分类",
                                more_info_url=href if href.startswith('http') else f"https://gaokao.chsi.com.cn{href}"
                            )

                            result["specialties"].append(specialty.to_dict())

                        except Exception as e:
                            print(f"  解析专业失败: {e}")
                            continue
                else:
                    # 使用 Playwright 选择器解析
                    print(f"✓ 找到 {len(specialty_links)} 个专业链接")

                    for i, link in enumerate(specialty_links[:50]):  # 限制数量
                        try:
                            name = await link.text_content()
                            href = await link.get_attribute('href')

                            if not name or not href:
                                continue

                            name = name.strip()

                            # 提取专业ID
                            specialty_id = ""
                            if 'specialtyId=' in href:
                                specialty_id = href.split('specialtyId=')[1].split('&')[0]

                            specialty = Specialty(
                                specialty_id=specialty_id or f"unknown_{i}",
                                name=name,
                                level="本科",
                                category="未分类",
                                more_info_url=href if href.startswith('http') else f"https://gaokao.chsi.com.cn{href}"
                            )

                            result["specialties"].append(specialty.to_dict())

                        except Exception as e:
                            print(f"  解析专业 {i} 失败: {e}")
                            continue

                print(f"✓ 成功解析 {len(result['specialties'])} 个专业")

            except Exception as e:
                print(f"❌ Playwright 爬取错误: {e}")
                import traceback
                traceback.print_exc()

            await browser.close()
            return result

    def import_from_json(self, json_file: str) -> Dict:
        """从 JSON 文件导入数据（手动模式）"""
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 验证数据格式
        if "specialties" in data:
            print(f"✓ 导入 {len(data['specialties'])} 条专业信息")
        if "schools" in data:
            print(f"✓ 导入 {len(data['schools'])} 条院校信息")
        
        return data

    def save_data(self, data: Dict, filename: str):
        """保存数据到文件"""
        filepath = self.data_dir / filename

        if filename.endswith('.json'):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"数据已保存到: {filepath}")
        elif filename.endswith('.csv'):
            import pandas as pd

            if "specialties" in data and data["specialties"]:
                df = pd.DataFrame(data["specialties"])
                csv_file = filepath.parent / f"specialties_{filepath.stem}.csv"
                df.to_csv(csv_file, index=False, encoding="utf-8-sig")
                print(f"专业数据已保存到: {csv_file}")

            if "schools" in data and data["schools"]:
                df = pd.DataFrame(data["schools"])
                csv_file = filepath.parent / f"schools_{filepath.stem}.csv"
                df.to_csv(csv_file, index=False, encoding="utf-8-sig")
                print(f"院校数据已保存到: {csv_file}")
        else:
            # 默认保存为 JSON
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"数据已保存到: {filepath}")

    def export_template(self):
        """导出数据模板（用于手动填写）"""
        template = {
            "specialties": [
                {
                    "specialty_id": "080901",
                    "name": "计算机科学与技术",
                    "level": "本科",
                    "category": "工学",
                    "description": "专业介绍...",
                    "training_objective": "培养目标...",
                    "main_courses": "高等数学、线性代数...",
                    "employment_direction": "软件开发、网络安全...",
                }
            ],
            "schools": [
                {
                    "specialty_id": "080901",
                    "school_name": "清华大学",
                    "school_id": "10001",
                    "province": "北京",
                    "level": "本科",
                    "feature": "双一流",
                }
            ],
            "_comment": "手动填写数据后，使用 python scraper.py --import data.json 导入"
        }
        
        template_file = self.data_dir / "template.json"
        with open(template_file, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 数据模板已生成: {template_file}")
        print("  请根据模板填写数据，然后使用 --import 导入")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="阳光高考专业信息爬虫")
    parser.add_argument("--mode", choices=["auto", "playwright", "manual"], default="auto",
                       help="运行模式: auto=自动检测, playwright=使用浏览器, manual=手动导入")
    parser.add_argument("--import", dest="import_file", help="从 JSON 文件导入数据")
    parser.add_argument("--template", action="store_true", help="生成数据模板")
    parser.add_argument("--output", default="data.json", help="输出文件名")
    parser.add_argument("--all", action="store_true", help="爬取所有专业（默认行为）")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="输出格式")

    args = parser.parse_args()

    scraper = GaokaoScraper(use_playwright=(args.mode == "playwright"))

    # 生成模板
    if args.template:
        scraper.export_template()
        return

    # 手动导入
    if args.import_file:
        data = scraper.import_from_json(args.import_file)
        output_file = args.output if args.output != "data.json" else f"specialties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{args.format}"
        scraper.save_data(data, output_file)
        return

    # 自动模式
    if args.mode == "auto":
        print("🔍 检测网站访问状态...")
        if scraper.check_waf():
            print("\n⚠️  无法直接访问，切换到 Playwright 模式...")
            scraper.use_playwright = True

    # 使用 Playwright
    if scraper.use_playwright:
        print("\n🚀 使用 Playwright 模式爬取...")
        data = asyncio.run(scraper.scrape_with_playwright())

        # 生成输出文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if args.output == "data.json":
            output_file = f"specialties_{timestamp}.{args.format}"
        else:
            output_file = args.output

        scraper.save_data(data, output_file)

        print(f"\n✅ 爬取完成！")
        print(f"   专业数量: {len(data.get('specialties', []))}")
        print(f"   院校数量: {len(data.get('schools', []))}")
    else:
        print("❌ 请使用 --mode playwright 或 --template 生成模板后手动导入")


if __name__ == "__main__":
    main()
