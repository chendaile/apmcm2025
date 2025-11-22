---
title: "Q2-QUBO: UC with Network, N−1 Security, Spinning Reserve, Flexible Load Allocation (without Minimum Inertia)"
---
# Problem 2 → QUBO Reformulation (without Minimum Inertia)

本文件在 Q2 的原始模型基础上，去除 Minimum Inertia 约束，将问题完整转写为标准 QUBO 形式：

\[
\min_{x\in\{0,1\}^N} x^\mathsf{T} Q x
\]

其中：

- 所有决策变量（含原来的连续变量）都用 0–1 变量编码；
- 原目标函数 + 所有约束统一写成二次多项式；
- 所有约束通过惩罚项并入目标函数，不再显式出现。

---

## 1. 集合与索引

与 Q2 原问题相同：

- 机组集合：\(\mathcal{I}\)
- 母线集合：\(\mathcal{B}\)
- 线路集合：\(\mathcal{L}\)
- 时段集合：\(\mathcal{T} = \{1,\dots,T\}\)（本题 \(T=24\)）

N−1 场景集合：

- 机组故障场景：\(\mathcal{C}^G = \mathcal{I}\)，每个 \(g\in\mathcal{C}^G\) 表示机组 \(g\) 故障
- 线路故障场景：\(\mathcal{C}^L = \mathcal{L}\)，每个 \(\ell\in\mathcal{C}^L\) 表示线路 \(\ell\) 故障

---

## 2. 参数（与原 Q2 一致，略）

仅列出与 QUBO 结构密切相关的部分：

- 单机出力上下限：\(P_i^{\min}, P_i^{\max}\)
- 燃料成本系数：\(a_i,b_i,c_i\)
- 启停成本：\(SU_i, SD_i\)
- 最小开停机时间：\(UT_i, DT_i\)
- 爬坡上下限：\(RU_i, RD_i\)
- 线路电抗：\(x_\ell\)，潮流限额：\(F_\ell^{\max}\)
- 时段总负荷：\(D_t\)
- bus–unit、bus–line 拓扑关系（通过集合 \(\mathcal{I}(b), \delta^+(b), \delta^-(b)\) 等表示）
- 备用需求：\(R_t^{\text{req}}\)（如原问题给出）
- 参考母线：\(b_0\)

问题中涉及的所有其他数值参数（如惯量常数 \(H_i\)）在本 QUBO 中 **不再使用**，因为 Minimum Inertia 约束已删除。

---

## 3. 变量定义与二值化

### 3.1 原本是 0–1 的变量

这些变量直接进入 QUBO：

- 机组开停状态：
  \[
  u_{i,t} \in \{0,1\} \quad (\forall i\in\mathcal{I}, t\in\mathcal{T})
  \]
- 启机：
  \[
  y_{i,t} \in \{0,1\}
  \]
- 停机：
  \[
  z_{i,t} \in \{0,1\}
  \]

### 3.2 连续变量统一用 0–1 编码

对任意一个连续变量 \(Z\)（下面会具体列举），设其允许范围为：
\[
Z^{\min} \le Z \le Z^{\max}.
\]

选择一个比特数 \(K_Z\)，引入二元变量：
\[
z_{k} \in \{0,1\},\quad k=0,\dots,K_Z-1,
\]
并定义：
\[
Z = Z^{\min} + \sum_{k=0}^{K_Z-1} \delta_{Z,k} \, z_k,
\]
其中 \(\delta_{Z,k}\) 为权重，常用二进制权重：
\[
\delta_{Z,k} = 2^k \Delta_Z,\quad
\Delta_Z = \frac{Z^{\max}-Z^{\min}}{2^{K_Z}-1}.
\]

对 Problem 2 中所有连续变量分别进行编码，包括但不限于：

1. 基态机组出力：
   \[
   P_{i,t} = P_i^{\min} u_{i,t}

   + \sum_{k=0}^{K_P-1} \delta_{P,i,k} \, x^P_{i,t,k},\quad x^P_{i,t,k}\in\{0,1\},
     \]
     \(\delta_{P,i,k}\) 通常可统一为 \(\delta_{P,k}\)。
