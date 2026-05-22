# papercli translate

将 arXiv 或本地 LaTeX 论文翻译为目标语言的双语 PDF，保留全部数学公式与 LaTeX 排版。

## 使用方式

```bash
python run.py translate --input <arxiv-id|arxiv-url|本地目录|.tar.gz> [选项]
```

### 示例

```bash
# 通过 arXiv ID 翻译
python run.py translate --input 2307.16789

# 通过完整 arXiv URL 翻译
python run.py translate --input https://arxiv.org/abs/2307.16789

# 翻译本地 LaTeX 目录
python run.py translate --input tex/arXiv-2511.05271v4

# 翻译本地 .tar.gz 压缩包
python run.py translate --input tex/paper.tar.gz

# 指定模型
python run.py translate --input 2307.16789 --model gpt-4.1-mini

# 翻译为日语
python run.py translate --input 2307.16789 --target_lang Japanese

# debug 模式（无需 API，快速测试流程）
python run.py translate --input 2307.16789 --model x

# 只编译不翻译（验证原始论文能否正常编译）
python run.py translate --input 2307.16789 --model en

# 断点续翻（复用上次缓存）
python run.py translate --input 2307.16789 --resume true

# 指定并发数
python run.py translate --input 2307.16789 --max_workers 20

# 强制使用 xelatex 编译
python run.py translate --input 2307.16789 --engine xelatex

# 在文档开头插入目录与图表列表
python run.py translate --input 2307.16789 --toc true

# 使用配置文件
python run.py translate --config_path papercli/translate/config/default.yaml --input 2307.16789
```

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--input` | *(必填)* | arXiv ID、arXiv URL、本地论文目录或 `.tar.gz` 压缩包路径 |
| `--model` | `gpt-4.1-nano` | 翻译模型；填 `x`/`debug`/`none` 启用 debug 模式，填 `en` 仅编译不翻译 |
| `--provider` | `auto` | API 提供商：`auto`（自动检测）、`rightcode`、`blt` |
| `--target_lang` | `Chinese` | 目标语言，如 `Japanese`、`Korean`、`German`、`French`、`Spanish` |
| `--max_workers` | `30` | 最大并发 API 请求数，可根据 API 限速调整 |
| `--resume` | `false` | 断点续翻，跳过已缓存的段落 |
| `--engine` | *(自动检测)* | LaTeX 编译引擎：`xelatex` 或 `pdflatex`，留空自动选择 |
| `--toc` | `false` | 在 `\maketitle` 后插入目录（TOC）、表格列表（LOT）和图片列表（LOF） |

## 环境变量

| 变量 | 说明 |
|---|---|
| `MY_API_KEY` | blt / OpenAI 兼容服务的 API key |
| `MY_API_URL` | blt / OpenAI 兼容服务的 base URL（默认 `https://api.openai.com/v1/chat/completions`） |
| `RIGHTCODE_API` | right.codes 服务的 API key（设置后自动切换到该提供商） |
| `RIGHTCODE_URL` | right.codes 的 base URL（默认 `https://www.right.codes/codex/v1`） |

`provider=auto` 时：若 `RIGHTCODE_API` 已设置则优先使用 rightcode，否则使用 `MY_API_KEY`。

## 输入格式

| 格式 | 示例 | 说明 |
|------|------|------|
| arXiv ID | `2307.16789` | 下载最新版本 |
| 带版本号 | `2307.16789v2` | 下载指定版本 |
| abs URL | `https://arxiv.org/abs/2307.16789` | 从摘要页提取 ID |
| pdf URL | `https://arxiv.org/pdf/2307.16789` | 从 PDF 链接提取 ID |
| 本地目录 | `tex/arXiv-xxx` | 直接处理本地目录 |
| 压缩包 | `tex/arXiv-xxx.tar.gz` | 先解压再处理 |

## 输出位置

翻译结果写入原论文目录同级的新目录中：

```
tex/
  2307.16789/               # 原始 LaTeX 源码
  2307.16789_bilingual/     # 翻译后源码 + 生成的双语 PDF
    2307.16789.pdf
    .translations/          # 段落翻译缓存（用于断点续翻）
```

英文仅编译模式（`--model en`）输出目录后缀为 `_compiled`。

macOS 下生成 PDF 后会自动在 Finder 中打开输出目录。

## 工作流程

1. 若输入为 arXiv ID 或 URL，自动下载并解压源码包到 `tex/` 目录。
2. 识别主 `.tex` 文件（含 `\documentclass` 的文件）及所有 `\input`/`\include` 子文件。
3. 解析各文件，提取可翻译段落，屏蔽数学公式、引用、宏命令等不可翻译内容。
4. 并发调用翻译 API，已翻译段落从磁盘缓存读取（支持断点续翻）。
5. 将译文重新拼回 LaTeX 源文件，并注入 CJK 字体支持（针对目标语言自动配置）。
6. 自动检测或按指定引擎（XeLaTeX / pdfLaTeX）编译生成 PDF；编译失败时自动安装缺失宏包、修复字体问题并重试。

## 编译引擎选择

工具会分析源文件中的宏包使用情况自动选择引擎：

- **XeLaTeX**（默认）：支持 Unicode 与 CJK 字体，适合大多数现代论文。
- **pdfLaTeX**：当检测到 `fontenc`、`inputenc` 等宏包时自动切换，兼容旧版论文。

若自动检测结果不理想，可通过 `--engine xelatex` 或 `--engine pdflatex` 强制指定。

## 翻译缓存

每个已翻译段落按内容哈希缓存到输出目录的 `.translations/` 下。再次运行同一篇论文时：

- 不加 `--resume`：重新复制源文件，但已有缓存仍可复用（缓存会在 reset 时保留）。
- 加 `--resume true`：直接跳过已缓存段落，仅翻译新增或变更内容，大幅节省 API 用量。

## 配置文件

默认配置位于 `papercli/translate/config/default.yaml`，可直接修改其中的默认值，或通过 `--config_path` 指定自定义配置文件。命令行参数优先级高于配置文件。

## 手动编译 PDF

自动编译失败时，可在翻译输出目录中手动运行：

```bash
# XeLaTeX（推荐，中文支持更好）
latexmk -xelatex -bibtex -f -interaction=nonstopmode -file-line-error main.tex

# pdfLaTeX（兼容性更好）
latexmk -pdf -bibtex -f -interaction=nonstopmode -file-line-error main.tex
```

## 常见问题

**编译失败怎么办？**
查看终端错误信息。常见原因：字体缺失（程序自动添加回退方案）、包冲突（程序自动修复 subfigure/natbib/CJK 等冲突）、缺失包（程序自动安装）。XeLaTeX 失败时程序会询问是否切换到 pdfLaTeX。

**如何更换翻译 API？**
设置环境变量 `MY_API_URL`，需兼容 OpenAI 格式。

**翻译会修改原始文件吗？**
不会。原始文件保留在 `tex/{id}/`，所有修改都在 `tex/{id}_bilingual/` 中进行。

**翻译内容是否放在了新的段落？**
在 [papercli/translate/latex/parser.py](papercli/translate/latex/parser.py) 中修改。`final_parts.append(r"\par\trans{" + restored + "}")` 为新的段落，`final_parts.append(r"\\\trans{" + restored + "}")` 为同一个段落但是换行。
