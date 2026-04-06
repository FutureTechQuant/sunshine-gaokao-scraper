# 阿里云盾 WAF 绕过方案总结

## 问题描述

阳光高考网站（gaokao.chsi.com.cn）使用了**阿里云盾 WAF**（Web Application Firewall），会拦截自动化爬虫请求，返回 **HTTP 412 Precondition Failed**。

即使使用了以下反检测技术，仍然被拦截：
- ✅ Playwright 无头浏览器
- ✅ 完整的 WebDriver 隐藏脚本
- ✅ 真实浏览器指纹伪造
- ✅ Canvas/WebGL 指纹混淆
- ✅ 真实的 HTTP 请求头
- ✅ 随机延迟和人类行为模拟

## 测试结果

```
HTTP 状态码: 412
页面内容: <html><head></head><body></body></html>
```

这说明阿里云盾在 TLS 握手或更底层的协议层面就识别出了自动化请求。

## 阿里云盾检测机制

阿里云盾使用多层检测：

1. **TLS 指纹检测**：分析 TLS ClientHello 的特征
2. **HTTP/2 指纹检测**：检测 HTTP/2 帧的顺序和参数
3. **浏览器指纹检测**：Canvas、WebGL、字体等
4. **行为分析**：鼠标移动、滚动、点击模式
5. **IP 信誉检测**：数据中心 IP、代理 IP 等
6. **请求频率分析**：异常的请求模式

## 解决方案

### 方案 1：手动导入（推荐 ⭐）

**优点**：
- 100% 可靠
- 无需绕过 WAF
- 合法合规

**步骤**：
```bash
# 1. 生成模板
python main.py --template

# 2. 手动访问网站，复制数据到 data/template.json

# 3. 导入数据
python main.py --import data/template.json --format json
```

### 方案 2：使用住宅代理

**优点**：
- 可以自动化
- 成功率较高

**缺点**：
- 需要付费代理服务（$50-200/月）
- 仍可能被检测

**推荐服务**：
- Bright Data (Luminati)
- Smartproxy
- Oxylabs

**配置方法**：
编辑 `config.py`：
```python
PROXY_HTTP = "http://username:password@proxy-server:port"
PROXY_HTTPS = "http://username:password@proxy-server:port"
```

### 方案 3：使用官方 API

**优点**：
- 最可靠
- 合法合规
- 数据质量最高

**步骤**：
联系学信网（chsi.com.cn）申请官方数据接口。

### 方案 4：降低频率 + 真实浏览器

**优点**：
- 成本低
- 可能绕过部分检测

**缺点**：
- 效率低
- 仍可能失败

**方法**：
- 使用非 headless 模式（`headless=False`）
- 增加随机延迟（10-30 秒）
- 模拟真实用户行为（滚动、点击）
- 使用住宅 IP

## 当前实现

项目已实现：

1. ✅ **自动检测 WAF**：检测到 412 时自动提示
2. ✅ **手动导入模式**：提供模板和导入功能
3. ✅ **增强反检测**：Playwright + 多层反检测脚本
4. ✅ **GitHub Actions 集成**：自动运行，失败时创建 Issue
5. ✅ **详细文档**：README 中说明了所有方案

## 技术细节

### 已实现的反检测措施

```javascript
// 1. 隐藏 webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// 2. 伪造 Chrome 对象
window.chrome = { runtime: {}, loadTimes: function() {}, ... };

// 3. 伪造 plugins、languages、platform
// 4. Canvas 指纹混淆
// 5. WebGL 指纹伪造
```

### 为什么仍然被拦截？

阿里云盾可能使用了：
- **TLS 指纹**：Playwright 的 TLS 握手与真实 Chrome 不同
- **HTTP/2 指纹**：帧顺序、窗口大小等参数
- **时序分析**：页面加载时间、资源请求顺序
- **IP 信誉**：GitHub Actions 的 IP 被标记为数据中心 IP

## 建议

对于学习和研究目的：
1. **优先使用手动导入模式**（方案 1）
2. 如需自动化，考虑付费代理服务（方案 2）
3. 对于生产环境，申请官方 API（方案 3）

## 法律提示

- 绕过 WAF 可能违反网站服务条款
- 未经授权的爬虫可能违反《网络安全法》
- 建议优先使用官方 API 或手动导入方式
- 本项目仅供学习研究使用

## 参考资料

- [阿里云 WAF 官方文档](https://help.aliyun.com/product/28515.html)
- [TLS 指纹检测原理](https://tlsfingerprint.io/)
- [Playwright Stealth Plugin](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth)
- [学信网官网](https://www.chsi.com.cn/)

## 更新日志

- **2026-04-06**：完成 Playwright 反检测实现，确认阿里云盾仍然拦截
- **2026-04-06**：添加手动导入模式作为主要解决方案
- **2026-04-06**：更新 GitHub Actions workflow，添加失败处理
