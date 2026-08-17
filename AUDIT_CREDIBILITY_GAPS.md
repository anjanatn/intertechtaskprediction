# InterTech Credibility Audit — Critical Gaps

**Status:** 🚨 **FAILING** — Project makes unvalidated claims; self-grades as "COMPLIANT"; dashboard UI over-promises.

---

## 1. Self-Grading Credibility Red Flag

### ❌ **Problem**: The Project Grades Itself as "COMPLIANT"

**File:** `update_diagnostics_and_model_card.py` (lines 110–113)
```
"COMPLIANT Definition: Indicates complete compliance with InterTech problem statement specifications: 
binary delay target modeling (Delay > 0), automated PM alert triggers, and dynamic employee reallocation."
```

**Why this is a red flag:**
- A project grading **itself** as compliant is a governance anti-pattern.
- No external validation, no third-party audit, no documented acceptance criteria.
- Undermines trust in all claims (model performance, validation methodology, baseline comparison).

### ✅ **Fix:**
- **Remove** the self-grading "COMPLIANT" language entirely.
- Replace with: *"This project meets the following documented specifications: [list]. External validation and real-world testing are required before operational deployment."*
- Add a `VALIDATION_STATUS.md` file with:
  - ✅ Completed validation steps
  - ⏳ In-progress validation
  - ❌ Not yet validated (e.g., "Real-world project outcome matching")

---

## 2. Dashboard Promises vs. Model Reality Disconnect

### ❌ **Problem**: UI Advertises Features Never Implemented or Connected to Model

| Dashboard Claims | Model Output | Connection? | Evidence |
|---|---|---|---|
| **3D Digital Twin Visualizer** | None (model outputs binary predictions) | ❌ No | `index.html` line 906–1023: 3D canvas exists but receives no data |
| **$430K+ ROI Savings Estimate** | No ROI calculations exist | ❌ No | `index.html` line 1342: `$430,500` is hardcoded placeholder; no model input |
| **"Code Compliance" Score (96%)** | Not calculated by model | ❌ No | `index.html` line 957: `id="ct-code-compliance"` has no backend API endpoint |
| **"Rotate 3D Site View"** | N/A (no 3D model) | ❌ No | `index.html` line 916: Button calls `rotate3DSiteTwin()` but canvas is empty |
| **Delay Predictions** | ✅ Binary (0/1) + calibrated probabilities | ✅ Yes | Model outputs; API implemented |

### ✅ **Fix:**
**Option A: Remove Placeholder Features**
1. Delete 3D visualization canvas code (lines 1004–1050 in index.html).
2. Replace ROI calculator with a note: *"Savings estimates are illustrative scenario planning, not model outputs. Actual ROI depends on intervention effectiveness."*
3. Rename "Code Compliance" to "Configurability Status" or remove it entirely.

**Option B: Implement Features Properly** (High effort)
1. Add 3D data model to `dashboard_data.json` (site layout, task locations, dependency graph).
2. Implement ROI backend: calculate avoided delay costs based on historical delay durations + task costs.
3. Add compliance scoring: measure delivered tasks vs. on-time tasks per discipline.

---

## 3. Model Validation Gaps — "Proven Delays Prediction" Unsubstantiated

### ❌ **Problem A**: No Real-World Outcome Validation

**What we have:**
- 5-Fold Stratified CV on synthetic 1,000-record dataset (70–72% accuracy).
- Chronological 80/20 holdout on same synthetic data.

**What we don't have:**
- ✅ Out-of-sample validation on **real project data**.
- ✅ Prospective validation: model trained on Q1 2024, tested on Q2 2024 real outcomes.
- ✅ Documented baseline comparison on real data (naive classifier only validated on synthetic data).

**Why it matters:**
- Model could be **memorizing synthetic patterns** that don't generalize.
- "Delays prediction" is **assumed**, not proven.
- Accuracy on synthetic data ≠ accuracy on real projects.

### ❌ **Problem B**: Baseline Comparison Not Prominent Enough

**Current state (in `update_diagnostics_and_model_card.py`):**
```
Naive baseline: 56.4% accuracy (always predict "on-time")
ML model:       72.0% accuracy
Lift:           +15.6 percentage points
```

**Problems:**
1. Baseline trained on **synthetic data only**.
2. No statistical significance test (confidence intervals).
3. MCC = 0.437 is moderate, not strong (0.5–1.0 is "moderate to strong").
4. No cost-weighted comparison (some false positives may cost more than false negatives).

### ✅ **Fix:**

**Phase 1 (Immediate):**
1. Add to README: *"⚠️ Model validated on synthetic data only. Real-world performance is unproven."*
2. Document naive baseline in `dashboard_data.json` clearly with statistical confidence intervals.
3. Add Matthews Correlation Coefficient (MCC) and interpretation to all reports.

