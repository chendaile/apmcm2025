已处理：Problem 3 章节以“Model Core”段（[`Paper/main.tex`](Paper/main.tex:436-441)）覆盖原“Solution workflow”内容，量子求解流程与前文引用保持一致。
已处理：Problem 4 章节在缩减策略叙述（[`Paper/main.tex`](Paper/main.tex:478-489)）中交代实施步骤与硬件执行流程。

- 调整 Table~\ref{tab:q3_compare} 列宽，使用 `p{5.8cm}` 保证 Metric 列换行不过宽（[`Paper/main.tex`](Paper/main.tex:448-464)）。
- 引入四篇公开文献：Padhy (2004)、Carri\'on & Arroyo (2006)、Lucas (2014)、Glover et al. (2019)，分别在 UC 背景、经典 MILP、QUBO 编码与惩罚调优段落中增加 \cite 引用，并替换参考文献列表（[`Paper/main.tex`](Paper/main.tex:53-86,430-466,544-549)）。

---

2025-11-23 System reserve cleanup：

- 删除了系统层面的 $\sum_i R_{i,t} \ge 600$ 约束，仅保留 per-unit 备用上界（[`Paper/main.tex`](Paper/main.tex:317-324)），并在相邻文字说明中交代由 Benders 切面自动驱动备用需求。
- 更新 Figure~\ref{fig:q2_reserve} 的 caption 与描述，强调“无固定配额但 U1/U2 仍保留大部头寸”（[`Paper/main.tex`](Paper/main.tex:411-416)）。
- 当前未重新编译，仍需在 CJK 方案确定后整体再跑 `latexmk` 以验证编号与图表引用。

---

2025-11-22 Step10 终审记录：

- 摘要：四段均以加粗关键词（Classical UC / Network UC / QUBO / Scale Reduction）开头，量化指标与费用、时间及能量值与日志一致，关键词行保持 `Unit Commitment…` 不变（[`Paper/main.tex`](Paper/main.tex:29-39)）。
- Problem 1–4 公式与说明：所有核心方程均在相邻段落补充语义解释（例如 [`Paper/main.tex`](Paper/main.tex:174-211,239-415)），且描述中未出现绝对路径或外部文件引用。
- 图表：Q1/Q2/Q3/Q4 图表与表格均带完整 caption，新增 Table~\ref{tab:q3_compare} 及其引用闭环正常（[`Paper/main.tex`](Paper/main.tex:448-472)）。
- Path 清理：全文未再出现“Solution workflow”字样或 c:/… 形式路径（全局检索为空）。
- Problem 3/4 交叉引用：Model Core 段与 Table~\ref{tab:q3_compare} 的数据回指 Problem 1 基线与 Q3/Q4 日志一致；Problem 4 的缩减与硬件段落与前文解释互引用（[`Paper/main.tex`](Paper/main.tex:436-499)）。
- LaTeX 编译：`latexmk -pdf main.tex`（2025-11-22 19:57 UTC+8）因 pdfLaTeX 无法处理多段中文叙述而失败，首个错误出现在 [`Paper/main.tex`](Paper/main.tex:180) 并在 [`Paper/main.log`](Paper/main.log:942-2790) 连锁触发，提示需增加 CJK 支持（如 `xeCJK` / `ctex`）或改用 XeLaTeX。由于首次编译中断，产生的 `LastPage` 与 `eq:q1_*` 引用警告尚未回填，应在修复编码方案后复编两次验证。
- 待补：1）确定统一的中文排版方案（建议切换 XeLaTeX 并启用 `xeCJK`），或将中文段落转换为可被 pdfLaTeX 处理的命令；2）待上述问题解决后重新运行 `latexmk -pdf` 至成功并确认无引用/图表警告。
