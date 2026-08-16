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
    const { message } = req.body || {};
    if (!message) {
      return res.status(400).json({ error: 'Message payload required' });
    }

    let dashboardData = {};
    const jsonPath = path.join(process.cwd(), 'dashboard_data.json');
    if (fs.existsSync(jsonPath)) {
      dashboardData = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
    }

    const meta = dashboardData.meta || {};
    const tasks = dashboardData.tasks || [];
    const openHighRisk = tasks.filter(t => t.status === 'Open' && t.cat === 'HIGH');

    const apiKey = process.env.GEMINI_API_KEY;
    if (apiKey) {
      try {
        const { GoogleGenerativeAI } = require('@google/generative-ai');
        const genAI = new GoogleGenerativeAI(apiKey);
        const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });

        const systemPrompt = `You are the InterTech PRJ001 Project Delay Intelligence AI Assistant.
Project Context:
- Total Tasks: ${meta.total_tasks || tasks.length} (${meta.open_tasks || 260} Open, ${meta.delayed_tasks || 123} Delayed)
- Average Delay: +${meta.avg_delay_days || 3.5} days (Max: +${meta.max_delay_days || 12} days)
- Champion Model: ${meta.champion || 'Random Forest'} (${meta.cv_method || '5-Fold CV'})
- Open Tasks at High Risk: ${openHighRisk.length} tasks

Answer concisely with actionable recommendations.`;

        const result = await model.generateContent(`${systemPrompt}\n\nUser Question: ${message}`);
        const text = result.response.text();
        return res.status(200).json({ reply: text, source: 'gemini' });
      } catch (geminiError) {
        console.warn('Gemini API fallback to local rule engine:', geminiError);
      }
    }

    const lower = message.toLowerCase();
    let reply = "";

    if (lower.includes("high risk") || lower.includes("open task") || lower.includes("at risk")) {
      reply = `**High Risk Open Tasks Summary:**\nThere are **${openHighRisk.length} open tasks** currently classified in the **HIGH Risk Tier** (Probability ≥ 70%).\n\nTop Priority Actions:\n` +
        openHighRisk.slice(0, 3).map(t => `- **${t.id} (${t.desc})**: Discipline ${t.disc}, Score: ${t.score}%. *Action: Notify PM & Reallocate Subcontractors.*`).join("\n");
    } else if (lower.includes("model") || lower.includes("xgboost") || lower.includes("random forest") || lower.includes("algorithm") || lower.includes("compare")) {
      const champ = meta.champion || 'Random Forest';
      const cvData = meta.cv_accuracy || {};
      const sorted = Object.entries(cvData).sort((a, b) => (Number(b[1]?.f1 || 0) - Number(a[1]?.f1 || 0)));

      let graphHtml = `<div class="ai-inline-graph" style="margin-top:12px; padding:12px; background:#f8fafc; border:1px solid #cbd5e1; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div style="font-weight:700; font-size:11.5px; margin-bottom:10px; color:#0f172a; display:flex; justify-content:space-between; align-items:center;">
          <span>Model F1 Score Comparison</span>
          <span style="font-size:10px; color:#0284c7; font-weight:600;">5-Fold Stratified CV</span>
        </div>`;

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
      graphHtml += `</div>`;

      reply = `**ML Model Comparison (${meta.cv_method || '5-Fold Stratified CV'}):**\n\n` +
        sorted.map(([name, metrics]) => `- **${name}${name === champ ? ' (Champion)' : ''}**: F1 **${metrics.f1 ?? '-'}%**, AUC **${metrics.auc ?? '-'}%**, Accuracy **${metrics.mean ?? '-'}%**, Precision **${metrics.precision ?? '-'}%**, Recall **${metrics.recall ?? '-'}%**, MCC **${metrics.mcc ?? '-'}**`).join('\n') +
        `\n\n` + graphHtml + `\n\n*All available models are shown. Champion is selected by F1 score.*`;
    } else if (lower.includes("delay rate") || lower.includes("discipline") || lower.includes("site") || lower.includes("mep")) {
      reply = `**Discipline Delay Rate Breakdown:**\n` +
        Object.entries(dashboardData.disc_stats || {}).map(([disc, info]) => `- **${disc}**: ${info.rate}% historical delay rate (${info.delayed}/${info.total} completed tasks delayed)`).join("\n");
    } else {
      reply = `**Project PRJ001 Status Snapshot:**\n- **Total Tasks**: ${meta.total_tasks || 1000} (${meta.open_tasks || 260} Open, ${meta.delayed_tasks || 123} Delayed)\n- **Average Delay**: +${meta.avg_delay_days || 3.5} days\n- **Champion Model**: ${meta.champion || 'Random Forest'} (${meta.champion_metrics?.f1 || 69.5}% F1)\n\nTry asking me:\n- *"Which open tasks are at highest risk?"*\n- *"Compare algorithm metrics"*\n- *"What is the delay rate by discipline?"*`;
    }

    return res.status(200).json({ reply, source: 'local' });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
};
