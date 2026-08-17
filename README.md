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

## Important limitations

- The baseline dataset is synthetic and has not been validated against real project outcomes.
- Predictions support project-manager judgment; they are not operational decisions by themselves.
- The Advanced Analytics / 3D visualizer and illustrative ROI scenario are roadmap or exploratory views, not inputs to the prediction model.

## Deployment

Pushes to `master` deploy through the connected Vercel project at [intertechtaskprediction.vercel.app](https://intertechtaskprediction.vercel.app).
