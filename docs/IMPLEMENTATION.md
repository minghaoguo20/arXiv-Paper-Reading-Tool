# LaTeX 论文翻译工具 - 实现细节

本文档详细说明翻译工具的技术实现、工作流程和内部机制。

## 目录

- [项目架构](#项目架构)
- [工作流程](#工作流程)
- [翻译规则](#翻译规则)
- [自动修复机制](#自动修复机制)
- [引擎选择与回退](#引擎选择与回退)
- [缺失包自动安装](#缺失包自动安装)
- [arXiv 元数据水印](#arxiv-元数据水印)
- [全局并行翻译架构](#全局并行翻译架构)
- [断点续翻机制](#断点续翻机制)

## 项目架构

```
translation/
├── translate.py              # 入口脚本
├── README-zh.md              # 用户文档
├── translator/
│   ├── cli.py                # 命令行配置（draccus）
│   ├── processor.py          # 主处理流程
│   ├── arxiv.py              # arXiv 下载/解压
│   ├── api.py                # 翻译 API 调用（并发）
│   ├── cache.py              # 翻译缓存（基于 hash）
│   └── latex/
│       ├── parser.py         # LaTeX 解析（段落提取）
│       ├── cjk.py            # CJK 支持注入
│       ├── engine.py         # 引擎检测 & 缺失包自动安装
│       └── fixes.py          # 包冲突修复
├── docs/                     # 技术文档
│   ├── IMPLEMENTATION.md     # 本文档
│   └── bugs.md               # Bug 记录
└── tex/                      # 论文目录（自动创建）
```

## 工作流程

完整的翻译流程分为以下阶段：

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
[添加目录] TOC/LOT/LOF（可选）
    ↓
[编译] XeLaTeX 优先 → 失败时询问是否尝试 pdfLaTeX → 自动安装缺失包
    ↓
[打开] 自动打开生成的 PDF
```

### 详细步骤

1. **输入解析** (`cli.py`)
   - 识别 arXiv ID/URL、本地目录或压缩包
   - 提取版本号（如 `2307.16789v2`）

2. **下载与解压** (`arxiv.py`)
   - 从 `https://arxiv.org/src/{arxiv_id}` 下载源文件
   - 检测压缩包结构，处理无顶层目录的情况

3. **预处理** (`processor.py`)
   - 复制到 `_bilingual` 目录
   - 检测并修复包冲突 (`fixes.py`)
   - 添加 CJK 支持 (`cjk.py`)

4. **文件发现** (`processor.py`)
   - 查找包含 `\documentclass` 的主文件
   - 递归解析 `\input{}` 和 `\include{}`
   - 跳过 preamble/config 文件

5. **并行翻译** (三阶段，见下文)

6. **编译与输出** (`latex/engine.py`)
   - 使用 latexmk 编译
   - 自动安装缺失的包
   - 处理字体回退（pdfLaTeX）

## 翻译规则

### 翻译的内容

- **正文段落**：空行分隔的文本块（≥ 30 字符）
- **章节标题**：`\section{...}`、`\subsection{...}` 等
- **图表标题**：`\caption{...}` 内容
- **列表项**：itemize/enumerate 环境中的 `\item` 内容

### 跳过的内容

- **Preamble**：`\begin{document}` 之前的所有内容
- **数学环境**：equation、align、gather、displaymath 等
- **代码块**：lstlisting、verbatim、minted 等
- **表格内容**：tabular 环境内部
- **算法环境**：algorithm、algorithmic 等
- **配置文件**：文件名包含 config/preamble/header/macro/setup
- **纯命令行**：如 `\vspace`、`\newpage`、`\clearpage` 等
- **过短文本**：少于 30 字符的文本块

判断 preamble 文件的逻辑（`processor.py:is_preamble_file`）：
```python
# 按文件名跳过
if any(skip in name for skip in ["config", "preamble", "header", "macro", "command", "setup"]):
    return True

# 按内容跳过：如果 >50% 是 preamble 命令
preamble_cmds = \usepackage, \RequirePackage, \def, \newcommand, \renewcommand, \setlength, \definecolor
if preamble_cmds / total_lines > 0.5:
    return True
```

### 保留不翻译

翻译时使用**占位符保护**机制（`parser.py:clean_for_translation`）：

1. **行内数学公式**
   - `$...$` → `[MATH_0]`
   - `\(...\)` → `[MATH_1]`

2. **引用命令**
   - `\cite{...}` → `[CITE_0]`
   - `\ref{...}` → `[REF_0]`
   - `\eqref{...}` → `[REF_1]`

3. **LaTeX 宏**
   - `\emph{...}` → `[MACRO_0]`
   - `\textbf{...}` → `[MACRO_1]`

翻译后通过 `refs_map` 还原：
```python
refs_map = {
    "[MATH_0]": "$E = mc^2$",
    "[CITE_0]": "\\cite{smith2024}",
    ...
}
```

## 自动修复机制

### 包冲突修复 (`latex/fixes.py`)

| 问题 | 检测 | 解决方案 |
|------|------|---------|
| subfigure/subcaption 冲突 | 同时存在两个包 | 注释 `\usepackage{subfigure}` |
| natbib + unsrt 不兼容 | `\usepackage{natbib}` + `\bibliographystyle{unsrt}` | 添加 `[numbers]` 选项 |
| CJK/CJKutf8 与 xeCJK 冲突 | 旧式 CJK 包 | 注释旧包，移除 `\begin{CJK}...\end{CJK}` 环境 |

### 布局优化 (`latex/parser.py:sanitize_line`)

| 转换 | 原因 | 实现 |
|------|------|------|
| `wrapfigure` → `figure` | 文字环绕与翻译冲突 | `\begin{wrapfigure}{...}{...}` → `\begin{figure}[!ht]` |
| 移除负 vspace | 翻译增加内容导致重叠 | `\vspace{-10pt}` → `""` |

### 字体回退（pdfLaTeX）

当 pdfLaTeX 报告字体缺失时（`latex/engine.py:parse_missing_fonts`）：

```latex
% 检测错误：Font T1/ptm/m/n/10=ptmr7t at 10.0pt not loadable
% 自动添加回退：
\IfFileExists{ptm.sty}{}{
  \renewcommand{\rmdefault}{cmr}  % Computer Modern Roman
}
```

## 引擎选择与回退

### 引擎检测 (`latex/engine.py:detect_engine`)

根据源文件使用的包自动检测推荐引擎：

**pdfLaTeX 特征包**：
- `fontenc`, `inputenc` - 传统字体编码
- `pslatex`, `times`, `mathptmx` - PostScript 字体
- `pstricks`, `psfrag` - PostScript 图形

**XeLaTeX 特征包**：
- `fontspec`, `xeCJK` - Unicode 字体
- `polyglossia` - 多语言支持

默认：**XeLaTeX**（更好的中文支持）

### 交互式回退

当 XeLaTeX 编译失败时（`processor.py:_process_with_engine`）：

```python
# 1. 检测不可恢复错误（语法错误等）
if is_unrecoverable_error(error_output):
    print("[Unrecoverable error detected]")
    return  # 不提供回退选项

# 2. 询问用户是否尝试 pdfLaTeX
response = input("[Try pdfLaTeX instead?] [y/N]: ")
if response == "y":
    # 保留翻译缓存，重置输出目录
    _reset_output_dir(paper_dir, output_dir)
    # 使用 pdfLaTeX 重新处理
    _process_with_engine(..., engine=PDFLATEX, is_retry=True)
```

## 缺失包自动安装

### 工作原理 (`latex/engine.py`)

编译失败时自动检测并安装缺失的包（最多 20 次重试）：

```python
# 1. 编译
result = subprocess.run(["latexmk", "-xelatex", "main.tex"])

# 2. 解析错误日志
missing = parse_missing_packages(output)
# 示例：File `xifthen.sty' not found → "xifthen"

# 3. 包名映射
pkg_name = STY_TO_PACKAGE.get(f"{missing}.sty", missing)
# authblk.sty → preprint
# nicefrac.sty → units
# newtxmath.sty → newtx

# 4. 安装
subprocess.run(["tlmgr", "install", pkg_name])

# 5. 清理并重试
subprocess.run(["latexmk", "-c"])  # 清理辅助文件
```

### 内置包名映射

某些 `.sty` 文件名与 tlmgr 包名不同：

| 文件名 | tlmgr 包名 |
|--------|-----------|
| `authblk.sty` | preprint |
| `nicefrac.sty` | units |
| `newtxmath.sty` | newtx |
| `zref-abspage.sty` | zref |

未知映射会通过 `tlmgr info` 查找：
```bash
tlmgr info --data name --data category authblk.sty
```

## arXiv 元数据水印

### 功能

从 arXiv API 获取论文元数据，在 PDF 每页右上角添加浅灰色水印：

```
arXiv: 2511.05271v4
Published: 5 Nov 2025
Category: cs.CL
```

### 实现 (`latex/cjk.py`, `arxiv.py`)

1. **获取元数据** (`get_arxiv_metadata`)
   ```python
   url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
   xml = requests.get(url).text
   # 解析 <published>, <category> 等字段
   ```

2. **注入水印代码** (`add_cjk_support`)
   ```latex
   \usepackage{tikz}
   \usepackage{eso-pic}

   \AddToShipoutPictureBG{%
     \AtPageUpperLeft{%
       \raisebox{-1cm}{%
         \color{gray!30}\small\sffamily
         arXiv: 2511.05271v4\\
         Published: 5 Nov 2025\\
         Category: cs.CL
       }%
     }%
   }
   ```

3. **位置**：右上角，边距外（不遮挡正文）

## 全局并行翻译架构

采用**全局并行**策略，所有文件的所有段落一起并发翻译：

### 三阶段处理

```
阶段1: 解析 (processor.py:_process_with_engine)
├── 解析 main.tex → FileParseResult
├── 解析 section1.tex → FileParseResult
├── 解析 section2.tex → FileParseResult
└── 收集全部段落任务 → [task_0, task_1, ..., task_83]

阶段2: 翻译 (api.py:batch_translate)
└── ThreadPoolExecutor(max_workers=30)
    ├── translate(task_0) ─┐
    ├── translate(task_1) ─┤
    ├── ...               ─┤ 并发执行
    └── translate(task_83)─┘

阶段3: 组装 (parser.py:assemble_translated_file)
├── 将翻译结果分发回 main.tex
├── 将翻译结果分发回 section1.tex
└── 将翻译结果分发回 section2.tex
```

### 数据结构

**TranslationTask** (`api.py`):
```python
@dataclass
class TranslationTask:
    task_id: int              # 全局唯一 ID（用于映射翻译结果）
    index: int                # 在 result_parts 中的位置
    clean_text: str           # 清理后的文本（用于翻译）
    refs_map: dict[str, str]  # 占位符 → 原始 LaTeX
```

**FileParseResult** (`parser.py`):
```python
@dataclass
class FileParseResult:
    file_path: Path
    result_parts: list[str | TranslationTask]  # 混合列表：文本块 or 任务
    tasks: list[TranslationTask]               # 所有任务（引用）
```

### 优势

- **更快**：7 个文件只需 1 轮网络往返，而非 7 轮
- **更高效**：所有段落统一调度，不会被单个文件的慢段落阻塞
- **断点续翻友好**：缓存基于段落内容 hash，与文件结构无关

## 断点续翻机制

### 缓存机制 (`cache.py`)

每个段落翻译完成后立即保存：

```python
# 1. 计算内容 hash
def get_paragraph_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

# 2. 保存到缓存文件
cache_dir = output_dir / ".translations"
cache_file = cache_dir / f"{hash}.txt"
cache_file.write_text(translation)

# 3. 读取缓存
if cache_file.exists():
    return cache_file.read_text()
```

### 使用方式

```bash
# 首次翻译（中途中断）
python translate.py --input 2307.16789

# 继续翻译（复用已完成的翻译）
python translate.py --input 2307.16789 --resume true
```

输出示例：
```
Resuming translation in tex/arXiv-2307.16789_bilingual
  Found 58 cached translations
Parsing main file: main.tex
  Cached: 58, Pending: 6
```

### Resume 模式行为

- **保留**：`.translations/` 缓存目录
- **重置**：所有源文件（从原始目录重新复制）
- **复用**：已缓存的翻译结果
- **重新翻译**：未缓存的段落

## 目录生成

### TOC/LOT/LOF (`latex/cjk.py`)

添加在文档末尾（`\end{document}` 之前）：

```latex
% === List of Tables/Figures (auto-added) ===
\phantomsection
\addcontentsline{toc}{section}{List of Tables}
\listoftables

\phantomsection
\addcontentsline{toc}{section}{List of Figures}
\listoffigures

% === Table of Contents (auto-added) ===
\phantomsection
\tableofcontents
```

### 启用/禁用

```bash
# 启用（默认）
python translate.py --input 2307.16789 --toc true

# 禁用
python translate.py --input 2307.16789 --toc false
```

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

## 翻译输出格式

```latex
Large Language Models (LLMs) have emerged as a pivotal
breakthrough in natural language processing (NLP).

\trans{大型语言模型（LLMs）已成为自然语言处理（NLP）领域的重要突破。}

\begin{figure}
    \caption{Overview of our approach.}
    \trans{我们方法的概览。}
\end{figure}
```

`\trans{}` 命令定义（`latex/cjk.py`）：
```latex
\newcommand{\trans}[1]{{\color{gray}\small #1}}
```

PDF 中显示效果：
- **原文**：正常黑色，正常大小
- **翻译**：灰色，小字体
