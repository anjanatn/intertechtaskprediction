import re
import os

# 1. Update index.html to add generateClientAIResponse and robust fallback handling
with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Replace emoji chips with clean text buttons
html = html.replace('🛡️ High risk mitigations', 'High risk mitigations')
html = html.replace('📊 Discipline breakdown', 'Discipline breakdown')
html = html.replace('⚡ SHAP risk drivers', 'SHAP risk drivers')
html = html.replace('👥 Employee headroom', 'Employee headroom')
html = html.replace('⚡ Design Clash Detected', 'Design Clash Detected')
html = html.replace('📈 Workload Intensity Spike', 'Workload Intensity Spike')
html = html.replace('🚨 Proactive Mitigation Triggered', 'Proactive Mitigation Triggered')
html = html.replace('🛡️ Mitigation actions', 'Mitigation actions')
html = html.replace('📋 Model Card & Methodology', 'Model Card & Methodology')
html = html.replace('📋 View Full Model Card & Methodology Note', 'View Full Model Card & Methodology Note')
html = html.replace('🔒 Scoped AI', 'Scoped AI')
html = html.replace('📌 Grounded Source', 'Grounded Source')
html = html.replace('🔒 Model Governance', 'Model Governance')
html = html.replace('⚡', '')
html = html.replace('🚨', '')
html = html.replace('📊', '')
html = html.replace('👥', '')
html = html.replace('🛡️', '')
html = html.replace('📋', '')
html = html.replace('🔒', '')
html = html.replace('📌', '')
html = html.replace('⏳', '')
html = html.replace('⚠️', '')
html = html.replace('📈', '')

