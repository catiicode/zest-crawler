# zest-crawler

GeoGebra 资源批量下载工具。从 GeoGebra 的资源集合页、用户主页或单个资源页自动发现并下载 `.ggb` 文件，同时导出 CSV 格式的元数据。

## 工作原理

1. **页面分析** — 使用 Playwright 打开 GeoGebra 页面，从 DOM 中提取所有资源链接
2. **文件下载** — 逐个在 GeoGebra Classic 中打开资源，通过 `getBase64()` JS API 导出 `.ggb` 文件
3. **保存与记录** — 将文件保存到本地目录，并生成 `metadata.csv` 元数据文件

## 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) (推荐) 或 pip
- 网络环境需能访问 `www.geogebra.org`（如需代理见下方说明）

## 安装

### 1. 克隆项目

```bash
git clone <repo-url>
cd zest-crawler
```

### 2. 安装依赖

使用 uv（推荐）：

```bash
pip install uv          # 如果尚未安装 uv
uv sync                 # 安装运行时依赖
uv sync --extra dev     # 安装开发依赖（pytest 等）
```

或使用 pip：

```bash
pip install -e .            # 安装运行时依赖
pip install -e ".[dev]"     # 安装开发依赖
```

### 3. 安装 Playwright 浏览器

```bash
uv run playwright install chromium
# 或
playwright install chromium
```

## 使用说明

### 基本用法

```bash
uv run zest-crawler download <URL>
```

### 支持的 URL 类型

| 类型 | 格式 | 示例 |
|------|------|------|
| 资源集合 / Book | `https://www.geogebra.org/m/<id>` | `https://www.geogebra.org/m/wy53ufy2` |
| 用户主页 | `https://www.geogebra.org/u/<username>` | `https://www.geogebra.org/u/mengbaoxing` |
| 单个资源 | `https://www.geogebra.org/m/<id>` | `https://www.geogebra.org/m/gvu6wrmv` |
| 短链接 | `https://ggbm.at/<id>` | `https://ggbm.at/wy53ufy2` |

### 命令行选项

```
zest-crawler [--verbose/-v] download <URL> [选项]

选项:
  -o, --output PATH       输出目录 (默认: ./output)
  -c, --concurrency INT   最大并发下载数 (默认: 2)
  --headless / --no-headless  是否使用无头浏览器 (默认: headless)
  -p, --proxy URL         代理服务器地址
  -t, --timeout INT       页面加载超时时间，单位毫秒 (默认: 60000)
```

### 示例

下载资源集合（可视化浏览器窗口）：

```bash
uv run zest-crawler download https://www.geogebra.org/m/wy53ufy2 --no-headless
```

使用代理下载：

```bash
uv run zest-crawler download https://www.geogebra.org/m/wy53ufy2 --proxy http://127.0.0.1:7890
```

指定输出目录、显示详细日志：

```bash
uv run zest-crawler -v download https://www.geogebra.org/m/urufsydt -o ./downloads
```

降低并发避免连接被断开：

```bash
uv run zest-crawler download https://www.geogebra.org/m/urufsydt --concurrency 1
```

### 代理配置

如果无法直接访问 GeoGebra，有两种方式配置代理：

1. **命令行参数**：`--proxy http://127.0.0.1:7890`
2. **环境变量**：设置 `HTTPS_PROXY` 或 `HTTP_PROXY`，工具会自动检测

```bash
export HTTPS_PROXY=http://127.0.0.1:7890
uv run zest-crawler download https://www.geogebra.org/m/wy53ufy2
```

### 输出结构

```
output/
└── wy53ufy2/
    ├── 01-4的分与和.ggb
    ├── 02-5的分与和.ggb
    ├── 03-三个拼一拼.ggb
    ├── ...
    └── metadata.csv
```

`metadata.csv` 包含以下字段：

| 字段 | 说明 |
|------|------|
| `material_id` | GeoGebra 资源 ID |
| `title` | 资源标题 |
| `author` | 作者 |
| `resource_type` | 资源类型 (activity / book / worksheet) |
| `url` | 资源页面地址 |
| `filename` | 本地文件名 |
| `download_time` | 下载时间 (UTC) |

## 开发

### 运行测试

```bash
uv sync --extra dev
uv run pytest -v
```

### 项目结构

```
zest-crawler/
├── src/zest_crawler/
│   ├── __init__.py
│   ├── cli.py          # CLI 入口 (click)
│   ├── models.py       # 数据模型
│   ├── router.py       # URL 解析与路由
│   ├── analyzer.py     # Playwright 页面分析器
│   ├── downloader.py   # Playwright 文件下载器
│   └── storage.py      # 文件保存与 CSV 导出
├── tests/              # 单元测试
├── scripts/
│   └── debug_page.py   # 页面调试脚本
├── docs/plans/         # 设计文档
└── pyproject.toml
```

### 构建

```bash
uv build
# 或
pip install build && python -m build
```

构建产物位于 `dist/` 目录。
