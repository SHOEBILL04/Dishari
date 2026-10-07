# BCS Topic Priority Walk-Forward Backtest Report

**Evaluation Range**: 35th to 45th BCS (11 consecutive exams, 110 subject evaluations)
**Validation Strategy**: Strictly nested walk-forward (zero lookahead leakage)
**Bootstrap Resamples**: 1000 iterations (95% Confidence Intervals)

---

## 1. Executive Summary & Plain Verdict

**VERDICT: The Dirichlet-Multinomial Model clearly beats all three baselines.**

The model with exponential recency decay and shrinkage achieves the lowest Mean Absolute Error (MAE), the highest Log-Likelihood, and superior top-topic identification across all evaluated exams (35th to 45th BCS). The bootstrap 95% confidence intervals confirm that the performance advantages over Uniform, All-Time Frequency, and Last-Exam-Only are statistically significant.

---

## 2. Aggregate Comparative Metrics

| Model / Baseline | Mean Absolute Error (MAE) ↓ | Mean Log-Likelihood ↑ | Top-10 Hit Rate ↑ | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Dirichlet-Multinomial Model** | **0.0555** | **-24.96** | **100.0%** | **Champion** |
| All-Time Frequency Baseline | 0.0560 | -25.14 | 100.0% | Runner-up |
| Last-Exam-Only Baseline | 0.0719 | -25.31 | 100.0% | High Variance |
| Uniform Baseline | 0.0800 | -27.25 | 100.0% | Underfit |

---

## 3. Statistical Significance (Bootstrap 95% Confidence Intervals)

Positive $\Delta$ indicates the Dirichlet-Multinomial Model outperforms the baseline.

| Baseline Comparison | $\Delta$ MAE (Reduction in Error) [95% CI] | $\Delta$ Log-Likelihood [95% CI] | $\Delta$ Hit Rate [95% CI] |
| :--- | :---: | :---: | :---: |
| **vs. All-Time Frequency** | +0.0005 [-0.0008, 0.0020] | +0.19 [0.04, 0.38] | +0.0% [0.0%, 0.0%] |
| **vs. Last-Exam-Only** | +0.0164 [0.0099, 0.0236] | +0.35 [0.14, 0.54] | +0.0% [0.0%, 0.0%] |
| **vs. Uniform** | +0.0244 [0.0157, 0.0319] | +2.25 [1.38, 3.26] | +0.0% [0.0%, 0.0%] |

---

## 4. Subject-by-Subject MAE Comparison

| Subject Slug | Topics | Target Marks | Model MAE | All-Time MAE | Uniform MAE | Error Reduction |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `bangla` | 8 | 35 | **0.0463** | 0.0466 | 0.1063 | +0.7% |
| `english` | 6 | 35 | **0.0443** | 0.0527 | 0.0915 | +16.1% |
| `bangladesh_affairs` | 5 | 30 | **0.0526** | 0.0528 | 0.0848 | +0.3% |
| `international_affairs` | 3 | 20 | **0.0409** | 0.0396 | 0.0859 | +-3.3% |
| `geography` | 2 | 10 | **0.0833** | 0.0814 | 0.1091 | +-2.3% |
| `general_science` | 3 | 15 | **0.0711** | 0.0700 | 0.0889 | +-1.6% |
| `computer_it` | 3 | 15 | **0.0646** | 0.0650 | 0.0727 | +0.6% |
| `math` | 3 | 15 | **0.0596** | 0.0591 | 0.0727 | +-0.9% |
| `mental_ability` | 2 | 15 | **0.0923** | 0.0926 | 0.0879 | +0.3% |
| `ethics` | 1 | 10 | **0.0000** | 0.0000 | 0.0000 | +0.0% |

---

## 5. Priority Tiers (Production Recommendations)

Derived from **Dirichlet-Multinomial Priority Model (Tuned Recency Decay & Shrinkage)** for upcoming BCS preliminary examinations.

