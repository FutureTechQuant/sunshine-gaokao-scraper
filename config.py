# 阳光高考爬虫配置

# 请求间隔（秒），控制爬取频率，避免被封
REQUEST_DELAY = 2

# 单个页面超时时间（秒）
REQUEST_TIMEOUT = 30

# 最大重试次数
MAX_RETRIES = 3

# User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 数据存储路径
DATA_DIR = "data"

# 专业目录页 URL
SPECIALTY_CATALOG_URL = "https://gaokao.chsi.com.cn/zyk/zybk/catalog.shtml"

# 专业详情页模板（{code} 为专业代码）
SPECIALTY_DETAIL_URL = "https://gaokao.chsi.com.cn/zyk/zybk/specialtyDetail.action?specialtyId={id}"

# 专业开设院校页模板
SPECIALTY_SCHOOLS_URL = "https://gaokao.chsi.com.cn/zyk/zybk/schoolSpecialty.action?specialtyId={id}"

# 代理设置（可选，留空则不使用代理）
# PROXY_HTTP = "http://127.0.0.1:7890"
# PROXY_HTTPS = "http://127.0.0.1:7890"
PROXY_HTTP = ""
PROXY_HTTPS = ""
