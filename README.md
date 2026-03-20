# LaTeX 论文翻译工具

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
pip install requests tqdm
```

### 翻译 API（可选）

默认使用测试模式（mock 翻译）。启用真实翻译需设置环境变量：

```bash
export ONE_API="your-api-key"
```

并修改 `translate.py` 中的 `TEST_MODE = False`。

## 使用方法

```bash
cd /Users/minghao/Desktop/translation

# 方式 1: arXiv ID（自动下载最新版本）
python translate.py 2307.16789

# 方式 2: 指定版本
python translate.py 2307.16789v1

# 方式 3: arXiv URL（支持 abs/pdf/src/html）
python translate.py https://arxiv.org/abs/2307.16789
python translate.py https://arxiv.org/pdf/2307.16789

# 方式 4: 本地压缩包
python translate.py tex/arXiv-2307.16789.tar.gz

# 方式 5: 本地目录
python translate.py tex/arXiv-2307.16789v2
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
[翻译] 逐段翻译，添加 \trans{翻译内容}
    ↓
[编译] tectonic → PDF
    ↓
[打开] 自动打开生成的 PDF
```

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

## 配置选项

在 `translate.py` 中可修改：

```python
# 测试模式（不调用 API，使用 mock 翻译）
TEST_MODE = True

# 翻译 API
API_URL = "https://api.bltcy.ai/v1/chat/completions"
MODEL_NAME = "gpt-4.1-nano"
```

## 文件说明

```
translation/
├── translate.py    # 主程序
├── bugs.md         # Bug 记录和修复历史
├── README.md       # 本文档
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
修改 `API_URL` 和 `translate()` 函数中的请求格式。

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
