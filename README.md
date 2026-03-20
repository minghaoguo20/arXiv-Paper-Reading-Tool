# LaTeX 论文翻译工具

中文 | [English](README_EN.md)

将 arXiv 论文的 LaTeX 源文件翻译为中英双语 PDF。

## 功能特性

- **arXiv 自动下载**：支持 arXiv ID 或 URL，自动下载源文件
- **智能文件解析**：递归解析 `\input{}` 和 `\include{}`，自动发现所有需要翻译的文件
- **选择性翻译**：跳过 preamble/config 文件，只翻译正文内容
- **保留原文**：翻译以灰色小字显示在原文下方，方便对照阅读
- **自动修复冲突**：处理常见的 LaTeX 包冲突（subfigure/subcaption、natbib、CJK 等）
- **XeTeX 编译**：使用 tectonic 编译，自动下载所需宏包，原生支持中文

## 安装

### 系统依赖

```bash
# macOS
brew install tectonic
```

### Python 依赖

```bash
pip install requests tqdm draccus
```

### 环境变量

```bash
# 翻译 API Key（必需，除非使用 --model x 测试模式）
export ONE_API="your-api-key"

# 自定义 API 地址（可选，默认 https://api.bltcy.ai/v1/chat/completions）
export API_URL="https://your-api-endpoint/v1/chat/completions"
```

## 使用方法

```bash
# arXiv ID（自动下载最新版本）
python translate.py --input 2307.16789

# 指定版本
python translate.py --input 2307.16789v1

# arXiv URL（支持 abs/pdf/src/html）
python translate.py --input https://arxiv.org/abs/2307.16789
python translate.py --input https://arxiv.org/pdf/2307.16789

# 本地压缩包
python translate.py --input tex/arXiv-2307.16789.tar.gz

# 本地目录
python translate.py --input tex/arXiv-2307.16789v2

# Debug 模式（不调用 API，使用 mock 翻译）
python translate.py --input 2307.16789 --model x

# 自定义模型
python translate.py --input 2307.16789 --model gpt-4.1-mini

# 断点续翻（中断后继续，复用缓存）
python translate.py --input 2307.16789 --resume true

# 调整并发数（默认 10）
python translate.py --input 2307.16789 --max_workers 20

# 查看帮助
python translate.py --help
```

## 输入格式

| 格式 | 示例 | 说明 |
|------|------|------|
| arXiv ID | `2307.16789` | 下载最新版本 |
| 带版本号 | `2307.16789v2` | 下载指定版本 |
| abs URL | `https://arxiv.org/abs/2307.16789` | 从 abs 页面提取 ID |
| pdf URL | `https://arxiv.org/pdf/2307.16789` | 从 pdf 链接提取 ID |
| src URL | `https://arxiv.org/src/2307.16789` | 从源文件链接提取 ID |
| 本地目录 | `tex/arXiv-xxx` | 直接处理本地目录 |
| 压缩包 | `tex/arXiv-xxx.tar.gz` | 先解压再处理 |

## 输出结构

```
tex/
├── arXiv-2307.16789v2.tar.gz      # 下载的源文件
├── arXiv-2307.16789v2/            # 解压后的原始文件
└── arXiv-2307.16789v2_bilingual/  # 翻译输出
    ├── .translations/             # 翻译缓存（用于断点续翻）
    │   ├── a1b2c3d4e5f6.txt       # 段落 hash → 翻译内容
    │   └── ...
    ├── main.tex                   # 添加了翻译的 LaTeX
    ├── sections/*.tex             # 翻译后的章节文件
    └── main.pdf                   # 最终双语 PDF
```

## 工作流程

```
输入 (ID/URL/目录/压缩包)
    ↓
[arXiv 下载] → tex/arXiv-{id}.tar.gz
    ↓
[解压] → tex/arXiv-{id}/
    ↓
[复制] → tex/arXiv-{id}_bilingual/
    ↓
[修复包冲突] subfigure/subcaption, natbib, CJK
    ↓
[添加中文支持] xeCJK, fontspec, \trans{} 命令
    ↓
[解析文件] 从主文件递归查找 \input{} 和 \include{}
    ↓
[全局并行翻译] 三阶段处理（见下文）
    ↓
[编译] tectonic → PDF
    ↓
[打开] 自动打开生成的 PDF
```

### 全局并行翻译架构

采用「全局并行」策略，所有文件的所有段落一起并发翻译：

