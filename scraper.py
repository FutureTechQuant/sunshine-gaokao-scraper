"""
阳光高考专业信息爬虫
"""
import time
import random
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime
import json

import requests
from bs4 import BeautifulSoup

import config


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

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })

        # 设置代理
        if config.PROXY_HTTP:
            self.session.proxies = {
                "http": config.PROXY_HTTP,
                "https": config.PROXY_HTTPS,
            }

    def _request(self, url: str, retries: int = config.MAX_RETRIES) -> Optional[requests.Response]:
        """发送请求，带重试机制"""
        for attempt in range(retries):
            try:
                # 随机延迟，避免被识别为机器人
                delay = config.REQUEST_DELAY + random.uniform(0, 2)
                time.sleep(delay)

                response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                response.raise_for_status()
                return response

            except requests.RequestException as e:
                print(f"请求失败 (attempt {attempt + 1}/{retries}): {url}")
                print(f"错误: {e}")

                if attempt == retries - 1:
                    return None

        return None

    def get_specialty_catalog(self) -> List[Dict]:
        """
        获取专业目录

        返回格式: [
            {id: "0809", name: "计算机", level: "本科", category: "工学"},
            ...
        ]
        """
        url = config.SPECIALTY_CATALOG_URL
        response = self._request(url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, "lxml")

        # 这里需要根据实际页面结构来解析
        # 阳光高考的专业目录页面结构比较复杂，可能需要处理动态加载
        specialties = []

        # TODO: 实现页面解析逻辑
        # 这里提供一些可能的选择器示例（需要根据实际页面调整）
        #
        # 示例1: 静态表格
        # table = soup.find("table", class_="xxx-table")
        # for row in table.find_all("tr")[1:]:
        #     cols = row.find_all("td")
        #     specialty_id = cols[0].text.strip()
        #     name = cols[1].text.strip()
        #     ...
        #
        # 示例2: 列表项
        # for item in soup.select(".specialty-item"):
        #     specialty_id = item.get("data-id")
        #     name = item.select_one(".name").text.strip()
        #     ...

        return specialties

    def get_specialty_detail(self, specialty_id: str) -> Optional[Specialty]:
        """获取专业详情"""
        url = config.SPECIALTY_DETAIL_URL.format(id=specialty_id)
        response = self._request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        # TODO: 实现详情页解析逻辑
        # 需要根据实际页面结构提取以下信息：
        # - 专业名称
        # - 专业介绍
        # - 培养目标
        # - 主干课程
        # - 就业方向

        specialty = Specialty(
            specialty_id=specialty_id,
            name="",
            level="",
            category="",
            more_info_url=url
        )

        return specialty

    def get_specialty_schools(self, specialty_id: str) -> List[SchoolSpecialty]:
        """获取开设某专业的院校列表"""
        url = config.SPECIALTY_SCHOOLS_URL.format(id=specialty_id)
        response = self._request(url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, "lxml")

        schools = []

        # TODO: 实现院校列表解析逻辑
        # 示例：
        # for row in soup.select("table.school-list tr"):
        #     school = SchoolSpecialty(
        #         specialty_id=specialty_id,
        #         school_name=row.select_one(".school-name").text.strip(),
        #         ...
        #     )
        #     schools.append(school)

        return schools

    def scrape_all(self, level: str = None) -> Dict[str, List[Dict]]:
        """
        爬取所有专业信息

        Args:
            level: 筛选层次，"本科" 或 "专科"，None 表示全部

        Returns:
            {
                "specialties": [专业信息列表],
                "schools": [院校专业开设信息列表]
            }
        """
        result = {
            "specialties": [],
            "schools": [],
            "scrape_time": datetime.now().isoformat()
        }

        # 1. 获取专业目录
        print("正在获取专业目录...")
        catalog = self.get_specialty_catalog()

        if level:
            catalog = [item for item in catalog if item.get("level") == level]

        print(f"找到 {len(catalog)} 个专业")

        # 2. 遍历每个专业，获取详情和开设院校
        for idx, item in enumerate(catalog, 1):
            specialty_id = item.get("id")
            print(f"[{idx}/{len(catalog)}] 正在爬取专业 {specialty_id}...")

            # 获取专业详情
            specialty = self.get_specialty_detail(specialty_id)
            if specialty:
                result["specialties"].append(specialty.to_dict())

            # 获取开设院校
            schools = self.get_specialty_schools(specialty_id)
            result["schools"].extend([s.to_dict() for s in schools])

        return result

    def save_data(self, data: Dict, filename: str):
        """保存数据到 JSON 文件"""
        import os
        os.makedirs(config.DATA_DIR, exist_ok=True)

        filepath = os.path.join(config.DATA_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"数据已保存到: {filepath}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="阳光高考专业信息爬虫")
    parser.add_argument("--all", action="store_true", help="爬取所有专业")
    parser.add_argument("--level", choices=["本科", "专科"], help="只爬取指定层次")
    parser.add_argument("--code", help="爬取指定专业代码")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="输出格式")

    args = parser.parse_args()

    scraper = GaokaoScraper()

    if args.code:
        # 爬取单个专业
        print(f"正在爬取专业 {args.code}...")
        specialty = scraper.get_specialty_detail(args.code)
        if specialty:
            data = {
                "specialties": [specialty.to_dict()],
                "scrape_time": datetime.now().isoformat()
            }
            scraper.save_data(data, f"specialty_{args.code}.json")
        else:
            print("获取失败")
    else:
        # 爬取所有或按层次筛选
        data = scraper.scrape_all(level=args.level)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if args.format == "json":
            scraper.save_data(data, f"specialties_{timestamp}.json")
        elif args.format == "csv":
            # 导出为 CSV
            import pandas as pd
            import os
            os.makedirs(config.DATA_DIR, exist_ok=True)

            specialty_df = pd.DataFrame(data["specialties"])
            school_df = pd.DataFrame(data["schools"])

            specialty_file = os.path.join(config.DATA_DIR, f"specialties_{timestamp}.csv")
            school_file = os.path.join(config.DATA_DIR, f"schools_{timestamp}.csv")

            specialty_df.to_csv(specialty_file, index=False, encoding="utf-8-sig")
            school_df.to_csv(school_file, index=False, encoding="utf-8-sig")

            print(f"专业信息已保存到: {specialty_file}")
            print(f"院校信息已保存到: {school_file}")


if __name__ == "__main__":
    main()
