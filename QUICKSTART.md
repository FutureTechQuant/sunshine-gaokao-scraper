# 快速开始指南

## 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/sunshine-gaokao-scraper.git
cd sunshine-gaokao-scraper

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器（可选）
python -m playwright install chromium
```

## 使用方法

### 方法 1：手动导入（推荐）

由于阿里云盾 WAF 的强力防护，推荐使用手动导入模式：

```bash
# 1. 生成数据模板
python main.py --template

# 2. 编辑 data/template.json，填入从网站手动收集的数据

# 3. 导入数据
python main.py --import data/template.json --format json
```

### 方法 2：尝试自动爬取

```bash
# 自动检测并尝试爬取（可能失败）
python main.py --all --format json

# 强制使用 Playwright 模式
python main.py --mode playwright --all --format json
```

**注意**：由于 WAF 拦截，自动爬取很可能返回 HTTP 412 错误。

## 数据模板格式

`data/template.json` 示例：

```json
{
  "specialties": [
    {
      "specialty_id": "080901",
      "name": "计算机科学与技术",
      "level": "本科",
      "category": "工学",
      "description": "本专业培养具有良好的科学素养...",
      "training_objective": "培养掌握计算机科学与技术基本理论...",
      "main_courses": "高等数学、线性代数、数据结构、算法设计...",
      "employment_direction": "软件开发、系统架构、网络安全、人工智能..."
    }
  ],
  "schools": [
    {
      "specialty_id": "080901",
      "school_name": "清华大学",
      "school_id": "10001",
      "province": "北京",
      "level": "本科",
      "feature": "双一流、985、211"
    }
  ]
}
```

## 输出格式

### JSON 格式（默认）

```bash
python main.py --import data/template.json --format json
```

输出：`data/specialties_YYYYMMDD_HHMMSS.json`

### CSV 格式

```bash
python main.py --import data/template.json --format csv
```

输出：
- `data/specialties_YYYYMMDD_HHMMSS.csv`
- `data/schools_YYYYMMDD_HHMMSS.csv`

## 常见问题

### Q: 为什么返回 HTTP 412？

A: 阳光高考网站使用阿里云盾 WAF，会拦截自动化请求。请使用手动导入模式。

### Q: 如何手动收集数据？

A: 
1. 访问 https://gaokao.chsi.com.cn/zyk/zybk/
2. 浏览专业列表
3. 复制专业信息到 `data/template.json`
4. 运行导入命令

### Q: 可以使用代理吗？

A: 可以。编辑 `config.py`：

```python
PROXY_HTTP = "http://your-proxy:port"
PROXY_HTTPS = "http://your-proxy:port"
```

然后运行：
```bash
python main.py --mode playwright --all --format json
```

## GitHub Actions

项目已配置自动运行，每周日 11:00 UTC 执行。

如果爬取失败，会自动创建 Issue 提醒。

## 更多信息

- 详细文档：[README.md](README.md)
- WAF 绕过方案：[SOLUTION.md](SOLUTION.md)
- 问题反馈：[GitHub Issues](https://github.com/your-username/sunshine-gaokao-scraper/issues)