2. 母线电压相角：
   \[
   \theta_{b,t} = \theta_b^{\min}

   + \sum_{k=0}^{K_\theta-1} \delta_{\theta,b,k}\, x^\theta_{b,t,k},
     \]
     对参考母线 \(b_0\) 可不给变量而直接固定为 0（见后文）。
3. 线路潮流：
   \[
   F_{\ell,t} = F_\ell^{\min}

   + \sum_{k=0}^{K_F-1} \delta_{F,\ell,k}\, x^F_{\ell,t,k}.
     \]
4. 机组备用：
   \[
   R_{i,t} = R_i^{\min}

   + \sum_{k=0}^{K_R-1} \delta_{R,i,k} \, x^R_{i,t,k}.
     \]
5. 母线负荷分配：
   \[
   D_{b,t} = D_{b,t}^{\min}

   + \sum_{k=0}^{K_D-1} \delta_{D,b,k}\, x^D_{b,t,k}.
     \]
6. 机组故障场景 \(g\in\mathcal{C}^G\) 中的变量（每个场景一套）：

   - 机组出力：
     \[
     P_{i,t}^{(g)} = P_{i}^{(g),\min}
     + \sum_k \delta_{P^{(g)},i,k}\, x^{P,(g)}_{i,t,k},
       \]
   - 出力增量：
     \[
     \Delta P_{i,t}^{(g)} = \Delta P_{i}^{(g),\min}
     + \sum_k \delta_{\Delta P^{(g)},i,k}\, x^{\Delta P,(g)}_{i,t,k},
       \]
   - 母线相角：
     \[
     \theta_{b,t}^{(g)} = \theta_{b}^{(g),\min}
     + \sum_k \delta_{\theta^{(g)},b,k}\, x^{\theta,(g)}_{b,t,k},
       \]
   - 线路潮流：
     \[
     F_{\ell,t}^{(g)} = F_{\ell}^{(g),\min}
     + \sum_k \delta_{F^{(g)},\ell,k}\, x^{F,(g)}_{\ell,t,k}.
       \]
