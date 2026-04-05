"""
阳光高考爬虫 - 完整版

支持两种模式：
1. Playwright 模式：自动爬取（需要绕过阿里云盾）
2. 手动模式：提供数据接口，可手动导入数据
"""
import json
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup


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
            resp = self.session.get("https://gaokao.chsi.com.cn/zyk/zybk/catalog.shtml", timeout=30)
            if resp.status_code == 412:
                print("⚠️  被阿里云盾拦截 (HTTP 412)")
                print("   建议：")
                print("   1. 在本地机器运行，使用真实浏览器")
                print("   2. 使用代理池")
                print("   3. 或使用手动导入模式")
                return True
            return resp.status_code != 200
        except Exception as e:
            print(f"连接错误: {e}")
            return True

    async def scrape_with_playwright(self) -> Dict:
        """使用 Playwright 爬取（需要安装 playwright）"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("请先安装: pip install playwright && playwright install chromium")

        print("启动 Playwright...")
        
        async with async_playwright() as p:
            # 反检测配置
            browser = await p.chromium.launch(
                headless=False,  # 设为 False 可能更容易绕过检测
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            
            # 注入反检测脚本
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
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
                url = "https://gaokao.chsi.com.cn/zyk/zybk/catalog.shtml"
                print(f"正在访问: {url}")
                
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(5)  # 等待 JS 渲染
                
                # TODO: 根据实际页面结构解析
                # 这里需要你手动查看页面后补充选择器
                # 示例：
                # specialties = await page.query_selector_all(".specialty-item")
                # for item in specialties:
                #     name = await item.query_selector(".name").text_content()
                #     ...
                
                print("⚠️  页面解析逻辑需要根据实际页面结构补充")
                print("   请在浏览器中打开页面，按 F12 查看元素结构")
                print("   然后修改 scraper.py 中的解析代码")
                
            except Exception as e:
                print(f"Playwright 爬取错误: {e}")
            
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
        elif filename.endswith('.csv'):
            import pandas as pd
            
            if "specialties" in data:
                df = pd.DataFrame(data["specialties"])
                df.to_csv(filepath.parent / f"specialties_{filepath.stem}.csv", 
                         index=False, encoding="utf-8-sig")
            
            if "schools" in data:
                df = pd.DataFrame(data["schools"])
                df.to_csv(filepath.parent / f"schools_{filepath.stem}.csv", 
                         index=False, encoding="utf-8-sig")
        
        print(f"✓ 数据已保存到: {filepath}")

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
    
    args = parser.parse_args()
    
    scraper = GaokaoScraper(use_playwright=(args.mode == "playwright"))
    
    # 生成模板
    if args.template:
        scraper.export_template()
        return
    
    # 手动导入
    if args.import_file:
        data = scraper.import_from_json(args.import_file)
        scraper.save_data(data, args.output)
        return
    
    # 自动模式
    if args.mode == "auto":
        if scraper.check_waf():
            print("\n无法直接访问，尝试切换到 Playwright 模式...")
            scraper.use_playwright = True
    
    # 使用 Playwright
    if scraper.use_playwright:
        data = asyncio.run(scraper.scrape_with_playwright())
        scraper.save_data(data, args.output)
    else:
        print("请使用 --template 生成模板，手动填写后用 --import 导入")


if __name__ == "__main__":
    main()