**Phase 2 (Medium-term):**
1. Collect real project outcome data for Q1 2025.
2. Retrain model, split by date: train on Q4 2024, test on Q1 2025 **real outcomes**.
3. Compare ML model vs. baseline on real data.
4. Document results in `VALIDATION_REPORT.md`.

**Phase 3 (Long-term):**
1. Implement **prospective validation**: freeze model, predict on new projects, compare to actual outcomes monthly.
2. Report monthly: "This month: 68% accuracy on real data (vs. 72% on synthetic CV)."

---

## 4. Chronological Validation Claims — Partial Implementation

### ❌ **Problem**: Claims are made, but not all are shown in outputs

**File:** `train_and_predict.py` (lines 330–372)
- Code implements chronological 80/20 split ✅
- Metrics computed (accuracy, F1, AUC) ✅
- **But**: No confidence intervals printed or exported ❌
- **And**: Temporal validation results not persisted to `dashboard_data.json` ❌

### ✅ **Fix**:
1. Ensure chronological holdout metrics are **printed prominently** during training.
2. Export `temporal_validation` object to `dashboard_data.json`.
3. Display in Model Card modal with 95% confidence intervals.

---

## 5. Feature Engineering — Small Scope Not Flagged

### ❌ **Problem**: Only 7–8 pre-execution features; real-world delays have 50+ drivers.

**Feature set:**
- `priority_enc`, `risk_enc`, `high_pri_high_risk`, `Hours`, `planned_duration`, `hours_per_day`, `disc_hist_delay_rate` + discipline dummies.

**Not captured:**
- Resource availability, external dependencies, vendor schedules.
- Scope creep, change orders, permit delays.
- Supply chain events, weather, economic indicators.
- Communication gaps, stakeholder disputes, team experience.

### ✅ **Fix**: (Already done in Limitations section, but reinforce)
1. Add bold warning in README: *"⚠️ **Feature Set Limited**: Only task-level features (priority, hours, discipline). Resource, external, and organizational factors not modeled."*
2. Document in Model Card that this model is **"task-level risk indicator"**, not "project-level outcome predictor."

---

## 6. No Confidence Intervals in Metrics Display

### ❌ **Problem**: Point estimates only; no uncertainty quantified.

**Current:**
- "Accuracy: 72.0%"

**Should be:**
- "Accuracy: 72.0% [68.5%–75.2%]" (95% CI)

### ✅ **Fix**: (Partially addressed in test suite; needs deployment)
1. Implement Wilson CI for accuracy, Bootstrap CI for F1 in `train_and_predict.py`.
2. Export confidence intervals to `dashboard_data.json`.
3. Display in Model Card and diagnostics view with interpretation: *"We are 95% confident the true accuracy is between 68.5% and 75.2%."*

---

## Summary: What's Broken & Priority Fixes

| Issue | Severity | Effort | Priority |
|---|---|---|---|
| **Self-grading "COMPLIANT"** | 🔴 Critical | 1 hour | **P0** |
| **Dashboard 3D/ROI/Compliance disconnect** | 🔴 Critical | 2–4 hours | **P0** |
| **No real-world outcome validation** | 🔴 Critical | Ongoing | **P1** (blocks deployment) |
| **Baseline comparison not prominent** | 🟡 High | 1 hour | **P1** |
| **Chronological holdout not exported** | 🟡 High | 1 hour | **P1** |
| **Confidence intervals missing** | 🟡 High | 2 hours | **P2** |
| **Feature set scope not highlighted** | 🟠 Medium | 0.5 hours | **P2** |

---

## Recommended Action Plan

### **Week 1: Remove Red Flags (P0)**
- [ ] Delete or retitle self-grading "COMPLIANT" language.
- [ ] Remove unimplemented 3D/ROI/Compliance UI elements OR label as "placeholder/demo."
- [ ] Add prominent disclaimer: "Synthetic data only; real-world validation required."

### **Week 2–4: Strengthen Validation (P1)**
- [ ] Export temporal validation results to dashboard.
- [ ] Implement confidence intervals in training output.
- [ ] Create `VALIDATION_STATUS.md` documenting what's been validated vs. not.
- [ ] Add baseline comparison prominently to Model Card.

### **Ongoing: Real-World Validation (P1+)**
- [ ] Partner with InterTech to collect real Q1 2025 project data.
- [ ] Retrain + validate on real outcomes.
- [ ] Monthly prospective validation reporting.

---

**Document Date:** 2026-08-17  
**Status:** Ready for action  
**Next Review:** After P0 fixes deployed
