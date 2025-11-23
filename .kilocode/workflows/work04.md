# 工作流：Paper 第四轮修订（work04）

目标：根据 `.idea/Paper04.md` 的十项要求，进一步完善 `Paper/main.tex`，强调量子与经典差异、完善图表/公式解读，并清理无关段落。步骤需按顺序执行，如遇资料缺口需记录在 `.idea/Paper04_notes.md`。

## 1. 资料与现状检查
1. 通读最新 `Paper/main.tex`，列出以下内容的当前位置：
   - 摘要与关键词；
   - 所有 “Solution workflow” 小节；
   - 每个公式、图表、表格所在段落；
   - Table 5（Classical vs. QUBO results）。
2. 准备参考数据：`output/Q1~Q4/solve_log.txt`、`output/Q1~Q4/solution*.xlsx`、`Paper/figures/understanding-Q*.txt`。仅用于提取数据/描述，禁止在正文引用其路径。

## 2. 摘要优化
1. 维持 Problem 1–4 分段结构；在每段中用 `\textbf{}` 加粗最关键术语（如 “Classical UC”、“Network UC”、“QUBO”、“Scale Reduction”）。
2. 针对 “highlighting the trade-offs in quantum formulations” 的描述：引用具体指标（如功率残差、启停违反、能量值）说明哪些约束受到影响，以及为何形成权衡。
3. 删除重复句子；确保每段遵循 “方法 → 数值 → 结论” 顺序。

## 3. 删除 Solution workflow 段
1. 搜索 “Solution workflow” 或类似标题，整段移除。
2. 若段落包含必要的实现说明，将关键信息融入模型描述或结果分析中，但不保留标题。

## 4. 公式解释增强
1. 遍历所有 `equation`/`align` 环境，确保紧随每个公式后有 2–3 句解释，包括：
   - 公式中符号的物理含义；
   - 公式对整体模型的作用或约束之间的联系；
   - 与其他方程联合生效的说明。
2. 参考 `.idea` 笔记和 `Paper/figures/understanding-*` 中的解释，补充必要背景（例如 N−1 场景、QUBO 惩罚来源）。
3. 若已有解释过于简略，扩写但保持紧凑；若缺失解释则新增段落。

## 5. 图像说明与位置校验
1. 对每张图（Q1–Q4）执行：
   - 确认其 `\includegraphics` 所在章节与题号一致；若不一致，移动至正确章节并更新引用编号。
   - 在图像附近增加独立段落，引用 `Paper/figures/understanding-Q*.txt` 提供的要点，至少包含：轴/色阶含义、主要观察、对模型的启示。
2. 确认正文中引用顺序正确（先引用再插图）；若有跨节引用，说明原因。

## 6. 清理文件路径表述
1. 搜索 `output/`、`solve_log`、`solution_variables` 等字样，将其替换为描述性表述，例如 “求解日志显示……”、“调度导出表明……”，并在必要时添加脚注说明“数据来自求解日志”，不出现路径。
2. 若段落引用日志中的特定表格或列，将数据提取写入新的 `table`/`longtable` 或正文。

## 7. Q3 模型特色补充
1. 强化 Problem 3 文本，说明 slack 变量设计的目的（弥补离散编码对约束的影响），包括：
   - slack 定义方式与 QUBO 位结构；
   - slack 如何被惩罚项吸收；
   - 对求解残差的影响（引用统计数据）。
2. 在 Q3 章节加入一段“模型核心”描述，解释为何该构造凸显本论文的差异化。

## 8. 替换 Table 5 内容
1. 删除原 “Classical vs. QUBO results” 表格。
2. 新建表格对比 Q1 与 Q3 中 `u_{i,t}` 与 `P_{i,t}` 的差异，可采用：
   - 选取代表时段（峰值、低谷）列出两个模型的 on/off 状态及出力；
   - 或者统计各机组的启停次数、最大出力差。
3. 数据来源：`output/Q1/solve_log.txt`、`output/Q3/solve_log.txt` 或相关 Excel；整理为 `booktabs` 表格，配文字分析，强调量子解的跳变特性。

## 9. Problem 4 核心说明
1. 在 Problem 4 章节补充对“去除 slack/压缩比特”的详细阐释：
   - 列出原始 QUBO 位宽与目标位宽；
   - 说明删减 slack、参数范围、场景筛选的具体操作；
   - 描述这些操作如何满足 Kaiwu 硬件限制并保持可行性。
2. 将此解释与图 Figure~(Q4) 对应，标明 Hamiltonian/成本变化。

## 10. 终审
1. 通读全文，确认：
   - 摘要已加粗关键字且阐明量子权衡；
   - 无 Solution workflow 段；
   - 所有公式、图表解释充足且无文件路径；
   - Q3/Q4 特性描述完整。
2. 运行 LaTeX 编译两遍，确保图表/公式引用无警告。
3. 在 `.idea/Paper04_notes.md` 记录本轮改动与仍需补充的数据项（若有）。
