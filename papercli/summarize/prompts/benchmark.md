You are a research assistant. Read the LaTeX source. Explain this benchmark paper in concise zh for a manager/research discussion. This is a benchmark-focused analysis task, not a generic paper summary.

Your output must be:
- concise,
- concrete,
- focused on only the most important points,
- easy to present verbally,
- and suitable for a boss-facing report.

Do NOT produce a long section-by-section paraphrase.
Do NOT explain every minor detail.
Only keep the key points that determine:
1. what is being benchmarked,
2. how the benchmark is designed,
3. how the pipeline/workflow runs,
4. how evaluation/scoring works,
5. what the main result really means,
6. what the biggest limitations are,
7. what the benchmark’s typical questions/tasks look like in concrete terms.

Style requirements:
- Write in clear Chinese.
- Be brief and direct.
- Prefer short paragraphs and bullets over long prose.
- Each subsection should contain only the essential points.
- Avoid generic praise and empty wording.
- If something is unclear in the paper, write “论文未明确说明”.
- Do not overclaim.

Visual requirements:
- Make the output figure-aware and presentation-friendly.
- Whenever a figure, table, chart, screenshot, architecture diagram, pipeline diagram, qualitative example, benchmark example, or any visual evidence should be inserted, add a placeholder in this format:
  - 【Figure x】
  - 【Table x】
- Use the actual index when available, such as 【Figure 1】, 【Table 2】.
- If the paper has no suitable indexed figure/table but a screenshot or cropped visual would help, mention it.
- After each placeholder, briefly state what should be shown there and why it matters.
- Especially add placeholders for:
  - benchmark overview figure,
  - pipeline/workflow figure,
  - evaluation setup figure/table,
  - main result table,
  - representative benchmark question/task example,
  - qualitative case / failure case,
  - fairness / comparison setup if relevant.

Formatting requirements:
- Mention figures and tables with their original indices when possible.
- Write equations within $ as latex inline format.
- Percent sign is `\%`.
- Do not use latex equation for simple numbers, dimensions, or percentages.
- Do not invent content not supported by the paper.

Use the following format:

# 1. 这篇论文在做什么
用 3 到 5 句话讲清：
- 这篇 benchmark 到底测什么
- 被测对象是 base model、agent、tool-use system、MCP workflow，还是 end-to-end system
- 它为什么值得看

【Figure/Table/...】放一张最能代表论文核心问题定义或整体 benchmark 概览的图/表，并说明这张图/表要传达什么。

# 2. Benchmark 是怎么设计的
只讲最关键的 benchmark design：
- 一个 sample 是什么：单轮问题、multi-turn episode、trajectory，还是 workflow instance
- task design 的关键点
- environment design 的关键点
- 它想模拟什么真实场景
- final score intended to represent 什么能力

用 4 到 8 个要点讲清，不要展开成教科书。

【Figure/Table/...】放 benchmark overall design / task taxonomy / setup overview，并说明读图重点。

# 3. Benchmark 中的典型问题 / 典型任务
这一节必须具体，不要空泛总结。请挑出论文中最有代表性的 2 到 5 类典型问题、任务或 episode，并对每类都说明：
- 这类题 / 任务长什么样
- 具体要求模型或系统做什么
- 它主要在测什么能力
- 为什么这类题有代表性
- 常见失败模式是什么

要求：
- 尽量用论文中的真实例子、真实任务描述、真实 case type
- 如果能引用论文里的 example / case / screenshot / task instance，就优先引用
- 如果论文未给出完整例题，就根据论文描述概括题型，但要注明“论文未给出完整示例”
- 不要只说“测推理能力”“测工具使用”，要具体到任务层面

【Figure/Table/Text/...】放 representative benchmark question / task example / episode screenshot，并说明这个例子为什么典型。  
【...】如有必要，放 failure case 或错误轨迹，并说明暴露了什么问题。

# 4. Pipeline / Workflow 是怎么跑的
用最简洁的方式按步骤解释：
task input -> context construction -> planner/agent -> tool or MCP interface -> execution/environment -> feedback loop -> final output -> evaluator/judge -> score

要求：
- 每一步只讲“输入 / 输出 / 作用”
- 明确哪些是 benchmark infrastructure，哪些是被测能力
- 如果涉及 agent / tool / MCP / judge / verifier / environment，要分别说明角色
- 如果论文没有这些模块，就直接说明没有

【Figure/Table/...】放 pipeline/architecture 图，并说明每个模块要怎么看。

# 5. 怎么打分，怎么比较
只保留最关键的 evaluation protocol：
- 主要指标是什么
- score 测量什么，不测量什么
- baseline 怎么比
- 是否公平，控制了哪些变量
- 还有哪些没控制住，可能影响结论

要求：
- 必须明确说清 benchmark score 的含义边界
- 必须指出最重要的 fairness issue 或 bias risk
- 不要泛泛而谈

【Table x】放主结果表。说明应该看哪几列、哪几个对比最关键。  
【Figure/Table/Other x】如果有 judge / evaluator / verification 流程图或公平性相关图表，也加上。

# 6. 主要结果到底说明了什么
用 3 到 6 个要点回答：
- 谁表现最好
- 为什么可能最好
- 这个结果说明的是模型更强、系统更强、pipeline 更强，还是 protocol advantage
- 哪个结果最值得老板关注
- 哪些结论不能过度解读

【Table/Figure x】放最关键结果图/表，并说明老板应该看什么结论。  
Others 如有必要，放 qualitative case / failure case / trajectory screenshot，并说明它证明了什么。

# 7. 一页式批判性总结
分成四小段，每段尽量短：

## 7.1 TL;DR

## 7.2 亮点
只写最有价值的 2 到 4 点。

## 7.3 局限
只写最关键的 2 到 4 点。

## 7.4 对我们有什么启发
只写最直接的 2 到 4 点，优先写对 benchmark 设计、agent 设计、MCP/tool 集成、评测协议的启发。
