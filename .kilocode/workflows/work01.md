#工作流：A 题论文撰写（work01）

本工作流面向熟悉竞赛背景的 AI/助手，目标是基于 `Paper/main.tex` 撰写中文版论文正文。所有步骤须严格按顺序执行，必要时回溯确认素材。若任一步骤缺资料，应在日志中说明缺口并暂存待补。

##1. 资料与环境准备

1.**通读题目与附录**：阅读题面原文及 `QuestionD/Table.xlsx` 等官方数据，确保理解 Q1–Q4 的业务含义。

2.**阅读本地笔记**：依次查看 `.idea/Q1.md`、`.idea/Q2.md`、`.idea/Q1_QUBO.md`、`.idea/Q2_QUBO.md`、`.idea/Paper.md`，记录符号、变量、参考假设。

3.**了解假设与数据来源**：打开 `.idea/assumption.md`，列出全部假设并在后续章节统一引用。

4.**梳理代码结构**：浏览下列脚本，理解求解逻辑及输出：

-`src/classic/q1_uc_model.py`

-`src/classic/q2_uc_network.py`

-`src/QUBO/Q1-QUBO.py`

5.**确认输出素材**：检查 `output/`、`Paper/figures/` 目录。

- Q1：`output/Q1/solve_log.txt`、`output/Q1/solution_variables.xlsx`、`Paper/figures/Q1-hot.png`、`Paper/figures/Q1-plot.png`
- Q2：`output/Q2/`、`Paper/figures/Q2/*.png`
- Q3：`output/Q3/`, `Paper/figures/Q3/*.png`（Kaiwu 对比结果）、相关图表
  `Paper\figures\understanding-Q1.txt` `Paper\figures\understanding-Q2.txt` `Paper\figures\understanding-Q3.txt`是每道题对应的所有图片理解,用于解释图片
  ##2. LaTeX 文件基础设置

1. 打开 `Paper/main.tex`。
2. 保留模板导言与 `\documentclass{apmcmthesis}`，清理示例正文内容。
3. 摘要暂留空白或使用 `TODO` 占位。
4. 保留 `\tableofcontents`，正文页码从 `\section{Introduction}` 开始并将页码计数器重置为 1。
5. 确保导言区加载 `booktabs`、`amsmath`、`algorithm`、`graphicx` 等必须宏包。

##3. Introduction（第一部分）

为除摘要外的首个章节，包含三个子节，均以中文命名：

1.`\subsection{问题背景}`：概述电力系统 UC/安全约束 UC 背景、数据来源、竞赛设定。

2.`\subsection{问题重述}`：用自己语言重述 Q1–Q4 要求，明确决策变量、目标、约束侧重点。

3.`\subsection{问题分析}`：描述整体求解思路（Q1 经典 UC ➜ Q2 增强约束 ➜ Q3 QUBO ➜ Q4 真机验证），强调分析逻辑，禁止直接给结果。

##4. 问题假设

1. 新建 `\section{问题假设}`。
2. 使用 `enumerate` 环境列出 `.idea/assumption.md` 中所有假设。
3. 每条假设附加一句“原因/应用场景”说明，如“仅考察 24 h：竞赛聚焦日内调度”。
4. 若建模过程中新增了假设，也在该列表末尾补充。

##5. 符号说明

1. 建立 `\section{符号说明}`。
2. 汇总 `.idea/Q1.md`、`.idea/Q2.md`、`Q1_QUBO.md`、`Q2_QUBO.md` 中的符号。
3. 用单个三线表展示：列为“符号/含义/适用问题”。使用 `booktabs`，例如：

      ```latex

      \begin{table}[h]

      \centering

      \begin{tabular}{lll}

      \toprule

      符号 & 含义 & 适用问题 \\

      \midrule

      $u_{i,t}$ & 机组 $i$ 在时段 $t$ 的开机状态(0/1) & Q1--Q3 通用 \\

      ...

      \bottomrule

      \end{tabular}

      \end{table}

      ```

4. 若符号跨题通用，只写一次并在第三列标注“通用”。

##6. 模型建立（核心章节）

建立 `\section{模型建立}`，按题目拆为 `\subsection{问题一模型}`、`\subsection{问题二模型}`、`\subsection{问题三模型}`，Q4 暂不写正文，可留注释。

###6.1 统一结构

每个题目内按照以下子结构展开：

1.**模型描述**：

- 以文字+公式给出目标函数与关键约束，使用 `align` 环境编号。
- 在引用公式时使用先前定义的符号。

     2.**伪代码/求解流程**：

