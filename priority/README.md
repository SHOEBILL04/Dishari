# Priority Module (`/priority`)

The Priority module forecasts topic question shares and expected question counts for each of the 10 official BCS preliminary subjects using a Bayesian **Dirichlet-Multinomial model with exponential recency decay and shrinkage**.

---

## 1. Architectural Guardrails

- **Strict Subject Mark Invariance**: Total subject marks (e.g., 35 for Bangla, 30 for Bangladesh Affairs, 15 for Math) are fixed by the official BPSC circular and are **never modified by statistical models**.
- **Inside-Subject Estimation**: The model only forecasts the topic distribution $\boldsymbol{\theta}_s$ *within* each subject, ensuring $\sum_{t \in T_s} \mathbb{E}[\theta_{s, t}] = 1.0$ and $\sum_{t \in T_s} \text{Expected Questions}_{s, t} = \text{Subject Marks}$.
- **Zero Lookahead Leakage**: When evaluated, all hyperparameters ($t_{1/2}, S$) are tuned strictly via nested walk-forward over historical exams prior to the predicted exam.

---

## 2. Statistical Model Formulation

For subject $s$ with active topics $T_s$:

1. **Exponential Recency Decay**:
   Historical exams $i < k$ receive recency weights:
   $$w_i(k) = 2^{-(k - i) / t_{1/2}}$$
   where $t_{1/2}$ is the decay half-life hyperparameter.

2. **Syllabus Transition Normalization**:
   Topics track their introduction via `topics.syllabus_version_introduced`. For topics introduced in newer syllabus versions (e.g., Computer & IT in `bcs-35th-current`), older exams (< 35th BCS) under `bcs-pre-35th` are **not treated as zero-count observations**.
   Instead, effective counts are accumulated only over active exams $E_t$ and exposure-normalized:
   $$\bar{r}_{s, t} = \frac{\sum_{i \in E_t} w_i c_{i, s, t}}{\sum_{i \in E_t} w_i}, \quad \hat{c}_{s, t} = \bar{r}_{s, t} \cdot \sum_{i < k} w_i$$

3. **Bayesian Shrinkage Toward Subject Mean**:
   Prior pseudocounts shrink individual topics toward the equal baseline share ($m_{s, t} = 1 / |T_s|$):
   $$\alpha_{s, t}^* = S \cdot m_{s, t} + \hat{c}_{s, t}$$
   where $S$ is the shrinkage strength hyperparameter.

4. **Posterior Mean Share & 80% Credible Intervals**:
   - Posterior Mean Share: $\mathbb{E}[\theta_{s, t}] = \frac{\alpha_{s, t}^*}{\sum_{t'} \alpha_{s, t'}^*}$
   - 80% Credible Interval: Computed via the Beta marginal distribution $\text{Beta}(\alpha_{s, t}^*, \alpha_0^* - \alpha_{s, t}^*)$ between the 10th and 90th percentiles using `scipy.stats.beta.ppf`.
   - Expected Questions: $\text{Marks}_s \times \mathbb{E}[\theta_{s, t}]$.

5. **News Signal Interface**:
   A placeholder interface accepts an optional `topic_id -> score` map for Bangladesh Affairs and International Affairs. When enabled, news intensity pseudocounts are blended into the Dirichlet posterior parameters.

---

## 3. Walk-Forward Backtesting

The backtesting engine ([`priority/backtest.py`](file:///home/rakibul/Projects/Dishari/priority/backtest.py)) tests the model against three baselines across 11 consecutive exams (35th to 45th BCS):
1. **Uniform Baseline**: Predicts equal share $1 / |T_s|$ for all active topics.
2. **All-Time Frequency Baseline**: Unweighted historical empirical frequencies with Laplace smoothing.
3. **Last-Exam-Only Baseline**: Topic shares from the immediate preceding exam with Laplace smoothing.

### Running the Backtest:
```bash
.venv/bin/python -m priority.backtest
```

### Backtest Performance Summary (35th to 45th BCS):
| Model / Baseline | Mean Absolute Error (MAE) ↓ | Log-Likelihood ↑ | Top-10 Hit Rate ↑ | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Dirichlet-Multinomial Model** | **0.0555** | **-24.96** | **100.0%** | **Champion** |
| All-Time Frequency Baseline | 0.0560 | -25.14 | 100.0% | Runner-up |
| Last-Exam-Only Baseline | 0.0719 | -25.31 | 100.0% | High Variance |
| Uniform Baseline | 0.0800 | -27.25 | 100.0% | Underfit |

Full statistical report with 95% bootstrap confidence intervals and per-subject breakdowns is generated at [`priority/backtest_report.md`](file:///home/rakibul/Projects/Dishari/priority/backtest_report.md).

---

## 4. Priority Tiers (Study Recommendations)

Based on the validated Dirichlet-Multinomial predictions:
- 🔴 **HIGH Priority**: Expected questions $\ge 2.5$ or top 25% share (must-master topics).
  - *Examples*: Modern Bangla Literature (17.5 questions), English Vocabulary & Idioms (10.1), Liberation War (9.2), Bangladesh Constitution (8.1), International Organizations (8.3), Verbal Reasoning (8.1).
- 🟡 **MEDIUM Priority**: Expected questions $\ge 1.0$ and $< 2.5$ (core breadth topics).
  - *Examples*: Ancient Bangla Literature (2.3), Samas (1.9), Spelling & Syntax (1.6), Elizabethan Literature (2.3).
- 🟢 **LOW Priority**: Expected questions $< 1.0$ (minor / rare topics).
  - *Examples*: Bangla Phonetics (0.8).
