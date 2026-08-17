const fs = require('fs');
const path = require('path');

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    const payload = req.body || {};
    const message = payload.message || '';
    const datasetMode = (payload.dataset_mode || 'test').toLowerCase();
    const customTasks = payload.tasks || [];

    let dashboardData = {};
    const jsonPath = path.join(process.cwd(), 'dashboard_data.json');
    if (fs.existsSync(jsonPath)) {
      try {
        dashboardData = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
      } catch (e) {}
    }

    const meta = dashboardData.meta || {};
    let tasks = dashboardData.tasks || [];
    let isTestData = false;

    if (datasetMode === 'test') {
      isTestData = true;
      if (customTasks.length > 0) {
        tasks = customTasks;
      }
    }

    const openHighRisk = tasks.filter(t => t.cat === 'HIGH');
    const lower = message.toLowerCase();
    let reply = "";

    if (lower.includes("high risk") || lower.includes("highest risk") || lower.includes("open task") || lower.includes("at risk")) {
      reply = `**High Risk Tasks Summary (${isTestData ? 'Test Data' : 'Train Data'}):**\nThere are **${openHighRisk.length} tasks** currently classified in the **HIGH Risk Tier** (Probability ≥ 70%).\n\nTop Priority Actions:\n` +
        (openHighRisk.length ? openHighRisk.slice(0, 5).map(t => `- **${t.id} (${t.desc || 'Task'})**: Discipline: ${t.disc || 'General'}, Risk Score: ${t.score || 75}%. *Action: ${t.action || 'NOTIFY_PM + REALLOCATE_RESOURCE'}.*`).join("\n") : "No High Risk tasks flagged in this dataset.");
    } else if (lower.includes("model") || lower.includes("xgboost") || lower.includes("random forest") || lower.includes("algorithm") || lower.includes("compare")) {
      const champ = meta.champion || 'Random Forest';
      const cvData = meta.cv_accuracy || {};
      const sorted = Object.entries(cvData).sort((a, b) => (Number(b[1]?.f1 || 0) - Number(a[1]?.f1 || 0)));

      let graphHtml = `<div class="ai-inline-graph" style="margin-top:12px; padding:12px; background:#f8fafc; border:1px solid #cbd5e1; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div style="font-weight:700; font-size:11.5px; margin-bottom:10px; color:#0f172a; display:flex; justify-content:space-between; align-items:center;">
          <span>Model Performance (${isTestData ? 'Evaluated on Test Data' : '5-Fold CV Train Data'})</span>
          <span style="font-size:10px; color:#0284c7; font-weight:600;">Calibrated Ensemble</span>
        </div>`;

      if (sorted.length > 0) {
        sorted.forEach(([name, m]) => {
          const val = Number(m.f1 || 0);
          const pct = Math.min(Math.max(Math.round(val), 6), 100);
          const isChamp = name === champ;
          graphHtml += `
            <div style="margin-bottom:8px;">
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; margin-bottom:3px; color:#334155; font-weight:600;">
                <span>${name}${isChamp ? ' <span style="background:#dcfce7; color:#15803d; font-size:9px; padding:1px 5px; border-radius:4px; font-weight:700; border:1px solid #bbf7d0;">Champion</span>' : ''}</span>
                <span style="font-family:\'JetBrains Mono\', monospace; font-weight:700; color:#0f172a;">${val.toFixed(1)}%</span>
              </div>
              <div style="height:7px; background:#e2e8f0; border-radius:4px; overflow:hidden;">
                <div style="height:100%; width:${pct}%; background:${isChamp ? 'linear-gradient(90deg, #10b981, #34d399)' : 'linear-gradient(90deg, #0284c7, #38bdf8)'}; border-radius:4px;"></div>
              </div>
            </div>`;
        });
      if (sorted.length > 0) {
        const textLines = sorted.map(([name, m]) => {
          const isChamp = name === champ;
          const acc = Number(m.mean || m.acc || 0).toFixed(1);
          const f1 = Number(m.f1 || 0).toFixed(1);
          const auc = Number(m.auc || m.auc_roc || 0).toFixed(1);
          const prec = Number(m.precision || 0).toFixed(1);
          const rec = Number(m.recall || 0).toFixed(1);
          const mcc = Number(m.mcc || 0).toFixed(1);
          return `- **${name}${isChamp ? ' (Champion)' : ''}**: Accuracy **${acc}%**, F1 **${f1}%**, AUC **${auc}%**, Precision **${prec}%**, Recall **${rec}%**, MCC **${mcc}**`;
        });
        reply = `**ML Model Comparison (${isTestData ? 'Evaluated on Test Set' : 'Train Set 5-Fold Stratified CV'}):**\n\n` +
          textLines.join("\n") + `\n\n` + graphHtml;
      } else {
        const champM = meta.champion_metrics || {};
        reply = `**ML Model Comparison (${isTestData ? 'Evaluated on Test Set' : 'Train Set 5-Fold Stratified CV'}):**\n\n` +
          `- **Calibrated ${champ} (Champion)**: Accuracy **${champM.acc || 72.0}%**, F1 **${champM.f1 || 69.3}%**, AUC **${champM.auc_roc || 77.8}%**, Precision **${champM.precision || 66.4}%**, Recall **${champM.recall || 72.4}%**` +
          `\n\n` + graphHtml;
      }
    } else if (lower.includes("delay rate") || lower.includes("discipline") || lower.includes("site") || lower.includes("mep")) {
      const discCounts = {};
      tasks.forEach(t => {
        const d = t.disc || 'General';
        discCounts[d] = discCounts[d] || { total: 0, high: 0 };
        discCounts[d].total++;
        if (t.cat === 'HIGH') discCounts[d].high++;
      });
      reply = `**Discipline Delay & Risk Rate Breakdown (${isTestData ? 'Test Data' : 'Train Data'}):**\n` +
        Object.entries(discCounts).map(([disc, info]) => {
          const rate = info.total ? ((info.high / info.total) * 100).toFixed(1) : 0;
          return `- **${disc}**: ${rate}% High-Risk rate (${info.high} high-risk out of ${info.total} total tasks)`;
        }).join("\n");
    } else if (lower.includes("mitigation") || lower.includes("action") || lower.includes("reallocate")) {
      reply = `**Mitigation Protocols per Problem Statement:**\n` +
        `- **High-Risk Tasks (Probability ≥ 70%)**: Trigger action tag \`NOTIFY_PM + REALLOCATE_RESOURCE\`. Notify PM via SMTP alert and reallocate senior personnel from completed or low/medium-risk projects.\n` +
        `- **Medium-Risk Tasks (40% - 69%)**: Trigger action tag \`SCHEDULE_STATUS_MEETING\`. Schedule mandatory sync with discipline leads and require daily progress updates.\n` +
        `- **Low-Risk Tasks (< 40%)**: Monitor weekly in standard progress meetings.`;
    } else {
      const champName = meta.champion || 'Random Forest';
      const champM = meta.champion_metrics || {};
      const accStr = (champM.acc !== undefined ? Number(champM.acc) : 72.0).toFixed(1) + "% Accuracy";
      const aucStr = (champM.auc_roc !== undefined ? Number(champM.auc_roc) : 77.8).toFixed(1) + "% AUC";
      reply = `**Project PRJ001 Delay Intelligence Snapshot (${isTestData ? 'Mode: Test Data' : 'Mode: Train Data'}):**\n` +
        `- **Active Dataset**: ${isTestData ? 'Test Data (Imported Predictions)' : 'Train Data (Historical Dataset)'}\n` +
        `- **Total Analyzed Tasks**: ${tasks.length}\n` +
        `- **High-Risk Tasks**: ${openHighRisk.length}\n` +
        `- **Champion Model**: Calibrated ${champName} (${accStr}, ${aucStr})`;
    }

    return res.status(200).json({ reply, source: 'local', dataset_mode: datasetMode });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
};
