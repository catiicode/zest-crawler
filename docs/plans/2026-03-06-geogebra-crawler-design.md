# GeoGebra Resource Crawler - Design Document

**Date**: 2026-03-06
**Project**: zest-crawler

## 1. Overview

zest-crawler 是一个 Python CLI 工具，用于自动下载 GeoGebra 平台上的教育资源。支持从资源合集（Book）、用户主页、单个资源页面批量下载 .ggb 文件并导出元数据。

## 2. Goals

- 自动化 GeoGebra 资源的发现和下载
- 支持三种输入类型：资源合集页面、用户主页、单个资源页面
- 导出元数据为 CSV 格式
- CLI 优先，后续可扩展为 Web 界面
- 后续可扩展：关键字搜索下载

## 3. Technical Stack

| 技术 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.12+ | 爬虫生态最丰富 |
| HTTP 客户端 | httpx (async) | 异步支持好，用于文件下载 |
| 浏览器自动化 | Playwright | SPA 页面解析，API 请求拦截 |
| CLI 框架 | click | 成熟稳定，支持子命令 |
| 包管理 | uv + pyproject.toml | 现代 Python 工具链 |
| 数据模型 | dataclass | 标准库，简洁够用 |

## 4. Architecture

```
┌─────────────────────────────────────────────────┐
│                   CLI (click)                    │
│  zest-crawler <url>  |  zest-crawler search <kw> │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              URL Router / Dispatcher             │
│  识别 URL 类型: /m/<id> | /u/<user> | 单个资源    │
└──────────┬───────────┬──────────────┬───────────┘
           │           │              │
    ┌──────▼──┐  ┌─────▼────┐  ┌─────▼────┐
    │ Book    │  │ User     │  │ Single   │
    │ Crawler │  │ Crawler  │  │ Crawler  │
    └────┬────┘  └────┬─────┘  └────┬─────┘
         │            │              │
┌────────▼────────────▼──────────────▼────────────┐
│            Page Analyzer (Playwright)            │
│  - 打开页面，拦截 XHR 请求                        │
│  - 提取资源列表（ID、标题、类型）                   │
│  - 处理分页/滚动加载                              │
└──────────────────────┬──────────────────────────┘
                       │ 资源列表
┌──────────────────────▼──────────────────────────┐
│           Downloader (httpx async)               │
│  - 并发下载 .ggb 文件                             │
│  - 并发限流 (Semaphore, 默认 5)                   │
│  - 重试机制                                      │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Storage / Output                    │
│  output/                                         │
│  ├── <book-name>/                                │
│  │   ├── metadata.csv                            │
│  │   ├── 01-<title>.ggb                          │
│  │   └── 02-<title>.ggb                          │
│  └── <user-name>/                                │
│      ├── metadata.csv                            │
│      └── ...                                     │
└─────────────────────────────────────────────────┘
```

## 5. Project Structure

```
zest-crawler/
├── pyproject.toml              # 项目配置、依赖管理
├── src/
│   └── zest_crawler/
│       ├── __init__.py
│       ├── cli.py              # CLI 入口 (click)
│       ├── router.py           # URL 类型识别与分发
│       ├── analyzer.py         # Playwright 页面解析 + API 拦截
│       ├── downloader.py       # httpx 异步下载器 (带限流)
│       ├── storage.py          # 文件存储 + CSV 元数据
│       └── models.py           # 数据模型 (dataclass)
├── tests/
│   └── ...
└── output/                     # 默认输出目录
```

## 6. Module Details

### 6.1 cli.py - CLI 入口

基于 click 框架，提供以下命令：

```bash
# 下载资源（自动识别 URL 类型）
zest-crawler download <url> [-o OUTPUT_DIR] [-c CONCURRENCY]

# 后续扩展：关键字搜索
zest-crawler search <keyword> [-o OUTPUT_DIR]
```

参数：
- `url`: GeoGebra 资源 URL
- `-o, --output`: 输出目录，默认 `./output`
- `-c, --concurrency`: 并发下载数，默认 5

### 6.2 router.py - URL 路由

通过正则匹配识别 URL 类型：

- `/m/<id>` → 可能是 Book（资源合集）或 Single（单个资源）
- `/u/<username>` → User（用户主页）

对于 `/m/<id>` 类型，需要通过 Playwright 解析页面后确认是 Book 还是 Single。

### 6.3 analyzer.py - 页面解析器

核心模块，使用 Playwright：

1. 启动无头浏览器
2. 注册网络请求拦截器（监听 XHR/Fetch）
3. 导航到目标 URL
4. 分析拦截到的 API 请求，提取资源列表
5. 对于用户主页，处理滚动加载/分页
6. 返回结构化的资源列表

### 6.4 downloader.py - 异步下载器

使用 httpx 异步客户端：

1. 接收资源列表
2. 使用 asyncio.Semaphore 控制并发（默认 5）
3. 下载 .ggb 文件，支持最多 3 次重试（指数退避）
4. 返回下载结果

已知下载 URL 模式：
```
https://www.geogebra.org/material/download/format/file/id/<MATERIAL_ID>
```

### 6.5 storage.py - 存储管理

负责：
- 创建输出目录结构
- 保存 .ggb 文件（按序号+标题命名）
- 写入 metadata.csv

### 6.6 models.py - 数据模型

```python
@dataclass
class GeoGebraResource:
    material_id: str
    title: str
    author: str
    resource_type: str  # activity, book, worksheet 等
    url: str
    filename: str       # 本地保存的文件名
    download_time: str  # ISO 格式时间戳
```

## 7. metadata.csv Format

```csv
material_id,title,author,resource_type,url,filename,download_time
abc123,三角函数演示,mengbaoxing,activity,https://www.geogebra.org/m/abc123,01-三角函数演示.ggb,2026-03-06T10:30:00
```

## 8. Error Handling

- **网络超时/失败**: httpx 重试机制（最多 3 次，指数退避）
- **资源不存在**: 记录错误日志，跳过继续处理下一个
- **页面结构变化**: Playwright 解析失败时给出明确错误提示
- **并发限流**: asyncio.Semaphore 防止触发反爬

## 9. Future Extensions

- **关键字搜索下载**: `zest-crawler search "三角函数"`
- **Web UI**: 基于 FastAPI/Gradio 的可视化界面
- **更多资源类型**: 分类浏览、主题浏览等
- **去重/增量下载**: 基于 material_id 避免重复下载

## 10. Key Technical Notes

- GeoGebra 是 SPA（单页应用），内容通过 JavaScript 动态加载
- .ggb 文件本质是 ZIP 压缩包，包含 geogebra.xml + 缩略图
- GeoGebra 没有公开的 Materials REST API 文档
- 需要通过 Playwright 拦截网络请求来发现实际的 API 端点
- GeoGebra 资源在非商业用途下可自由复制和分发
