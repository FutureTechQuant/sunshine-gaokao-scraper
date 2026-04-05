# 阳光高考专业信息爬虫

爬取 [阳光高考](https://gaokao.chsi.com.cn) 平台的高校专业信息，包括专业目录、开设院校、就业前景等数据。

## 功能

- 爬取本科/专科专业目录
- 爬取每个专业的详细介绍（培养目标、课程、就业方向等）
- 爬取开设该专业的院校列表
- 支持断点续爬
- 数据导出为 JSON / CSV

## 爬取的数据字段

### 专业信息
| 字段 | 说明 |
|------|------|
| specialty_id | 专业代码 |
| name | 专业名称 |
| level | 层次（本科/专科） |
| category | 学科门类 |
| description | 专业介绍 |
| training_objective | 培养目标 |
| main_courses | 主干课程 |
| employment_direction | 就业方向 |
| more_info_url | 详情页链接 |

### 开设院校
| 字段 | 说明 |
|------|------|
| specialty_id | 专业代码 |
| school_name | 院校名称 |
| school_id | 院校ID |
| province | 省份 |
| level | 办学层次 |
| feature | 办学特色 |

## 技术栈

- Python 3.10+
- requests + BeautifulSoup4（静态页面）
- Playwright（动态渲染页面，按需启用）
- GitHub Actions 定时运行

## 使用方法

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 爬取全部专业信息
python main.py --all

# 只爬取本科专业
python main.py --level 本科

# 爬取特定专业代码
python main.py --code 080901

# 导出为 CSV
python main.py --all --format csv
```

### GitHub Actions 自动运行

项目已配置 GitHub Actions workflow，每周自动运行一次，结果保存到 `data/` 目录。

## ⚠️ 免责声明

本项目仅供学习研究使用。请遵守阳光高考网站的使用条款和 robots.txt 规则，合理控制爬取频率，不要对目标网站造成过大压力。

## License

MIT