7. 线路故障场景 \([\ell]\in\mathcal{C}^L\) 中的变量（每条故障线路一套）：

   - 机组出力 \(P_{i,t}^{[\ell]}\)、出力增量 \(\Delta P_{i,t}^{[\ell]}\)
   - 母线相角 \(\theta_{b,t}^{[\ell]}\)
   - 各条线路潮流 \(F_{\ell',t}^{[\ell]}\)（其中故障线路 \(\ell\) 本身应为 0）

形式同上，用相应的权重 \(\delta_{\cdot}\) 和 0–1 变量 \(x^{\cdot,[\ell]}_{\cdot}\) 表示。

---

## 4. QUBO 变量向量

将所有 0–1 变量按任意固定顺序排成一个长向量：

\[
x = \Big(
u_{i,t},\, y_{i,t},\, z_{i,t},\,
x^P_{i,t,k},\, x^\theta_{b,t,k},\, x^F_{\ell,t,k},\,
x^R_{i,t,k},\, x^D_{b,t,k},
x^{P,(g)}_{i,t,k},\, x^{\Delta P,(g)}_{i,t,k},\, x^{\theta,(g)}_{b,t,k},\, x^{F,(g)}_{\ell,t,k},
x^{P,[\ell]}_{i,t,k},\, x^{\Delta P,[\ell]}_{i,t,k},\, x^{\theta,[\ell]}_{b,t,k},\, x^{F,[\ell]}_{\ell',t,k},
\text{（如有）各不等式的 slack 比特}
\Big).
\]

所有约束与目标函数最终都要写为 \(x\) 的二次型 \(x^\mathsf{T} Q x\)。

---

## 5. 原始目标函数的二次化

Problem 2 的基态成本目标函数为：
\[
\min
\sum_{t\in\mathcal{T}} \sum_{i\in\mathcal{I}}
\Big(
a_i P_{i,t}^2 + b_i P_{i,t} + c_i u_{i,t}

- SU_i y_{i,t} + SD_i z_{i,t}
  \Big).
  \]

将每个 \(P_{i,t}\) 用其二值化表示代入：
\[
P_{i,t}
= P_i^{\min} u_{i,t} + \sum_k \delta_{P,i,k}\, x^P_{i,t,k}.
\]

展开后会得到：

- 常数项 \(c_0\)（对最优解无影响，可以忽略）；
- 一次项 \(\sum_p \alpha_p x_p\)；
- 二次项 \(\sum_{p\le q} \beta_{pq} x_p x_q\)。

因此可写为一个 QUBO 型：
\[
f_{\text{cost}}(x) = x^\mathsf{T} Q_{\text{cost}} x,
\]
其中 \(Q_{\text{cost}}\) 的元素由上述展开得到。

---

## 6. 约束罚函数化的一般原则

### 6.1 等式约束

对任意线性等式约束
\[
h(x) = 0,
\]
直接加入罚项
\[
\lambda_h \, h(x)^2,
\]
其中 \(\lambda_h > 0\) 是足够大的罚系数。
因为 \(h(x)\) 是关于 \(x\) 的线性函数，故 \(h(x)^2\) 是二次多项式，符合 QUBO 形式。

### 6.2 不等式约束

对线性不等式
\[
g(x) \le 0,
\]
严格的 QUBO 处理方法是引入非负松弛变量 \(s\ge 0\)，使之成为：
\[
g(x) + s = 0,\quad s\ge 0.
\]

再对 \(s\) 做二值化：
\[
s = \sum_{k=0}^{K_s-1} \delta_{s,k} \, s_k,\quad s_k\in\{0,1\},
\]
并将等式
\[
h(x,s) = g(x) + s = 0
\]
加入罚项
\[
\lambda_g \, h(x,s)^2.
\]

这样所有不等式也转化为纯二次多项式，不出现 \(\max\) 之类非多项式操作，模型保持“严格 QUBO”。

下文中如有 \(g(x)\le 0\) 的写法，均理解为采用上述 slack 变量方法处理。

---

## 7. 基态 UC 约束的 QUBO 形式

### 7.1 出力上下限

原约束：
\[
P_i^{\min} u_{i,t} \le P_{i,t} \le P_i^{\max} u_{i,t}.
\]

可以通过编码直接保证范围（选择 \(Z^{\min}=0\), \(Z^{\max}=P_i^{\max}\) 且乘以 \(u_{i,t}\)），也可以显式用不等式约束：

- 上界：
  \[
  g^{P,\text{up}}_{i,t}(x) = P_{i,t}(x) - P_i^{\max} u_{i,t} \le 0.
  \]
- 下界：
  \[
  g^{P,\text{low}}_{i,t}(x) = P_i^{\min} u_{i,t} - P_{i,t}(x) \le 0.
  \]

分别引入 slack 变量 \(s^{P,\text{up}}_{i,t}\)、\(s^{P,\text{low}}_{i,t}\)，得到等式：
\[
h^{P,\text{up}}_{i,t}(x,s)
= g^{P,\text{up}}_{i,t}(x) + s^{P,\text{up}}_{i,t} = 0,
\]
\[
h^{P,\text{low}}_{i,t}(x,s)
= g^{P,\text{low}}_{i,t}(x) + s^{P,\text{low}}_{i,t} = 0.
\]

罚项：
\[
Q_}
===

\lambda_{P,\text{lim}}
\sum_{i,t}
\Big(
\big(h^{P,\text{up}}_{i,t}(x,s)\big)^2
+
\big(h^{P,\text{low}}_{i,t}(x,s)\big)^2
\Big).
\]

### 7.2 启停逻辑

原约束：
\[
u_{i,t} - u_{i,t-1} = y_{i,t} - z_{i,t},\quad
y_{i,t} + z_{i,t} \le 1.
\]

等式部分：
\[
h^}_(x)
= u_ - u_ - y_ + z_,
\]
罚项：
\[
Q_}
===

\lambda_{\text{logic,eq}}
\sum_{i,t} \big(h^{\text{logic}}_{i,t}(x)\big)^2.
\]

