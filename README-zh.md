# LaTeX 论文翻译工具

将 arXiv 论文的 LaTeX 源文件翻译为中英双语 PDF。

## 功能特性

- **arXiv 自动下载**：支持 arXiv ID 或 URL，自动下载源文件
- **智能文件解析**：递归解析 `\input{}` 和 `\include{}`，自动发现所有需要翻译的文件
- **选择性翻译**：跳过 preamble/config 文件，只翻译正文内容
- **保留原文**：翻译以灰色小字显示在原文下方，方便对照阅读
- **自动修复冲突**：处理常见的 LaTeX 包冲突（subfigure/subcaption、natbib、CJK 等）
- **智能引擎选择**：默认使用 XeLaTeX（更好的中文支持），失败时可交互式切换到 pdfLaTeX
- **缺失包自动安装**：编译时自动检测并安装缺失的 LaTeX 包
- **arXiv 元数据水印**：自动获取 arXiv 论文的发布日期和分类，添加到 PDF 右上角
- **目录生成**：可选添加目录（TOC）、表格列表（LOT）、图片列表（LOF）
- **断点续翻**：支持中断后继续翻译，复用已缓存的结果

## 快速开始

### 安装

#### 1. Python 依赖

```bash
pip install -r requirements.txt
```

或手动安装：
```bash
pip install requests tqdm draccus
```

#### 2. LaTeX 编译器

推荐使用 TinyTeX（轻量级 LaTeX 发行版）：

```bash
# 安装 TinyTeX
curl -sL "https://yihui.org/tinytex/install-bin-unix.sh" | sh

# 安装基础中文支持包
tlmgr install cjk ctex xecjk fontspec
```

> **注意**：缺失的包会在编译时自动安装，无需手动处理。

#### 3. 环境变量

```bash
# 翻译 API Key（必需，除非使用测试模式）
export ONE_API="your-api-key"

# 自定义 API 地址（可选）
export API_URL="https://api.bltcy.ai/v1/chat/completions"
```

### 基本用法

```bash
# 从 arXiv 下载并翻译（推荐）
python translate.py --input 2307.16789

# 指定 arXiv 版本
python translate.py --input 2307.16789v2

# 使用 arXiv URL
python translate.py --input https://arxiv.org/abs/2307.16789

# 翻译本地目录
python translate.py --input tex/arXiv-2511.05271v4

# 翻译本地压缩包
python translate.py --input tex/paper.tar.gz
```

## 常用选项

### 测试模式（不调用 API）

```bash
python translate.py --input 2307.16789 --model x
```

### 自定义翻译模型

```bash
python translate.py --input 2307.16789 --model gpt-4.1-mini
```

### 断点续翻

```bash
# 首次翻译（中途中断）
python translate.py --input 2307.16789

# 继续翻译（复用缓存）
python translate.py --input 2307.16789 --resume true
```

### 调整并发数

```bash
# 降低并发（API 限流严格时）
python translate.py --input 2307.16789 --max_workers 10

# 提高并发（默认 30）
python translate.py --input 2307.16789 --max_workers 50
```

### 指定 LaTeX 引擎

```bash
# 自动选择（默认）：优先 XeLaTeX，失败时可选 pdfLaTeX
python translate.py --input 2307.16789 --engine auto

# 强制使用 XeLaTeX
python translate.py --input 2307.16789 --engine xelatex

# 强制使用 pdfLaTeX
python translate.py --input 2307.16789 --engine pdflatex
```

### 目录和列表

```bash
# 添加目录和图表列表（默认启用）
python translate.py --input 2307.16789 --toc true

# 不添加目录
python translate.py --input 2307.16789 --toc false
```

## 输入格式

| 格式 | 示例 | 说明 |
|------|------|------|
| arXiv ID | `2307.16789` | 下载最新版本 |
| 带版本号 | `2307.16789v2` | 下载指定版本 |
| abs URL | `https://arxiv.org/abs/2307.16789` | 从摘要页面提取 ID |
| pdf URL | `https://arxiv.org/pdf/2307.16789` | 从 PDF 链接提取 ID |
| src URL | `https://arxiv.org/src/2307.16789` | 从源文件链接提取 ID |
| 本地目录 | `tex/arXiv-xxx` | 直接处理本地目录 |
| 压缩包 | `tex/arXiv-xxx.tar.gz` | 先解压再处理 |

## 输出结构

```
tex/
├── arXiv-2307.16789v2.tar.gz      # 下载的源文件
├── arXiv-2307.16789v2/            # 解压后的原始文件
└── arXiv-2307.16789v2_bilingual/  # 翻译输出
    ├── .translations/             # 翻译缓存（断点续翻）
    ├── main.tex                   # 添加了翻译的 LaTeX
    ├── sections/*.tex             # 翻译后的章节文件
    └── main.pdf                   # 最终双语 PDF ✓
```

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | (必填) | 输入源：arXiv ID、URL、本地目录或压缩包 |
| `--model` | `gpt-5-nano` | 翻译模型，使用 `x` 启用测试模式 |
| `--max_workers` | `30` | 最大并发 API 请求数 |
| `--resume` | `false` | 断点续翻，复用已缓存的翻译 |
| `--engine` | `auto` | LaTeX 引擎：`auto`、`xelatex`、`pdflatex` |
| `--toc` | `true` | 在文档末尾添加目录和图表列表（TOC/LOT/LOF） |

## 翻译示例

翻译后的 LaTeX 格式：

```latex
Large Language Models (LLMs) have emerged as a pivotal
breakthrough in natural language processing (NLP).

\trans{大型语言模型（LLMs）已成为自然语言处理（NLP）领域的重要突破。}

\begin{figure}
    \caption{Overview of our approach.}
    \trans{我们方法的概览。}
\end{figure}
```

PDF 显示效果：
- **原文**：正常黑色，正常大小
- **翻译**：灰色小字，显示在原文下方

## 常见问题

### Q: 编译失败怎么办？

查看终端输出的错误信息。常见原因：

- **字体缺失**（pdfLaTeX）：程序会自动添加字体回退方案
- **包冲突**：程序会自动修复常见冲突（subfigure/natbib/CJK）
- **缺失包**：程序会自动安装缺失的 LaTeX 包

如果 XeLaTeX 编译失败，程序会询问是否尝试 pdfLaTeX。

### Q: 如何更换翻译 API？

设置环境变量 `API_URL`，API 需兼容 OpenAI 格式：

```bash
export API_URL="https://your-api-endpoint/v1/chat/completions"
```

### Q: 翻译会修改原始文件吗？

不会。原始文件保留在 `tex/arXiv-{id}/` 目录，所有修改都在 `tex/arXiv-{id}_bilingual/` 目录进行。

### Q: 断点续翻如何工作？

翻译缓存保存在 `.translations/` 目录，基于段落内容的 hash 匹配。使用 `--resume true` 时：
- 保留缓存目录
- 重新解析源文件
- 跳过已缓存的段落
- 只翻译新增或修改的段落

### Q: 如何自定义跳过某些文件？

修改 `translator/processor.py` 中的 `is_preamble_file()` 函数，添加文件名模式。

## 技术文档

详细的实现原理和技术细节请参考：

- **[实现细节](docs/IMPLEMENTATION.md)** - 架构、工作流程、翻译规则、自动修复机制
- **[Bug 记录](docs/bugs.md)** - 已修复的问题和新功能

## 许可证

Apache License 2.0

## 反馈与贡献

欢迎提交 Issue 和 Pull Request！