```
阶段1: 解析
├── 解析 main.tex
├── 解析 section1.tex
├── 解析 section2.tex
└── 收集全部段落任务 → [task_0, task_1, ..., task_83]

阶段2: 翻译
└── batch_translate([所有段落]) → 一次性并发（受 max_workers 限制）

阶段3: 组装
├── 将翻译结果分发回 main.tex
├── 将翻译结果分发回 section1.tex
└── 将翻译结果分发回 section2.tex
```

优势：
- **更快**：7 个文件只需 1 轮网络往返，而非 7 轮
- **更高效**：所有段落统一调度，不会被单个文件的慢段落阻塞
- **断点续翻友好**：缓存基于段落内容 hash，与文件结构无关

## 翻译规则

### 翻译的内容
- 正文段落（空行分隔）
- 章节标题后的内容
- 图表标题 `\caption{...}`
- itemize/enumerate 列表项

### 跳过的内容
- Preamble（`\begin{document}` 之前）
- 数学环境（equation, align, gather）
- 代码块（lstlisting, verbatim）
- 表格内容（tabular）
- 算法环境（algorithm）
- 配置文件（config.tex, macro.tex 等）
- 纯 LaTeX 命令行

### 保留不翻译
- 行内数学公式 `$...$`
- 引用 `\cite{}`、`\ref{}`
- LaTeX 命令结构

## 自动修复的问题

| 问题 | 解决方案 |
|------|----------|
| subfigure/subcaption 冲突 | 注释 subfigure（保留 subcaption） |
| natbib + unsrt 不兼容 | 添加 `[numbers]` 选项 |
| CJK/CJKutf8 与 xeCJK 冲突 | 注释旧包，移除 CJK 环境 |
| hyperref pdftex 驱动错误 | 添加 `\PassOptionsToPackage{xetex}{hyperref}` |
| 字体不支持 XeTeX | 使用 fontspec 设置系统字体 |

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | (必填) | 输入源：arXiv ID、URL、本地目录或压缩包 |
| `--model` | `gpt-5-nano` | 翻译模型，使用 `x` 启用测试模式 |
| `--max_workers` | `10` | 最大并发 API 请求数 |
| `--resume` | `false` | 断点续翻，复用已缓存的翻译 |
| `--help` | - | 显示帮助信息 |

### 模型选项

- `gpt-5-nano` - 默认模型
- `gpt-4.1-mini` - 更强的模型
- `x` / `debug` / `none` - 测试模式，不调用 API，使用 mock 翻译

### 断点续翻

翻译过程中如果中断（网络错误、API 限流等），可以使用 `--resume true` 继续：

```bash
# 首次翻译（中途中断）
python translate.py --input 2307.16789

# 继续翻译（复用已完成的翻译）
python translate.py --input 2307.16789 --resume true
```

缓存机制：
- 每个段落翻译完成后立即保存到 `.translations/` 目录
- 基于段落内容的 hash 匹配，即使文件结构变化也能复用
- 输出示例：`Cached: 58, Pending: 6`（58 个已缓存，6 个待翻译）

### 并发控制

根据 API 限流情况调整并发数：

```bash
# 降低并发（API 限流严格时）
python translate.py --input 2307.16789 --max_workers 5

# 提高并发（API 限流宽松时）
python translate.py --input 2307.16789 --max_workers 20
```

## 文件说明

```
translation/
├── translate.py    # 主程序
├── bugs.md         # Bug 记录和修复历史
├── README.md       # 本文档（中文）
├── README_EN.md    # English documentation
└── tex/            # 论文目录（自动创建）
```

## 常见问题

### Q: 编译失败怎么办？
查看 tectonic 错误输出，常见原因：
- 缺少字体：确保系统有 Times New Roman、STHeiti
- 包冲突：检查是否有未处理的包冲突
- 语法错误：翻译可能引入了特殊字符

### Q: 如何跳过某些文件？
在 `is_preamble_file()` 函数中添加文件名模式。

### Q: 如何更换翻译 API？
设置环境变量 `API_URL`，需兼容 OpenAI API 格式。

### Q: 下载的文件保存在哪里？
所有文件保存在 `tex/` 目录下，包括：
- `arXiv-{id}.tar.gz` - 原始压缩包
- `arXiv-{id}/` - 解压后的源文件
- `arXiv-{id}_bilingual/` - 翻译输出

## 示例输出

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

PDF 中显示效果：原文为正常黑色，翻译为灰色小字。