不等式 \(y_+z_\le 1\)：
\[
g^}_(x) = y_ + z_ - 1 \le 0,
\]
引入 slack \(s^}_\)：
\[
h^}_(x,s)
========

g^}_(x)
+
s^}_
= 0,
\]
罚项：
\[
Q_}
===

\lambda_{\text{logic,ineq}}
\sum_{i,t} \big(h^{\text{startstop}}_{i,t}(x,s)\big)^2.
\]

### 7.3 最小开停机时间

原约束：
\[
\sum_{\tau=t}^{t+UT_i-1} u_{i,\tau} \ge UT_i y_{i,t},
\]
\[
\sum_{\tau=t}^{t+DT_i-1} (1 - u_{i,\tau}) \ge DT_i z_{i,t}.
\]

写为不等式形式：

最小开机时间：
\[
g^_(x)
======

UT_i y_{i,t} - \sum_{\tau=t}^{t+UT_i-1} u_{i,\tau}
\le 0.
\]

最小停机时间：
\[
g^_(x)
======

DT_i z_{i,t} - \sum_{\tau=t}^{t+DT_i-1} (1 - u_{i,\tau})
\le 0.
\]

引入 slack 变量 \(s^{UT}_{i,t}, s^{DT}_{i,t}\)：
\[
h^{UT}_{i,t}(x,s) = g^{UT}_{i,t}(x) + s^{UT}_{i,t} = 0,
\]
\[
h^{DT}_{i,t}(x,s) = g^{DT}_{i,t}(x) + s^{DT}_{i,t} = 0.
\]

罚项：
\[
Q_
==

\lambda_{UT}\sum_{i,t} \big(h^{UT}_{i,t}(x,s)\big)^2
+
\lambda_{DT}\sum_{i,t} \big(h^{DT}_{i,t}(x,s)\big)^2.
\]

### 7.4 爬坡约束

原约束：
\[
P_{i,t} - P_{i,t-1} \le RU_i,
\quad
P_{i,t-1} - P_{i,t} \le RD_i.
\]

写为：
\[
g^{RU}_{i,t}(x) = P_{i,t}(x) - P_{i,t-1}(x) - RU_i \le 0,
\]
\[
g^{RD}_{i,t}(x) = P_{i,t-1}(x) - P_{i,t}(x) - RD_i \le 0.
\]

引入 slack 变量 \(s^{RU}_{i,t}, s^{RD}_{i,t}\)：
\[
h^{RU}_{i,t}(x,s) = g^{RU}_{i,t}(x) + s^{RU}_{i,t} = 0,
\]
\[
h^{RD}_{i,t}(x,s) = g^{RD}_{i,t}(x) + s^{RD}_{i,t} = 0.
\]

罚项：
\[
Q_
==

\lambda_{RU}\sum_{i,t} \big(h^{RU}_{i,t}(x,s)\big)^2
+
\lambda_{RD}\sum_{i,t} \big(h^{RD}_{i,t}(x,s)\big)^2.
\]

---

## 8. Flexible Load Allocation 约束

### 8.1 总负荷平衡

原约束：
\[
\sum_{b\in\mathcal{B}} D_{b,t} = D_t.
\]

定义：
\[
h^{D}_{t}(x) =
\sum_{b} D_{b,t}(x) - D_t.
\]

罚项：
\[
Q_{D,\text{bal}} =
\lambda_{D,\text{bal}}
\sum_{t} \big(h^{D}_{t}(x)\big)^2.
\]

若已通过编码保证 \(D_{b,t}\ge 0\)，可不再为非负性添加额外罚项。

---

## 9. 基态 DC 网络约束

### 9.1 母线功率平衡

对每个母线 \(b\in\mathcal{B}\)、时段 \(t\in\mathcal{T}\)：

\[
\sum_{i\in\mathcal{I}(b)} P_{i,t}

- D_{b,t}
- \sum_{\ell\in\delta^+(b)} F_{\ell,t}

+ \sum_{\ell\in\delta^-(b)} F_{\ell,t}
  = 0.
  \]

定义线性函数：
\[
h^}_(x)
=======

\sum_{i\in\mathcal{I}(b)} P_{i,t}(x)