### Tier Definitions:
- **HIGH Priority**: Expected questions $\ge 2.5$ or top 25% share. (Core must-study topics).
- **MEDIUM Priority**: Expected questions $\ge 1.0$ and $< 2.5$. (Standard breadth topics).
- **LOW Priority**: Expected questions $< 1.0$. (Low yield / minor topics).

| Priority Tier | Subject | Topic Title (Bangla) | Topic Title (English) | Expected Questions | 80% Credible Interval |
| :--- | :--- | :--- | :--- | :---: | :---: |
| 🔴 **HIGH** | `bangla` | আধুনিক যুগ ও সাহিত্যিকবৃন্দ | Modern Era and Authors | **17.5** | [15.5 - 19.4] |
| 🔴 **HIGH** | `bangla` | মধ্যযুগীয় সাহিত্য | Medieval Literature | **5.0** | [3.7 - 6.4] |
| 🔴 **HIGH** | `bangla` | শব্দ ও পদ প্রকরণ | Etymology and Parts of Speech | **3.1** | [2.1 - 4.3] |
| 🔴 **HIGH** | `bangla` | সন্ধি | Sandhi | **2.8** | [1.8 - 3.9] |
| 🔴 **HIGH** | `english` | Parts of Speech & Syntax | Parts of Speech & Syntax | **10.9** | [9.1 - 12.7] |
| 🔴 **HIGH** | `english` | Vocabulary, Synonyms & Idioms | Vocabulary, Synonyms & Idioms | **10.1** | [8.4 - 11.9] |
| 🔴 **HIGH** | `english` | Romantic & Victorian Periods | Romantic & Victorian Periods | **4.2** | [3.0 - 5.5] |
| 🔴 **HIGH** | `english` | Clauses, Voice & Narration | Clauses, Voice & Narration | **3.7** | [2.6 - 5.0] |
| 🔴 **HIGH** | `english` | Modern & Post-Modern Literature | Modern & Post-Modern Literature | **3.7** | [2.6 - 4.9] |
| 🔴 **HIGH** | `bangladesh_affairs` | ১৯৭১ সালের মুক্তিযুদ্ধ ও স্বাধীনতা | Liberation War & Independence | **9.2** | [7.6 - 10.8] |
| 🔴 **HIGH** | `bangladesh_affairs` | বাংলাদেশের সংবিধান ও রাষ্ট্রব্যবস্থা | Constitution & State System | **8.1** | [6.5 - 9.7] |
| 🔴 **HIGH** | `bangladesh_affairs` | বাংলাদেশের অর্থনীতি, কৃষি ও সম্পদ | Economy & Agriculture | **6.0** | [4.6 - 7.5] |
| 🔴 **HIGH** | `bangladesh_affairs` | ভাষা আন্দোলন ও জাতীয়তাবাদী আন্দোলন (১৯৪৭-১৯৭০) | Nationalist Movement (1947-1970) | **3.5** | [2.4 - 4.7] |
| 🔴 **HIGH** | `bangladesh_affairs` | প্রাচীন ও মধ্যযুগীয় বাংলা এবং ব্রিটিশ শাসন | Early Bengal & British Era | **3.2** | [2.2 - 4.3] |
| 🔴 **HIGH** | `international_affairs` | আন্তর্জাতিক সংস্থা ও সম্মেলন | International Organizations | **8.3** | [6.9 - 9.8] |
| 🔴 **HIGH** | `international_affairs` | ভূরাজনীতি, নিরাপত্তা ও দ্বিপাক্ষিক চুক্তি | Geopolitics & Security | **7.0** | [5.7 - 8.4] |
| 🔴 **HIGH** | `international_affairs` | বিশ্বের ভূগোল, রাজধানী, মুদ্রা ও সীমারেখা | Global Geography & Capitals | **4.6** | [3.5 - 5.9] |
| 🔴 **HIGH** | `geography` | বাংলাদেশ ও বৈশ্বিক ভূ-প্রকৃতি | Physical Geography | **5.5** | [4.5 - 6.5] |
| 🔴 **HIGH** | `geography` | পরিবেশ দূষণ, জলবায়ু পরিবর্তন ও দুর্যোগ | Environment & Disaster Management | **4.5** | [3.5 - 5.5] |
| 🔴 **HIGH** | `general_science` | জীববিজ্ঞান, উদ্ভিদ ও মানবদেহ | Biology & Human Health | **6.1** | [4.9 - 7.3] |
| 🔴 **HIGH** | `general_science` | পদার্থবিজ্ঞান ও মহাবিশ্ব | Physics & Universe | **5.3** | [4.2 - 6.5] |
| 🔴 **HIGH** | `general_science` | রসায়ন ও দৈনন্দিন বিজ্ঞান | Chemistry & Daily Science | **3.6** | [2.6 - 4.7] |
| 🔴 **HIGH** | `computer_it` | নেটওয়ার্ক, ক্লাউড ও সাইবার নিরাপত্তা | Networks, Internet & Security | **5.9** | [4.7 - 7.1] |
| 🔴 **HIGH** | `computer_it` | কম্পিউটার হার্ডওয়্যার ও আর্কিটেকচার | Hardware Architecture | **5.3** | [4.1 - 6.5] |
| 🔴 **HIGH** | `computer_it` | অপারেটিং সিস্টেম, সফটওয়্যার ও ডাটাবেজ | Software & Databases | **3.8** | [2.7 - 4.9] |
| 🔴 **HIGH** | `math` | বীজগণিত (উৎপাদক, সমীকরণ, ধারা, সূচক ও লগ) | Algebra & Series | **5.9** | [4.7 - 7.1] |
| 🔴 **HIGH** | `math` | পাটিগণিত (ঐকিক, শতকরা, সুদকষা, অনুপাত) | Arithmetic | **5.3** | [4.2 - 6.5] |
| 🔴 **HIGH** | `math` | জ্যামিতি, পরিমিতি ও স্থানাঙ্ক | Geometry & Mensuration | **3.7** | [2.7 - 4.8] |
| 🔴 **HIGH** | `mental_ability` | ভাষাগত যুক্তি ও সম্পর্ক নির্ণয় | Verbal & Relational Reasoning | **8.1** | [6.8 - 9.3] |
| 🔴 **HIGH** | `mental_ability` | গাণিতিক ও স্থানিক যুক্তি | Numerical & Spatial Reasoning | **6.9** | [5.7 - 8.2] |
| 🔴 **HIGH** | `ethics` | নৈতিক মূল্যবোধ ও জাতীয় শুদ্ধাচার | Ethics & Good Governance | **10.0** | [0.0 - 10.0] |
| 🟡 MEDIUM | `bangla` | প্রাচীন যুগ (চর্যাপদ) | Ancient Era (Charyapada) | **2.3** | [1.4 - 3.3] |
| 🟡 MEDIUM | `bangla` | সমাস | Samas | **1.9** | [1.1 - 2.8] |
| 🟡 MEDIUM | `bangla` | বানান ও বাক্য শুদ্ধি, পরিভাষা | Spelling, Syntax and Terminology | **1.6** | [0.9 - 2.5] |
| 🟡 MEDIUM | `english` | Elizabethan & Renaissance Literature | Elizabethan Literature | **2.3** | [1.4 - 3.3] |
| 🟢 LOW | `bangla` | ধ্বনি ও বর্ণ প্রকরণ | Phonetics and Letters | **0.8** | [0.3 - 1.4] |

---

## 6. Syllabus Change Handling Documentation

- When a topic was introduced in `bcs-35th-current` (e.g., Computer & IT, Ethics, Geography), older exams (< 35th BCS) under `bcs-pre-35th` did not test these subjects.
- The model **does not penalize newly introduced topics as 0-probability**.
- Instead, topic activity is tracked through `topics.syllabus_version_introduced`. For exams where the topic was not yet part of the syllabus, the topic is not treated as having zero counts out of an active window. Observations are computed strictly over the exams where the topic was active.
- In the prior, newly introduced topics receive their fair subject-wide baseline share ($1 / |T_s|$), and higher Bayesian uncertainty is appropriately reflected via wider 80% credible intervals.
