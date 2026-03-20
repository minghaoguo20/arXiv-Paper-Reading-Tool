# LaTeX 翻译脚本 Bug 记录

## 已修复的问题

### 1. 主文件检测错误
**问题**: 硬编码查找 `neurips_2025.tex` 或 `main.tex`，找不到其他命名的主文件
**解决**: 改为查找包含 `\documentclass` 的文件

### 2. subfigure/subcaption 包冲突
**问题**: 两个包同时存在导致编译失败
**解决**: 自动注释掉 `subfigure`（保留更新的 `subcaption`）

### 3. natbib 引用风格冲突
**问题**: `\usepackage{natbib}` 与 `\bibliographystyle{unsrt}` 不兼容
**解决**: 自动添加 `[numbers]` 选项

### 4. 旧式 CJK 包与 xeCJK 冲突
**问题**: `\usepackage{CJK}` 或 `\usepackage{CJKutf8}` 与 xeCJK 冲突
**解决**: 注释旧包，移除 `\begin{CJK}...\end{CJK}` 环境包装

### 5. hyperref 驱动不兼容 XeTeX
**问题**: hyperref 默认使用 pdftex 驱动，与 tectonic (XeTeX) 不兼容
**解决**: 在 `\documentclass` 后添加 `\PassOptionsToPackage{xetex}{hyperref}`

### 6. 翻译内容插入到 preamble
**问题**: 翻译整个主文件时，`\trans{}` 被插入到 `\begin{document}` 之前
**解决**: 添加 `is_main_file` 参数，只在 `\begin{document}` 后开始翻译

### 7. 无 sections 目录时找不到文件
**问题**: 硬编码查找 `sections/` 目录
**解决**: 改为解析 `\input{}` 和 `\include{}` 递归查找文件

### 8. 配置文件被错误翻译
**问题**: `config.tex` 等 preamble 文件被翻译导致编译失败
**解决**: 检测文件内容，跳过主要是 `\usepackage`/`\newcommand` 的文件

### 9. tar.gz 解压问题
**问题**: 有些压缩包没有顶层目录，解压后文件散落
**解决**: 检测压缩包结构，无顶层目录时创建目标文件夹

### 10. 主文件内容未翻译 ✅ 已修复
**问题**: 当论文主要内容在 `main.tex` 中（而非拆分到子文件），主文件不会被翻译
**现象**: `arXiv-2303.11366v4` 只翻译了 4 个 appendix 文件，正文未翻译
**原因**: 当找到 included 文件时，只翻译 included 文件，跳过了主文件
**解决**: 始终翻译主文件（is_main_file=True），同时翻译 included 文件

---

### 11. itemize/enumerate 选项参数被包含在翻译中 ✅ 已修复
**问题**: `\begin{itemize}[options]` 的选项参数出现在翻译内容中
**现象**: 翻译包含 `noitemsep,topsep=0pt,parsep=0pt,...`
**原因**: `clean_for_translation` 只处理 `\begin{...}` 没有处理 `[options]`
**解决**: 修改正则为 `\\begin\{[^}]+\}(\[[^\]]*\])?`，同时清理 `\item[label]`

---

## 新功能

### arXiv 自动下载 ✅
**功能**: 支持直接从 arXiv 下载论文源文件
**输入格式**:
- `2307.16789` - arXiv ID
- `2307.16789v2` - 带版本号的 arXiv ID
- `https://arxiv.org/abs/2307.16789` - abs 页面 URL
- `https://arxiv.org/pdf/2307.16789` - pdf 链接
- `https://arxiv.org/src/2307.16789` - 源文件链接
- `https://arxiv.org/html/2307.16789` - html 页面

**实现**: 从 `https://arxiv.org/src/{arxiv_id}` 下载 .tar.gz，保存到 `tex/arXiv-{id}.tar.gz`

---

## 待观察的潜在问题

- 非 UTF-8 编码的 .tex 文件
- 复杂的自定义环境
- `\verbatim` 或 `lstlisting` 中的特殊字符