- D_{b,t}(x)
- \sum_{\ell\in\delta^+(b)} F_{\ell,t}(x)

+ \sum_{\ell\in\delta^-(b)} F_{\ell,t}(x).
  \]

罚项：
\[
Q_{\text{bus}} =
\lambda_{\text{bus}}
\sum_{b,t} \big(h^{\text{bus}}_{b,t}(x)\big)^2.
\]

### 9.2 DC 潮流方程

对每条线路 \(\ell\in\mathcal{L}\)、时段 \(t\in\mathcal{T}\)：

\[
F_
==

\frac{\theta_{\text{from}(\ell),t} - \theta_{\text{to}(\ell),t}}{x_\ell}.
\]

定义：
\[
h^}_(x)
=======

F_(x)
-----

\frac{\theta_{\text{from}(\ell),t}(x) - \theta_{\text{to}(\ell),t}(x)}{x_\ell}.
\]

罚项：
\[
Q_{\text{DC}} =
\lambda_{\text{DC}}
\sum_{\ell,t} \big(h^{\text{DC}}_{\ell,t}(x)\big)^2.
\]

### 9.3 线路容量约束

原约束：
\[

- F_\ell^{\max} \le F_{\ell,t} \le F_\ell^{\max}.
  \]

写成两个不等式：
\[
g^{F,\text{up}}_{\ell,t}(x) = F_{\ell,t}(x) - F_\ell^{\max} \le 0,
\]
\[
g^{F,\text{low}}_{\ell,t}(x) = -F_{\ell,t}(x) - F_\ell^{\max} \le 0.
\]

各自引入 slack：
\[
h^{F,\text{up}}_{\ell,t}(x,s)
= g^{F,\text{up}}_{\ell,t}(x) + s^{F,\text{up}}_{\ell,t} = 0,
\]
\[
h^{F,\text{low}}_{\ell,t}(x,s)
= g^{F,\text{low}}_{\ell,t}(x) + s^{F,\text{low}}_{\ell,t} = 0.
\]

罚项：
\[
Q_}
===

\lambda_{F,\text{lim}}
\sum_{\ell,t}
\Big(
\big(h^{F,\text{up}}_{\ell,t}(x,s)\big)^2
+
\big(h^{F,\text{low}}_{\ell,t}(x,s)\big)^2
\Big).
\]

### 9.4 参考母线

选定参考母线 \(b_0\)，约束：
\[
\theta_{b_0,t} = 0.
\]

通常可直接不为 \(\theta_{b_0,t}\) 建立变量，而是作为常数 0；若仍要用罚函数形式：

\[
h^{\theta_0}_t(x) = \theta_{b_0,t}(x),
\quad
Q_{\theta_0} =
\lambda_{\theta_0}
\sum_{t} \big(h^{\theta_0}_t(x)\big)^2.
\]

---

## 10. Spinning Reserve 约束

### 10.1 单机备用能力

原约束：
\[
0 \le R_{i,t} \le P_i^{\max} u_{i,t} - P_{i,t}.
\]

若编码保证 \(R_\ge 0\)，只需处理上界：
\[
g^}_(x)
=======

R_{i,t}(x) - (P_i^{\max} u_{i,t} - P_{i,t}(x)) \le 0.
\]

引入 slack \(s^}_\)：
\[
h^}_(x,s)
========

g^{R,\text{up}}_{i,t}(x) + s^{R,\text{up}}_{i,t} = 0.
\]

罚项：
\[
Q_}
===

\lambda_{R,\text{up}}
\sum_{i,t} \big(h^{R,\text{up}}_{i,t}(x,s)\big)^2.
\]

### 10.2 系统备用需求（若在原 Q2 中给出）

例如：
\[
\sum_{i\in\mathcal{I}} R_{i,t} \ge R_t^{\text{req}}.
\]

写成：
\[
g^}_t(x)
========

R_t^{\text{req}} - \sum_i R_{i,t}(x) \le 0.
\]

引入 slack \(s^}_t\)：
\[
h^}_t(x,s)
==========

g^{R,\text{sys}}_t(x) + s^{R,\text{sys}}_t = 0.
\]