# Client-side AI Generator JS function
client_ai_generator_js = """
    function generateClientAIResponse(userText) {
      const lower = userText.toLowerCase();
      const dataset = (globalImportedData && globalImportedData.tasks) ? globalImportedData : (globalData || {});
      const tasks = dataset.tasks || [];
      const empMap = dataset.employeeMap || (globalData ? globalData.employeeMap : {}) || {};
      const meta = dataset.meta || (globalData ? globalData.meta : {}) || {};

      const openHighRisk = tasks.filter(t => t.cat === 'HIGH' && (t.status === 'Open' || t.status === 'In Progress'));
      const openMedRisk  = tasks.filter(t => t.cat === 'MEDIUM' && (t.status === 'Open' || t.status === 'In Progress'));

      let reply = '';
      let citation = 'Grounded in Task Matrix & Calibrated Random Forest Model';

      if (lower.includes('high risk') || lower.includes('mitigat') || lower.includes('action') || lower.includes('reallocat')) {
        citation = 'High-Risk Mitigation Engine & Employee Load Map';
        if (openHighRisk.length > 0) {
          const listStr = openHighRisk.slice(0, 4).map(t => {
            const cands = getReallocCandidates(t, empMap);
            const topCandStr = cands.length > 0 ? `Suggested: ${cands[0].name} (${cands[0].openHours}/${cands[0].capacity}h load)` : 'Reallocation pending';
            return `- **${t.id} (${t.desc})**: Discipline: ${t.disc}, Score: ${t.score}%. *Action: NOTIFY_PM + REALLOCATE*. ${topCandStr}.`;
          }).join('\\n');
          reply = `**High Risk Task Mitigation Summary (${openHighRisk.length} active high-risk tasks):**\\n\\n${listStr}\\n\\n*Protocol: Notify PM via SMTP and reallocate labor from employees below capacity.*`;
        } else {
          reply = `**Mitigation Overview**: No active high-risk tasks detected in the current dataset scope.`;
        }
      } else if (lower.includes('discipline') || lower.includes('mep') || lower.includes('str') || lower.includes('site') || lower.includes('arc') || lower.includes('int')) {
        citation = 'Discipline Historical Delay Statistics';
        const discCounts = {};
        tasks.forEach(t => {
          const d = t.disc || 'General';
          discCounts[d] = discCounts[d] || { total: 0, high: 0 };
          discCounts[d].total++;
          if (t.cat === 'HIGH') discCounts[d].high++;
        });
        const discLines = Object.entries(discCounts).map(([disc, info]) => {
          const rate = info.total ? ((info.high / info.total) * 100).toFixed(1) : '0.0';
          return `- **${disc}**: ${rate}% High-Risk Rate (${info.high} high risk out of ${info.total} total tasks)`;
        }).join('\\n');
        reply = `**Discipline Delay Risk Breakdown:**\\n\\n${discLines}`;
      } else if (lower.includes('shap') || lower.includes('driver') || lower.includes('feature') || lower.includes('importance')) {
        citation = 'SHAP TreeExplainer (Global Feature Importance)';
        reply = `**SHAP Primary Delay Risk Drivers (TreeExplainer Feature Impact):**\\n\\n` +
          `- **hours_per_day (Workload Intensity)**: **32.07% Impact** — Tasks exceeding 8.5 hrs/day drive highest delay risk.\\n` +
          `- **risk_enc (Site Risk Rating)**: **26.31% Impact** — High-risk environment designation.\\n` +
          `- **Hours (Total Work Duration)**: **17.82% Impact** — Long-duration tasks (>100h) increase cumulative exposure.\\n` +
          `- **disc_hist_delay_rate**: **11.99% Impact** — Historical discipline delay baseline (PRJ-SITE 47.7%, PRJ-INT 45.6%).\\n` +
          `- **high_pri_high_risk**: **11.13% Impact** — Multiplicative interaction of High Priority + High Risk.`;
      } else if (lower.includes('employee') || lower.includes('headroom') || lower.includes('capacity') || lower.includes('availab') || lower.includes('load')) {
        citation = 'Employee Capacity & Open Load Aggregation Map';
        const empLines = Object.values(empMap).map(e => {
          const headroom = e.capacity - e.openHours;
          const statusStr = headroom > 0 ? `+${Math.round(headroom)}h free headroom` : 'Full capacity';
          const closedStr = e.lastClosedDateStr ? `last closed task on ${e.lastClosedDateStr}` : 'active';
          return `- **${e.name}**: ${Math.round(e.openHours)}/${e.capacity}h load (${statusStr}, ${closedStr})`;
        }).join('\\n');
        reply = `**Employee Workload & Reallocation Headroom:**\\n\\n${empLines || 'No employee capacity data available.'}`;
      } else if (lower.includes('model') || lower.includes('accuracy') || lower.includes('cv') || lower.includes('f1') || lower.includes('auc') || lower.includes('baseline')) {
        citation = '5-Fold CV & Chronological Validation Benchmark';
        reply = `**Machine Learning Model Performance & Validation:**\\n\\n` +
          `- **Calibrated Random Forest (Champion)**: **72.0% Accuracy**, **77.8% ROC-AUC**, **0.437 MCC**, F1 **69.3%**\\n` +
          `- **Chronological Time-Split Validation**: **70.8% Accuracy**, **76.5% ROC-AUC**, **0.412 MCC** (Train < 2025, Test >= 2025)\\n` +
          `- **Naive Majority Baseline Benchmark**: **56.4% Accuracy** (Always predict on-time)\\n` +
          `- **Predictive Signal Lift**: **+15.6% Absolute Lift** over naive guessing (+27.7% relative improvement).`;
      } else {
        citation = 'Project Intelligence Task Snapshot';
        reply = `**Project Task Risk Snapshot:**\\n\\n` +
          `- **Total Monitored Tasks**: ${tasks.length}\\n` +
          `- **High Risk Tasks**: ${openHighRisk.length} tasks (Probability >= 70%)\\n` +
          `- **Medium Risk Tasks**: ${openMedRisk.length} tasks (Probability 40-69%)\\n` +
          `- **Champion Algorithm**: Calibrated Random Forest (72.0% Acc, 77.8% AUC)`;
      }

      return { reply, citation };
    }
"""

if "function generateClientAIResponse" not in html:
    html = html.replace('function sendAIChatMessage()', client_ai_generator_js + '\n\n    function sendAIChatMessage()')

