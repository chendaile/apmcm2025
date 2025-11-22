# 工作流：Paper 第二版修订（work02）

面向熟悉 APMCM 语境的 AI/助手，目标是在 `Paper/main.tex` 内完成第二轮结构化修订，逐条解决 `.idea/Paper02.md` 中列出的 9 个问题。所有步骤需依次执行，完成后方可进入下一步；如遇素材缺失，需记录位置与缺口原因，避免跳过。

## 1. 素材与现状确认

1. **读取现有正文**：全面浏览 `Paper/main.tex`，记录当前章节顺序（尤其是 Introduction、Assumptions、Notations、Model Formulation、Results、Strength/Weakness、Key Results Summary 所在位置）。
2. **建立素材清单**：
   - Q1：`output/Q1/solve_log.txt`、`output/Q1/solution_variables.xlsx`、`Paper/figures/Q1-hot.png`、`Paper/figures/Q1-plot.png`。
   - Q2：`output/Q2/solve_log.txt`、`output/Q2/solution_variables.xlsx`（备用）、`Paper/figures/Q2-*.png`、`Paper/figures/understanding-Q2.txt`。
   - Q3：`output/Q3/solve_log.txt`、`output/Q3/solution.xlsx`、`Paper/figures/Q3.png`、`Paper/figures/understanding-Q3.txt`。
   - Q4：`output/Q4/solve_log.txt`、`output/Q4/result.log`、`output/Q4/solve.png`。
3. **查阅公式/符号来源**：整理 `.idea/Q1.md`、`.idea/Q2.md`、`.idea/Q1_QUBO.md`、`.idea/Q2_QUBO.md`、`src/QUBO/Q1-QUBO_tmp.py`、`tmp/haha.py` 的关键信息，补足 notation 与 QUBO 说明素材。

## 2. 全局结构改造

1. **整体章节顺序**：保持 `Introduction → Assumptions → Notations` 的导入结构，之后将正文改写为“按题目推进”的主干：`Section 4 Problem 1`、`Section 5 Problem 2`、`Section 6 Problem 3`、`Section 7 Problem 4`。每个章节内按照“模型 → 算法实现/流程 → 结果与分析”的固定结构展开。
2. **删除“公式-结果”式串联**：若出现跨题混写（如统一的 Model Formulation、Results），拆分到对应题目的章节，确保每题独立完整。
3. **Key Results Summary 前移**：建立 `Section 3` 或独立 `Section` 紧接 `Introduction`，概述四道题的核心发现（每题 2–3 句），引用后文的表/图编号；原附录中的简表删除或合并。

## 3. 符号与公式规范

1. **Notations 显示问题**：
   - 将原有 `table` 改为 `longtable` 或 `tabularx`，必要时在导言区加载 `\usepackage{longtable}` 或 `\usepackage{tabularx}`，设置 `\begin{longtable}[c]{lll}`，写明 `\endfirsthead`/` \endhead`，保证符号表不会被浮动到文尾。
   - 若坚持使用 `table`，改用 `\begin{table}[H]` 并引入 `\usepackage{float}`，确保符号表在 `\section{Notations}` 下方立即渲染。
2. **补全符号来源**：结合 `.idea/*` 笔记，将所有变量、集合、参数按“符号/含义/适用题号”填入表中，禁止留空行；若需拆表，优先按“集合/参数/变量”分组。
3. **公式编号与解释**：
   - 所有公式统一使用 `equation` 或 `align` 环境并 `\label{eq:q1_obj}` 形式编号。
   - 在每段公式后立刻跟 2–3 句文字解释（变量含义、物理意义、约束作用）；禁止仅展示公式。
   - 当同一逻辑包含多条约束时，合并到 `aligned` 块并在解释中指出“式~\eqref{...} 与 \eqref{...} 共同保证 XXX”。

## 4. 问题一章节（经典 UC）

1. **模型部分**：
   - 重新组织 `Problem 1` 子节：`模型描述 → 约束分组（功率平衡/容量/时间逻辑/爬坡）→ 求解流程`。
   - 在求解流程内给出伪代码或步骤列表（读取数据 → 建立 Gurobi 模型 → 添加约束 → 求解 → 解析变量），并标注输入输出。
2. **结果部分**：
   - 用 `output/Q1/solve_log.txt` 提取求解元数据（行、列、非零数、变量类型、最优目标、gap、时间），整理成 `表~\ref{tab:q1_meta}`。
   - 引用 `solution_variables.xlsx` 提取 2–3 个代表性小时的机组出力，展示在 `booktabs` 表中。
   - 插入 `Q1-hot.png`、`Q1-plot.png` 两张图，使用 `Paper/figures/understanding-Q1.txt` 的描述撰写 `caption` 与正文分析。
3. **分析段落**：紧随图表解释“基荷/调峰机组角色”“约束满足性”，引用求解日志提供的数字（如 0.009% gap）。

## 5. 问题二章节（网络与安全约束 UC）

1. **模型扩展**：
   - 用子小节阐述新增内容：`2.1 灵活负荷建模`、`2.2 DC 潮流`、`2.3 备用约束`、`2.4 N−1 场景`。
   - 对每组公式添加编号与解释，说明网络变量、备用变量与场景索引的含义。
   - 在 `求解流程` 处给出“主问题 + 场景循环”的伪代码或流程图描述。