罚项：
\[
Q_}
===

\lambda_{R,\text{sys}}
\sum_t \big(h^{R,\text{sys}}_t(x,s)\big)^2.
\]

---

## 11. N−1 机组故障场景 \(\mathcal^G\)

对每个机组故障场景 \(g\in\mathcal{C}^G=\mathcal{I}\)，有一套对应场景变量
\(\{P_{i,t}^{(g)}, \Delta P_{i,t}^{(g)}, \theta_{b,t}^{(g)}, F_{\ell,t}^{(g)}\}\)。

### 11.1 故障机组停运

原约束：
\[
P_{g,t}^{(g)} = 0.
\]

可直接令 \(P_^\) 无变量、固定为 0；或通过等式罚函数：
\[
h^,(g)}_t(x)
============

P_{g,t}^{(g)}(x),
\quad
Q_{\text{out},(g)} =
\lambda_{\text{out},(g)}
\sum_{t} \big(h^{\text{out},(g)}_t(x)\big)^2.
\]

### 11.2 再调度关系

原约束：
\[
P_{i,t}^{(g)} = P_{i,t} + \Delta P_{i,t}^{(g)}.
\]

定义：
\[
h^_(x)
======

P_{i,t}^{(g)}(x) - P_{i,t}(x) - \Delta P_{i,t}^{(g)}(x).
\]

罚项：
\[
Q_
==

\lambda_{P,(g)}
\sum_{g\in\mathcal{C}^G}
\sum_{i,t}
\big(h^{P,(g)}_{i,t}(x)\big)^2.
\]

### 11.3 再调度能力约束

原约束（示例）：
\[
0 \le \Delta P_{i,t}^{(g)} \le R_{i,t},
\quad
0 \le P_{i,t}^{(g)} \le P_i^{\max} u_{i,t}.
\]

同前面的不等式处理方式，引入 slack，得到一组等式：
\[
h^{\Delta P,(g),\text{up}}_{i,t}(x,s)
\quad\text{与}\quad
h^{P,(g),\text{up}}_{i,t}(x,s),
\]
对应的罚项：
\[
Q_{\Delta P,(g)} + Q_{P,\text{lim},(g)}
\]
形式完全类似，不再展开。

### 11.4 故障场景下的节点平衡、DC 潮流、线路限额

对每个场景 \(g\)、母线 \(b\)、线路 \(\ell\)、时段 \(t\)：

- 节点平衡：
  \[
  \sum_{i\in\mathcal{I}(b)} P_{i,t}^{(g)}

  - D_{b,t}
  - \sum_{\ell\in\delta^+(b)} F_{\ell,t}^{(g)}

  + \sum_{\ell\in\delta^-(b)} F_{\ell,t}^{(g)}
    = 0,
    \]
    定义 \(h^{\text{bus},(g)}_{b,t}(x)\) 并加入罚项
    \(\lambda_{\text{bus},(g)} \sum (h^{\text{bus},(g)}_{b,t}(x))^2\)。
- DC 潮流：
  \[
  F_{\ell,t}^{(g)} =
  \frac{\theta_{\text{from}(\ell),t}^{(g)} - \theta_{\text{to}(\ell),t}^{(g)}}{x_\ell},
  \]
  定义 \(h^{\text{DC},(g)}_{\ell,t}(x)\) 并加入罚项。
- 线路限额、参考母线：
  与基态完全同形，只是变量替换为带上标 \((g)\) 的版本，罚系数可设为
  \(\lambda_{F,\text{lim},(g)}, \lambda_{\theta_0,(g)}\) 等。

---

## 12. N−1 线路故障场景 \(\mathcal^L\)

