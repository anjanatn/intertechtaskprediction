# InterTech Project Delay Prediction

A demonstration decision-support application for predicting task-delay risk, explaining the contributing factors, and suggesting a mitigation action. The bundled project-management dataset is simulated and is intended for evaluation and development only.

## What it does

- Scores each task with a calibrated delay probability and Low / Medium / High risk tier.
- Explains individual predictions with SHAP feature contributions.
- Recommends a risk-based project-manager action.
- Lets users import CSV or Excel task data for browser-side predictions.
- Evaluates the model with stratified cross-validation and a chronological holdout: older tasks train the model and the newest tasks are used as a future-data test set.
- Compares the model with a naive `flag every task as high risk` baseline.

## Prerequisites

- Python 3.10 or newer
- pip

## Setup

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Dependencies are declared in [requirements.txt](requirements.txt); the application does not install packages during training.

## Run locally

```powershell
python server.py
```

Open [http://localhost:8080](http://localhost:8080). The local server provides the dashboard and API routes used by the interface.

## Retrain the model

The default training dataset is `simulated_project_delay_dataset_1000.csv`.

```powershell
python train_and_predict.py
```

Retraining:

1. Loads and validates the task dataset.
2. Builds only pre-execution features; post-outcome fields such as actual delay, root cause, and overdue state are excluded from model inputs.
3. Compares Logistic Regression, Random Forest, Gradient Boosting, XGBoost, and a stacking ensemble with 5-fold stratified cross-validation.
4. Selects the champion by F1 score and calibrates its probabilities.
5. Tests the champion on a chronological 80/20 holdout, where the latest dated records represent future tasks.
6. Records the model metrics and the naive `flag every task as high risk` baseline in `dashboard_data.json`.

The command updates `dashboard_data.json`, `public/dashboard_data.json`, and writes a snapshot under `model_registry/`.

## Data schema

The simulated sample uses fields including:

`TaskID`, `ProjectID`, `ProjectDiscipline`, `Status`, `Description`, `Location`, `Created`, `Target`, `Actual`, `Delay`, `Priority`, `Risk`, `Hours`, `AssignedTo`, and `TeamCapacityHours`.

The classification target is `Delay > 0` for closed tasks. For uploaded files, the interface accepts `.csv`, `.xlsx`, and `.xls` formats; download samples are included in `public/`.

## Risk policy

| Delay probability | Risk tier | Default action |
| --- | --- | --- |
| 0–39% | Low | Normal monitoring |
| 40–69% | Medium | Weekly status meeting |
| 70–100% | High | Notify PM and reallocate a resource |

## Limitations

### Data and Training
- **Synthetic Dataset**: The training dataset (`simulated_project_delay_dataset_1000.csv`) is entirely synthetic and generated for demonstration purposes. It does not reflect real-world project characteristics, task dependencies, or organizational practices.
- **Unvalidated Against Real Outcomes**: Model predictions have not been validated against actual project data in any operational environment. Performance metrics observed in cross-validation may not transfer to real-world projects.
- **Limited Historical Context**: The dataset contains only 1,000 records. Real project-delay prediction typically benefits from larger, multi-year historical archives that capture seasonal patterns, organizational changes, and industry-specific dynamics.
- **No Domain Expert Review**: Features and risk thresholds have not been reviewed or validated by project-management professionals or domain experts from target industries.

### Feature Engineering
- **Small Feature Set**: The model uses only 7–8 core features (priority, risk, hours, planned duration, workload intensity, discipline). Real-world delay drivers include resource availability, external dependencies, scope changes, stakeholder communication gaps, and supply-chain events—most of which are absent.
- **Post-Hoc Feature Removal**: While leakage from post-outcome fields (e.g., `RootCause`, `Overdue`) is prevented, the feature set remains minimal. Historical discipline delay rates are computed in-sample and may not generalize to new project types.
- **No Temporal Features**: The model does not capture seasonality, fiscal-quarter patterns, team fatigue, or macroeconomic indicators that often influence project performance.
- **Missing Interaction Terms**: Only one interaction term (`high_pri_high_risk`) is engineered. Complex multi-way interactions and nonlinear relationships may exist but are not modeled.

### Model Uncertainty
- **Confidence Intervals Not Included in UI**: While F1, accuracy, and AUC scores are reported, 95% confidence intervals are not displayed in the dashboard. Reported metrics should be interpreted with inherent sampling uncertainty.
- **Calibration Limited**: Probability calibration uses isotonic regression on cross-validated predictions, but calibration is only valid for the synthetic training distribution. Real-world task characteristics may violate calibration assumptions.
- **Class Imbalance**: The model is trained with balanced class weights, but if deployed to a population with different delay rates, predicted probabilities may be miscalibrated.

### Deployment and Operational Risks
- **No Real-World Testing**: The application has never been deployed in a live project-management environment. Unknown failure modes and user-interaction issues may emerge in production.
- **Baseline Comparison**: The "flag every task as high risk" baseline is deliberately naive and may not represent a realistic alternative. Comparison to simpler models (e.g., hand-crafted heuristics) is absent.
- **Not a Decision Substitute**: Predictions are intended to *support* project-manager judgment, not replace it. Over-reliance on model scores—especially for high-risk predictions—without manual review is inadvisable.
- **No Active Learning or Feedback Loop**: The model is static. Performance degradation over time, concept drift, or systematic errors in a live environment are not monitored or corrected.

### Fairness and Bias
- **Discipline-Based Bias Risk**: The model includes historical discipline delay rates. If certain disciplines or teams have been systematically underfunded or under-resourced in historical data, the model may perpetuate or amplify those inequities.
- **No Fairness Audit**: The model has not been evaluated for disparate impact across project types, teams, or organizational units.
- **Interpretability Gaps**: While SHAP explanations show feature contributions, they may obscure latent biases in feature engineering or training data.

### Scope and Roadmap
- **Advanced Analytics Not Validated**: The 3D visualizer and illustrative ROI scenarios are exploratory views and do not inform the prediction model.
- **No Forecasting Beyond Delay Probability**: The model predicts binary delay status only. Duration, cost, or resource-impact forecasts are not supported.
- **Limited Scalability**: Performance with datasets larger than ~100,000 records has not been tested.

## Deployment

Pushes to `master` deploy through the connected Vercel project at [intertechtaskprediction.vercel.app](https://intertechtaskprediction.vercel.app).