2. **结果展示**：
   - 以 `output/Q2/solve_log.txt` 中的行/列/迭代次数/根松弛信息整理 `表~\ref{tab:q2_meta}`，对比 Q1。
   - 对比 `Q1` 与 `Q2` 的成本，明确指出增加安全约束的代价（引用日志中 15,129.08）。
   - 插入 `Q2-bus-load.png`、`Q2-flow.png`、`Q2-flow-outage-flow.png`、`Q2-flow-outage-gen.png`、`Q2-load.png`、`Q2-reserve.png` 等关键图，并用 `understanding-Q2.txt` 的文字写说明，强调网络瓶颈、备用分布、事故响应。
3. **求解元数据引用**：明确记录模型规模增长（行数 196,900 → 43,262 after presolve），满足“求解元数据未使用”的整改要求。

## 6. 问题三章节（QUBO 转换与量子求解）

1. **QUBO Formulation 详细化**：
   - 根据 `src/QUBO/Q1-QUBO_tmp.py` 与 `.idea/Q1_QUBO.md` 描述二进制编码方式（功率离散化、启停变量）、惩罚项构造（功率平衡、出力上下限、逻辑约束）的公式，分别编号并解释惩罚系数作用。
   - 解释 `Q = Q_{\text{obj}} + \lambda_b Q_{\text{balance}} + ...` 中各块的展开方式，列出至少 2 个具体矩阵条目示例。
   - 说明 `dimension=7024`、`density=6.6e-4` 等指标来源于 `output/Q3/solve_log.txt`，并讨论对 Kaiwu 真机位宽的影响。
2. **求解流程**：写出 Kaiwu SDK 处理步骤（QUBO 构造 → 尝试真机 → fallback 到模拟退火 → 解析 bit → 映射回出力）。
3. **结果对比**：
   - 建立 `表~\ref{tab:q3_compare}`，比较 Gurobi（Q1 结果）与 QUBO（Kaiwu 模拟）的指标：成本、功率平衡残差、启停违反、能量值。
   - 使用 `Paper/figures/Q3.png` 与 `understanding-Q3.txt` 文本解释量子结果的跳变特性，指出哪些约束被违反。

## 7. 问题四章节（规模约简与真机可行性）

1. **方法论陈述**：
   - 根据 `.idea/Paper02.md` 与 `output/Q4/solve_log.txt` 描述“通过减少 slack 变量、压缩参数空间，使 QUBO 适配真机位宽”的策略；列出减少的变量数量或比特比率（可由 Q3/Q4 dimension 对比估算）。
   - 若 `result.log` 给出 Hamiltonian，记录真机/模拟能量与可行性状态。
2. **结果展示**：
   - 使用 `output/Q4/solve.png` 插入图像，说明该图展示的求解曲线或布线结果，并在正文解释图中关键拐点。
   - 结合 `solve_log.txt` 描述约束残差、成本（26,775.55）以及与 Q3 的改进（如残差降低或可行时段增加）。
3. **结论总结**：写段落强调“减少 slack → QUBO 可在真机/模拟上运行”的可行性，并为摘要提供结论素材。

## 8. 结果汇总与摘要

1. **Key Results Summary 前置**：在 `Introduction` 之后或 `Results Overview` 节中，用 `itemize` 或 `subsection` 形式，按 Q1～Q4 列出主要发现（模型方法 + 数字 + 实际意义），引用相应表图。
2. **摘要撰写**：遵循“方法论（Methodology）→ 数值结果（Results）→ 结论（Conclusion）”结构，每个部分用 2–3 句，覆盖四道题的亮点：
   - 方法论：概括经典 UC、网络扩展、QUBO 转换、规模缩减；
   - 数值结果：引用关键成本、残差、变量规模、Q4 可行性；
   - 结论：指出量子方案的可行路径与限制。

## 9. 图表引用与说明

1. **统一引用规则**：所有图片、表格需在正文中先提及（“如图~\ref{fig:q2_flow}”），再出现对应浮动体。
2. **图片说明**：为每张图撰写 3–4 句解释，内容来自 `Paper/figures/understanding-Q*.txt`；若没有 Q4 的解释文件，则以 `output/Q4/solve_log.txt` 数据补写。
3. **表格说明**：在表格下添加 `\caption` 与必要的脚注（例如数据源、单位）。

## 10. 校验与交付

1. **交叉检查**：确保每个公式都有编号、每个编号在正文被引用一次以上；如有未引用编号，及时清理。
2. **素材核对**：确认 `Key Results Summary` 不在附录；附录仅保留代码与参考文献。
3. **编译校验**：运行 LaTeX 编译（至少一次 PDFLaTeX），检查目录、交叉引用、图片路径是否正确；若有 Warning（如 `Label(s) may have changed`），重复编译至消除。
4. **记录残留问题**：若某图或数据缺失，需在文末“后续工作”列表中说明缺口与所需操作。

完成以上步骤后再行提交，确保 A、B 两版工作流的一致性与可追溯性。
