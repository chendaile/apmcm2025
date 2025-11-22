---
# **Q1-QUBO（严格版，含 slack 变量）**

**Classical UC → Strict QUBO Reformulation with Slack Variables**

本文件将经典机组组合（UC）模型转换为  **严格数学意义上的 QUBO** ：

[

\min_{x\in{0,1}^N} x^\mathsf T Q x

]

由于 QUBO 仅能处理“二次等式 penalty”，所有**不等式约束 (g(x)\le 0)** 必须用 slack 变量 (s\ge 0) 转化为：

[

g(x) + s = 0

]

并将 slack  **二值化** ，从而保证模型完全由 0–1 变量和二次项构成。
---

# --------------------------------------------

# **1. 变量定义（全部为 0–1）**

# --------------------------------------------

## 1.1 原本是二元的变量（直接进入 QUBO）

- 开机状态：

     [

     u\_{i,t}\in{0,1}

     ]

- 启机变量：

     [

     y\_{i,t}\in{0,1}

     ]

- 停机变量：

     [

     z\_{i,t}\in{0,1}

     ]

---

## 1.2 连续出力变量的二值化

原模型中的：

[

P\_{i,t}\in[P_i^{\min},P_i^{\max}]

]

采用 K 比特编码：

[

P*{i,t}=P_i^{\min} u*{i,t}

+\sum*{k=0}^{K_P-1}\delta*{i,k} x*{i,t,k},\quad x*{i,t,k}\in{0,1}

]

---

## 1.3 Slack 变量（二值化）

对每个不等式

[

g(x)\le0

]

引入 slack：

[

s=\sum*{k=0}^{K_s-1}\delta*{s,k} s_k,\quad s_k\in{0,1},\ s\ge0

]

再将：

[

g(x)+s=0

]

加入 QUBO。

---

# --------------------------------------------

# **2. 目标函数的 QUBO 形式**

# --------------------------------------------

UC 原始成本：

[

\sum\_{i,t}

(a*i P*{i,t}^2+b*i P*{i,t}+c*i u*{i,t}-SU*i y*{i,t}+SD*i z*{i,t})

]

代入二值化的 (P\_{i,t})，

展开后得到：

- 常数项（忽略）
- 一次项 (\alpha_p x_p)
- 二次项 (\beta\_{pq} x_p x_q)

整理为：

[

f*{\text{cost}}(x)=x^\mathsf T Q*{\text{cost}} x

]

---

# --------------------------------------------

# **3. 约束严格转化为 QUBO（全部等式）**

# --------------------------------------------

## **所有不等式 g(x)≤0 → 引入 slack：g(x)+s=0 → penalty：(g+s)^2**

---

# **3.1 功率平衡（等式，无需 slack）**

原约束：

[

\sum*i P*{i,t}=D_t

]

定义：

[

h^{\text{bal}} _t(x)=\sum_i P_ {i,t}(x)-D_t

]

Penalty：

[

Q*{\text{bal}}=\lambda*{\text{bal}} \sum_t (h^{\text{bal}}\_t(x))^2

]

---

# **3.2 出力上下限（严格版需要 slack）**

### 上界约束：

[

P*{i,t}-P_i^{\max}u*{i,t}\le0

]

引入 slack (s^{P,\text{up}}\_{i,t}\ge0)：

[

h^{P,\text{up}} _{i,t}=P_ {i,t}-P*i^{\max}u*{i,t}+s^{P,\text{up}}\_{i,t}=0

]

### 下界约束：

[

P*i^{\min}u*{i,t}-P\_{i,t}\le0

]

引入 slack (s^{P,\text{low}}\_{i,t}\ge0)：

[

h^{P,\text{low}} _{i,t}=P_i^{\min}u_ {i,t}-P*{i,t}+s^{P,\text{low}}*{i,t}=0

]

Penalty：

[

Q\_{P,\text{lim}}

=\lambda\_{P,\text{lim}}

\sum\_{i,t}\Big[

(h^{P,\text{up}} _{i,t})^2+(h^{P,\text{low}}_ {i,t})^2

\Big]

]

---

# **3.3 启停逻辑**

### 等式约束（无 slack）：

[

h\_{i,t}^{\text{logic}}=

u*{i,t}-u*{i,t-1}-y*{i,t}+z*{i,t}=0

]

Penalty：

[

Q\_{\text{logic,eq}}

=\lambda\_{\text{logic,eq}}

\sum*{i,t}(h*{i,t}^{\text{logic}})^2

]

---

# **3.4 最小开机时间（UT）**

原式：

[

\sum*{\tau=t}^{t+UT_i-1} u*{i,\tau}\ge UT*i y*{i,t}

]

整理：

[

g^{UT} _{i,t}=UT_i y_ {i,t}-\sum*{\tau=t}^{t+UT_i-1}u*{i,\tau}\le0

]

引入 slack (s^{UT}\_{i,t}\ge0)：

[

h^{UT} _{i,t}=g^{UT}_ {i,t}+s^{UT}\_{i,t}=0

]

Penalty：

[

Q\_{UT}=

\lambda*{UT}\sum*{i,t}(h^{UT}\_{i,t})^2

]

---

# **3.5 最小停机时间（DT）**

原式：

[

\sum*{\tau=t}^{t+DT_i-1}(1-u*{i,\tau})\ge DT*i z*{i,t}

]

整理：

[

g^{DT} _{i,t}=DT_i z_ {i,t}-\sum*{\tau=t}^{t+DT_i-1}(1-u*{i,\tau})\le0

]

引入 slack：

[

h^{DT} _{i,t}=g^{DT}_ {i,t}+s^{DT}\_{i,t}=0

]

Penalty：

[

Q\_{DT}=

\lambda*{DT}\sum*{i,t}(h^{DT}\_{i,t})^2

]

---

# **3.6 爬坡约束 RU/RD**

原约束：

[

P*{i,t}-P*{i,t-1}\le RU_i

]

[

P*{i,t-1}-P*{i,t}\le RD_i

]

整理：

[

g^{RU} _{i,t}=P_ {i,t}-P\_{i,t-1}-RU_i\le0

]

[

g^{RD} _{i,t}=P_ {i,t-1}-P\_{i,t}-RD_i\le0

]

引入 slack：

[

h^{RU} _{i,t}=g^{RU}_ {i,t}+s^{RU} \*{i,t}=0

]

[

h^{RD}_ {i,t}=g^{RD} _{i,t}+s^{RD}\* {i,t}=0

]

Penalty：

[

Q\_{RU,RD}=

\lambda\_{RU}!\sum(h^{RU})^2

+\lambda\_{RD}!\sum(h^{RD})^2

]

---

# --------------------------------------------

# **4. 最终 QUBO 形式**

# --------------------------------------------

所有部分合并：

[

Q=

Q\_{\text{cost}}

+Q\_{\text{bal}}

+Q\_{P,\text{lim}}

+Q\_{\text{logic,eq}}

+Q\_{UT}

+Q\_{DT}

+Q\_{RU,RD}

]

最终：

[

\boxed{

\min\_{x\in{0,1}^N} x^\mathsf T Q x

}

]

其中

- (x) 包含所有 0–1 变量（含 slack 比特）
- (Q) 为上述所有 penalty 二次项的系数累加

---