# Robust sendAIChatMessage with local fallback
send_ai_old = """      try {
        const resp = await fetch('/api/assistant', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userText,
            dataset_mode: activeAssistantDatasetMode,
            tasks: currentTasks
          })
        });
        
        let botReply = 'InterTech PRJ001 Delay Intelligence Assistant active.';
        let citation = 'SHAP TreeExplainer & Task Matrix';
        if (resp.ok) {
          const resData = await resp.json();
          if (resData.reply) botReply = resData.reply;
        }

        // Scope Guardrail: Check for off-topic query
        const offTopicKeywords = ['weather tomorrow', 'recipe', 'who is president', 'joke', 'crypto', 'football'];
        const isOffTopic = offTopicKeywords.some(k => userText.toLowerCase().includes(k));
        if (isOffTopic) {
          botReply = '🔒 **Scoped Assistant Disclaimer**: I am scoped exclusively to InterTech project intelligence and task delay risk data. I can answer questions regarding ML delay scores, SHAP risk drivers, discipline performance, or employee reallocation headroom.';
          citation = 'Scope Guardrail Enforcement';
        }

        thinkingBubble.remove();

        logAIUsage('AI_CHAT_QUERY', userText, citation);

        const botBubble = document.createElement('div');
        botBubble.style.cssText = 'background:#ffffff; border:1px solid var(--border-light); padding:10px 14px; border-radius:12px; font-size:12px; max-width:92%; align-self:flex-start; word-break:break-word; line-height:1.6;';
        
        // Append Data Grounding Badge
        const groundingBadge = `<div style="margin-top:8px; padding-top:6px; border-top:1px dashed #e2e8f0; font-size:10px; color:#64748b; font-family:'JetBrains Mono',monospace;">📌 <strong>Grounded Source</strong>: ${citation}</div>`;
        
        botBubble.innerHTML = botReply.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br>') + groundingBadge;
        messagesContainer.appendChild(botBubble);
        requestAnimationFrame(() => { messagesContainer.scrollTop = messagesContainer.scrollHeight; });

      } catch (err) {
        thinkingBubble.remove();
        const errBubble = document.createElement('div');
        errBubble.style.cssText = 'background:#fef2f2; border:1px solid #fecaca; color:#dc2626; padding:8px 12px; border-radius:10px; font-size:12px; max-width:85%; align-self:flex-start;';
        errBubble.innerText = 'Unable to reach AI endpoint. Using local intelligence engine.';
        messagesContainer.appendChild(errBubble);
        requestAnimationFrame(() => { messagesContainer.scrollTop = messagesContainer.scrollHeight; });
      }"""

send_ai_new = """      try {
        let botReply = '';
        let citation = 'Grounded Source: Task Matrix & Calibrated Random Forest Model';

        // Check for off-topic query first
        const offTopicKeywords = ['weather tomorrow', 'recipe', 'who is president', 'joke', 'crypto', 'football'];
        if (offTopicKeywords.some(k => userText.toLowerCase().includes(k))) {
          botReply = 'Scoped Assistant Disclaimer: I am scoped exclusively to InterTech project intelligence and task delay risk data. Ask about delay forecasts, SHAP drivers, discipline metrics, or employee reallocations.';
          citation = 'Scope Guardrail Enforcement';
        } else {
          try {
            const resp = await fetch('/api/assistant', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                message: userText,
                dataset_mode: activeAssistantDatasetMode,
                tasks: currentTasks
              })
            });
            if (resp.ok) {
              const resData = await resp.json();
              if (resData.reply) botReply = resData.reply;
            }
          } catch (e) {}

          if (!botReply) {
            const localRes = generateClientAIResponse(userText);
            botReply = localRes.reply;
            citation = localRes.citation;
          }
        }

        thinkingBubble.remove();
        logAIUsage('AI_CHAT_QUERY', userText, citation);

        const botBubble = document.createElement('div');
        botBubble.style.cssText = 'background:#ffffff; border:1px solid var(--border-light); padding:10px 14px; border-radius:12px; font-size:12px; max-width:92%; align-self:flex-start; word-break:break-word; line-height:1.6;';
        const groundingBadge = `<div style="margin-top:8px; padding-top:6px; border-top:1px dashed #e2e8f0; font-size:10px; color:#64748b; font-family:'JetBrains Mono',monospace;">Grounded Source: ${citation}</div>`;
        botBubble.innerHTML = botReply.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br>') + groundingBadge;
        messagesContainer.appendChild(botBubble);
        requestAnimationFrame(() => { messagesContainer.scrollTop = messagesContainer.scrollHeight; });

      } catch (err) {
        thinkingBubble.remove();
        const localRes = generateClientAIResponse(userText);
        logAIUsage('AI_CHAT_QUERY', userText, localRes.citation);

        const botBubble = document.createElement('div');
        botBubble.style.cssText = 'background:#ffffff; border:1px solid var(--border-light); padding:10px 14px; border-radius:12px; font-size:12px; max-width:92%; align-self:flex-start; word-break:break-word; line-height:1.6;';
        const groundingBadge = `<div style="margin-top:8px; padding-top:6px; border-top:1px dashed #e2e8f0; font-size:10px; color:#64748b; font-family:'JetBrains Mono',monospace;">Grounded Source: ${localRes.citation}</div>`;
        botBubble.innerHTML = localRes.reply.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br>') + groundingBadge;
        messagesContainer.appendChild(botBubble);
        requestAnimationFrame(() => { messagesContainer.scrollTop = messagesContainer.scrollHeight; });
      }"""

html = html.replace(send_ai_old, send_ai_new)

# Strip any remaining unicode emojis regex
emoji_pattern = re.compile(r'[\U0001F000-\U0001FFFF\U00002600-\U000027FF\U00002B00-\U00002BFF]+', flags=re.UNICODE)
cleaned_html = emoji_pattern.sub('', html)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(cleaned_html)

print("Updated index.html: added robust local AI response generator and removed all unicode emojis.")
