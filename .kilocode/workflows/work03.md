# 工作流：Paper 第三轮修订（work03）

目标：依据 `.idea/Paper03.md` 指出的七项问题，进一步完善 `Paper/main.tex`。所有步骤需按顺序执行，若材料不足，需记录缺口及处理方法。

## 1. 资料复核
1. 打开 `Paper/main.tex`，确认摘要、Problem Analysis、Key Results Summary、各题章节、图表引用的现状。
2. 准备必要数据源：`output/Q1~Q4/solve_log.txt`、`output/Q1~Q4/solution*.xlsx`、`Paper/figures/understanding-Q*.txt`，确保后续引用的数字与说明均来源清晰。
3. 建立一个草稿记录表（可在 `.idea/Paper03_notes.md`）用于暂存从日志/表格中整理出的数值，避免在正文中提及原路径。

## 2. 摘要重写
1. 将摘要拆成四个段落，对应 Problem 1–4；每段按照“Methodology（方法）→ Results（关键数值）”顺序描述，必要时结尾补一句结论。
2. 每段至少包含一项定量指标（如最优成本、约束残差、QUBO 维度、Hamiltonian 等），来源于日志或图表。
3. 删除旧有的“Methodology / Results / Conclusion”小标题描述，换成正文自然段。
4. 完成后检查关键词段落保持不变。

## 3. Problem Analysis 结构调整
1. 将当前 `\subsection{Problem Analysis}` 改写为按题目划分的结构，示例：
   - `\subsubsection{Problem 1 Analysis}`：概述建模核心假设、求解策略；
   - `\subsubsection{Problem 2 Analysis}`：说明新增约束、预期影响；
   - `\subsubsection{Problem 3 Analysis}`：解释 QUBO 映射思路、惩罚参数；
   - `\subsubsection{Problem 4 Analysis}`：阐述规模压缩迭代、目标。
2. 每个子小节需描述“思路/迭代逻辑”，可引用相关公式或算法流程，但不要提前列出结果。

## 4. 移除 Key Results Summary 章节
1. 删除 `\section{Key Results Summary}` 整段内容。
2. 将其中的重要信息分散整合到：
   - Problem 1–4 各自章节的开头或结果分析段；
   - 或在 `Introduction` 末尾用 1–2 句提示读者后续结构（不可再使用“Key Results Summary”标题）。

## 5. 数据引用方式整改
1. 禁止在正文出现类似 `output/Q4/solve_log.txt` 的路径。若需要引用某文件内容，需：
   - 从日志中提取具体数字，填入表格或正文；
   - 在文字中描述“根据求解日志，我们得到……”，而非写绝对路径。
2. 对现有文本中出现路径的段落逐一搜索并改写为数据描述。
3. 在 Problem 3、Problem 4 小节，若要提醒数据来源，可在脚注说明“数据来源于求解日志”，但同样不出现文件路径。

## 6. 结果内容充实
1. `Representative classical dispatch (MW)` 目前仅展现 3 个小时。需补充完整 24h 出力表，可参考：
   - 直接导出 `output/Q1/solution_variables.xlsx` 中 24 小时的数据；
   - 或者拆为附录长表（`longtable`），正文保留聚合指标（如平均/峰值），并在文字中说明附录提供全量数据。
2. 检查所有“结果”小节是否只提供摘要。若信息不足，补充：
   - 更多时段/场景对比（例如 Q2 的多个故障情景）；
   - Q3/Q4 的约束残差统计、位宽变化等。
3. 确保每个补充数据都来自前述素材，并在表/图标题中注明含义。

## 7. 图像位置校验
1. 逐一检查 `Figure` 插图，确认其 `\includegraphics` 路径与题目对应关系：
   - Q1 图仅出现在 Problem 1 章节；
   - Q2 图仅在 Problem 2；
   - Q3/Q4 图同理。
2. 若某图放在错误章节或未被引用，调整其位置和编号。
3. 对新加入或移动的图，依据 `Paper/figures/understanding-Q*.txt` 撰写配套说明和 caption，保证描述对应题目范围。

## 8. 终审
1. 全文自查：摘要结构、Problem Analysis 小节、Key Results Summary 是否已处理；搜索 `output/`、`solve_log` 等关键词确认不再出现路径。
2. 检查交叉引用（公式/图表/表格）是否仍然有效，必要时重新编译 LaTeX 至警告消失。
3. 在工作记录（如 `.idea/Paper03_notes.md`）中总结本轮修改要点，供后续版本追踪。

完成以上步骤后再交付，确保 `Paper/main.tex` 已满足 Paper03 的全部要求。
