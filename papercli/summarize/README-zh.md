# papercli summarize

从 arXiv 或本地 LaTeX 源码生成学术论文的结构化摘要，底层调用 Codex 模型。

## 使用方式

```bash
python run.py summarize --input <arxiv-id|arxiv-url|本地目录> [选项]
```

### 示例

```bash
# 通过 arXiv ID 摘要
python run.py summarize --input 2307.16789

# 通过完整 arXiv URL 摘要
python run.py summarize --input https://arxiv.org/abs/2307.16789

# 摘要本地 LaTeX 目录
python run.py summarize --input tex/my-paper/

# 指定模型与推理强度
python run.py summarize --input 2307.16789 --model o3 --reasoning_effort high

# 使用自定义 prompt
python run.py summarize --input 2307.16789 --prompt_file papercli/summarize/prompts/my_prompt.md
```

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--input` | *(必填)* | arXiv ID、arXiv URL 或本地论文目录路径 |
| `--model` | `gpt-5.5` | 使用的 Codex 模型 |
| `--reasoning_effort` | `xhigh` | 推理强度：`low`、`medium`、`high`、`xhigh` |
| `--prompt_file` | `papercli/summarize/prompts/summary.md` | prompt 文件路径（相对于项目根目录） |
| `--max_tex_chars` | `120000` | 传给模型的 LaTeX 内容最大字符数 |

## 输出位置

摘要写入论文目录同级的新目录中：

```
tex/
  2307.16789/          # 解压后的论文源码
  2307.16789_summary/
    2307.16789.md      # 生成的摘要
```

macOS 下会自动在 Finder 中打开输出目录。

## 摘要格式

默认 prompt（`prompts/summary.md`）生成包含五个章节的结构化摘要：

- **TL;DR** — 3-5 句话概括核心贡献
- **Problem** — 论文解决的问题与研究空白
- **Method** — 关键技术方案或算法
- **Key Results** — 主要实验结果与基线对比
- **Limitations & Future Work** — 作者指出的局限性与未来方向

## 自定义 prompt

在 `papercli/summarize/prompts/` 下新建 `.md` 文件，通过 `--prompt_file` 指定即可。runner 会在 prompt 之后自动拼接完整的 LaTeX 源码，因此 prompt 写成独立指令即可，无需手动引用源码。

## 工作流程

1. 若输入为 arXiv ID 或 URL，自动下载并解压源码包到 `tex/` 目录。
2. 查找主 `.tex` 文件（含 `\documentclass` 的最大文件）。
3. 若内容超过 `--max_tex_chars`，自动截断。
4. 调用 `codex exec` 生成摘要，结果写入 `.md` 文件。
