#!/bin/bash
# LaTeX 编译命令参考
# 直接复制下面的命令使用

# ============================================
# 使用前先进入你的 tex 目录
# ============================================
# cd tex/arXiv-2506.18096v2_bilingual


# ============================================
# 方法 1: 使用 XeLaTeX 编译(推荐,更好的中文支持)
# ============================================
latexmk -xelatex -bibtex -f -interaction=nonstopmode -file-line-error main.tex


# ============================================
# 方法 2: 使用 pdfLaTeX 编译(兼容性更好)
# ============================================
latexmk -pdf -bibtex -f -interaction=nonstopmode -file-line-error main.tex


# ============================================
# 清理编译产生的辅助文件(保留 PDF)
# ============================================
latexmk -c


# ============================================
# 完全清理(包括 PDF)
# ============================================
latexmk -C


# ============================================
# 参数说明
# ============================================
# -xelatex          使用 XeLaTeX 引擎
# -pdf              使用 pdfLaTeX 引擎
# -bibtex           运行 BibTeX 处理参考文献
# -f                强制完成编译(即使有警告)
# -interaction=...  遇到错误不暂停
# -file-line-error  显示详细的错误位置
# -c                清理辅助文件
# -C                完全清理


# ============================================
# 如果你想手动控制编译步骤(不推荐,除非调试)
# ============================================
# 第一步: LaTeX 编译
xelatex -interaction=nonstopmode main.tex

# 第二步: BibTeX 处理参考文献
bibtex main

# 第三步: 再次编译读取参考文献
xelatex -interaction=nonstopmode main.tex

# 第四步: 最后一次编译解决交叉引用
xelatex -interaction=nonstopmode main.tex


# ============================================
# 检查编译结果
# ============================================
# 查看未定义的引用数量
grep "Citation.*undefined" main.log | wc -l

# 查看具体哪些引用未定义
grep "Citation.*undefined" main.log

# 查看编译错误
grep "^!" main.log

# 打开生成的 PDF (macOS)
open main.pdf
