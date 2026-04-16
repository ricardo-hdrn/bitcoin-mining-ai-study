# Bitcoin Mining Operations — Exploratory Analysis

Deep-dive notebooks exploring bitcoin mining site operational data across five analytical dimensions. Built as a domain-learning exercise for industrial-scale mining operations: data quality, efficiency analysis, anomaly detection, curtailment optimization, and predictive maintenance.

📊 **[Browse the rendered notebooks on GitHub Pages →](https://ricardo-hdrn.github.io/bitcoin-mining-ai-study/)**

## Notebooks

| # | Notebook | Focus |
|---|---|---|
| 01 | Data Quality & Schema | Completeness, range validation, schema critique. Proposes an improved schema aligned with MiningOS (Tether's open-source mining platform) field conventions. |
| 02 | Efficiency & Waste | Per-miner efficiency vs nominal specs, dollar waste quantification, degradation trend detection via linear regression on daily metrics. |
| 03 | Anomaly Detection | Three-layer approach: statistical (z-score, IQR), contextual (deviation from fleet median), and Isolation Forest on engineered features. Container-wide event detection. |
| 04 | Curtailment Optimization | Merit-order dispatch with switching costs (hysteresis), binary optimization via dynamic programming, sensitivity analysis on BTC/electricity prices. |
| 05 | Predictive Maintenance | Daily miner profile feature engineering, unsupervised degradation scoring, supervised failure prediction (XGBoost with time-aware split), composite maintenance priority list. |

## Dataset

Synthetic 14-day telemetry for a 180-miner site with 3 containers, mixed miner models (Antminer S21, S19 XP, Whatsminer M56S, M63), and embedded patterns:
- 7 degrading miners (gradual efficiency loss)
- 3 intermittent failure patterns
- Container-wide cooling failure event
- ERCOT-style time-of-use electricity pricing
- Difficulty adjustment mid-period

## Setup

```bash
pip install pandas numpy matplotlib seaborn scikit-learn xgboost scipy scipy statsmodels jupyter
python generate_site_data.py   # generates site_telemetry.csv (~88 MB)
jupyter lab
```

## Context

This repository documents preparation work for applied industrial analytics in bitcoin mining — exploring how techniques from adjacent domains (rail/port operations, OPC UA telemetry, weather forecasting) map to ASIC fleet management. The analyses reference [Tether's MiningOS](https://github.com/tetherto) open-source architecture where relevant (field names, aggregation windows, curtailment logic).

Topics covered span data engineering, statistical process control, time-series analysis, and mathematical optimization — the toolkit of an AI/Optimization Engineer working on industrial telemetry.