- 采用 `algorithm` 或 `lstlisting` 给出求解流程（如 Gurobi 建模步骤、安全约束迭代、QUBO 构造+Kaiwu 调用）。
- 伪代码需包含输入、输出、关键循环。

     3.**结果展示**：

     -**表格**：整理 `output` 中的数据。示例：Q1 将 `q1.txt` 的“模型规模、目标值、求解时间”整理成一张三线表；Q2 提供不同约束场景的成本/冗余/备用；Q3 给出 Gurobi vs Kaiwu 的目标值、约束违反指标。

     -**图像**：插入 `Paper/figures` 中对应图片，例如 `Q1-hot.png`、`Q1-plot.png`。用 `figure` 环境设置 `

\includegraphics[width=...]`，配 `caption `、`label`，并在正文中引用。

-**数据表**：若图片来自 Excel/CSV，需为关键曲线提供摘要表格（如负荷分配、机组出力峰值）。

4.**结果分析**：

- 用文字解释表格/图含义，与上一题比较（尤其 Q2 对比 Q1、Q3 对比 Gurobi 结果）。
- 指出出现的现象（例如 Q3 惩罚项导致约束违规）。

###6.2 各题目要点

-**问题一（Q1）**：

- 强调所有机组 24h 持续开机的原因（min up/down）。
- 表格列出求解器元数据（变量数、约束数、最优成本、求解时间）。
- 分析来自 `solution_variables.xlsx` 的出力数据，必要时列出高峰/低谷小时的出力表。

-**问题二（Q2）**：

- 重点描述新约束：N−1 发电机、N−1 线路、柔性负荷变量、备用约束绑定等；指出目标函数与 Q1 相同。
- 伪代码展示“主问题 + 各故障场景潮流”的迭代结构。
- 结果部分需比较不同约束组合（如 baseline 与 no-inertia），展示成本、备用轨迹、冗余。

-**问题三（Q3）**：

- 解释如何将 Q1 目标与约束映射到 QUBO（变量编码、惩罚系数）。
- 描述 Kaiwu SDK 的调用流程（建模 → 量化 → 求解）。
- 结果中对比 Gurobi 与 Kaiwu（目标、约束满足度、图表差异），强调惩罚项导致的违规实例。

-**问题四（Q4）**：

- 暂不写正文，保留注释“等待真机实验数据后补充”。

##7. 模型结果总结

1. 创建 `\section{模型结果总结}`。
2. 用 `itemize` 或小节形式汇总 Q1–Q3 的主要发现（成本差异、可靠性提升、惩罚法局限等）。
3. 需要引用前文表图支撑，例如“见表~\ref{tab:q2_compare}”。

##8. 模型优劣分析

1.`\section{模型优劣}`，分成两个 `\subsection`：

- “模型优势”：例如建模层次分明、约束覆盖全面、可扩展到 Q4。
- “模型局限”：如假设偏多、柔性负荷数据缺乏、Q3 惩罚参数难调。

2. 对应假设或结果部分逐条说明原因及可能影响。

##9. 附录

设置 `\section{附录}`，包含两个子部分：

1.**示例代码**：

- 选取具有代表性的代码片段（Q1 目标函数构造、Q2 N−1 约束循环、Q1-QUBO 惩罚项推导等）。
- 使用 `lstlisting`，注明语言 (`language=Python`) 与 `caption`。

     2.**参考文献**：

- 所有引用（题面、教材、Gurobi、Kaiwu）需在正文中 `\cite`。
- 在附录末尾使用 `thebibliography` 或 BibTeX。格式示例：`\bibitem{gurobi} Gurobi Optimization, LLC. Gurobi Optimizer Reference Manual, 2024.`

##10. 写作与排版注意

1. 全文使用中文描述，变量/函数保持英文。
2. 所有图表须在正文中先引用再出现，编号格式 `图~\ref{fig:...}`、`表~\ref{tab:...}`。
3. 表格统一使用 `booktabs` 三线格式，必要时在表下方说明单位和数据来源。
4. 公式尽量编号，引用时用 `\eqref`。
5. 若某步骤因依赖缺失而无法完成（如图未生成），必须记录原因并在文末“后续工作”处列出所需操作。
6. 完成后自行编译一次 LaTeX，确保无错误、目录与引用正确。

> 以上步骤意在最大化写作准确率：每轮执行前后需回顾素材是否齐备，若有更新（如新增图表），需同步修改引用与说明。