对每条线路故障场景 \([\ell]\in\mathcal{C}^L\)，有一套对应场景变量
\(\{P_{i,t}^{[\ell]}, \Delta P_{i,t}^{[\ell]}, \theta_{b,t}^{[\ell]}, F_{\ell',t}^{[\ell]}\}\)。

### 12.1 故障线路切除

原约束：
\[
F_{\ell,t}^{[\ell]} = 0.
\]

同样可直接固定为常数 0，或用等式罚函数：
\[
h^,[\ell]}_t(x) = F_^(x),
\quad
Q_,[\ell]}
==========

\lambda_{\text{cut},[\ell]}
\sum_t \big(h^{\text{cut},[\ell]}_t(x)\big)^2.
\]

### 12.2 再调度关系与能力约束

与机组故障场景完全类似：

- 再调度关系：
  \[
  P_{i,t}^{[\ell]} = P_{i,t} + \Delta P_{i,t}^{[\ell]},
  \]
  定义 \(h^{P,[\ell]}_{i,t}(x)\) 并加入罚项。
- 再调度能力：
  \[
  0 \le \Delta P_{i,t}^{[\ell]} \le R_{i,t},
  \quad
  0 \le P_{i,t}^{[\ell]} \le P_i^{\max} u_{i,t},
  \]
  用 slack 变量转化为等式并平方处罚。

### 12.3 故障场景下的节点平衡与 DC 潮流

对每个 \([\ell]\)、母线 \(b\)、线路 \(\ell'\neq \ell\)、时段 \(t\)：

- 节点平衡：
  \[
  \sum_{i\in\mathcal{I}(b)} P_{i,t}^{[\ell]}

  - D_{b,t}
  - \sum_{\ell'\in\delta^+(b)} F_{\ell',t}^{[\ell]}

  + \sum_{\ell'\in\delta^-(b)} F_{\ell',t}^{[\ell]}
    = 0,
    \]
    定义 \(h^{\text{bus},[\ell]}_{b,t}(x)\)，加入罚项。
- DC 潮流（对所有 \(\ell'\neq \ell\)）：
  \[
  F_{\ell',t}^{[\ell]} =
  \frac{\theta_{\text{from}(\ell'),t}^{[\ell]} - \theta_{\text{to}(\ell'),t}^{[\ell]}}{x_{\ell'}},
  \]
  定义 \(h^{\text{DC},[\ell]}_{\ell',t}(x)\)，加入罚项。
- 线路限额、参考母线：
  同样仿照基态与机组故障场景处理，使用场景上标 \([\ell]\)。

---

## 13. 最终 QUBO 模型

将所有部分合并，总的 Q 矩阵为：
\[
Q =
Q_{\text{cost}}

+ Q_{P,\text{lim}}
+ Q_{\text{logic,eq}} + Q_{\text{logic,ineq}}
+ Q_{UT,DT}
+ Q_{RU,RD}
+ Q_{D,\text{bal}}
+ Q_{\text{bus}} + Q_{\text{DC}} + Q_{F,\text{lim}} + Q_{\theta_0}
+ Q_{R,\text{up}} + Q_{R,\text{sys}}
+ \sum_{g\in\mathcal{C}^G}
  \big(
  Q_{\text{out},(g)} + Q_{P,(g)} + Q_{\Delta P,(g)} + Q_{P,\text{lim},(g)}
+ Q_{\text{bus},(g)} + Q_{\text{DC},(g)} + Q_{F,\text{lim},(g)} + Q_{\theta_0,(g)}
  \big)
  \]
  \[
+ \sum_{\ell\in\mathcal{C}^L}
  \big(
  Q_{\text{cut},[\ell]} + Q_{P,[\ell]} + Q_{\Delta P,[\ell]} + Q_{P,\text{lim},[\ell]}
+ Q_{\text{bus},[\ell]} + Q_{\text{DC},[\ell]}
+ Q_{F,\text{lim},[\ell]} + Q_{\theta_0,[\ell]}
  \big).
  \]

最终得到的 QUBO 为：

\[
\boxed{
\min_{x\in\{0,1\}^N} \; x^\mathsf{T} Q x
}
\]

其中：

- \(x\) 为前述所有 0–1 决策变量（含 slack 比特）的拼接向量；
- \(Q\) 的每个元素由：
  - 原始成本函数，
  - 以及每一条约束对应的线性函数平方展开
    的系数累加得到。

本文件给出的就是 Q2（去除 Minimum Inertia 后）的严格 QUBO 结构，可作为构造数值 Q 矩阵的完整公式说明。
