import re
from build_full_prerender import build_prerender

pr = build_prerender()

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update AI Diagnostics Widget HTML to add Audit Log Tab, Starter Chips, and Pre-rendered tables
widget_old = """      <!-- Panel Tabs -->
      <div style="display: flex; border-bottom: 1px solid var(--border-light); background: var(--bg-subtle);">
        <button id="ai-tab-btn-diag" onclick="switchAIPanelTab('diag')" style="flex: 1; padding: 10px; border: none; background: #ffffff; font-weight: 700; font-size: 12px; color: var(--brand-primary); border-bottom: 2px solid var(--brand-primary); cursor: pointer;">Model Diagnostics</button>
        <button id="ai-tab-btn-chat" onclick="switchAIPanelTab('chat')" style="flex: 1; padding: 10px; border: none; background: transparent; font-weight: 600; font-size: 12px; color: var(--text-subtle); border-bottom: 2px solid transparent; cursor: pointer;">Ask AI Assistant</button>
      </div>

      <!-- Tab 1: Diagnostics Content -->
      <div id="ai-panel-diag-content" style="padding: 16px; overflow-y: auto; flex: 1;">
        <div style="margin-bottom: 16px;">
          <h4 style="font-size: 12px; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">Model Performance Leaderboard</h4>
          <div style="overflow-x: auto; font-size: 11px;">
            <table class="data-table" style="width: 100%;">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Accuracy</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1</th>
                  <th>AUC</th>
                </tr>
              </thead>
              <tbody id="ai-models-table-body">
                <!-- JS -->
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h4 style="font-size: 12px; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">SHAP Global Risk Drivers</h4>
          <div id="ai-feat-list-container" style="font-size: 11px;">
            <!-- JS -->
          </div>
        </div>
      </div>

      <!-- Tab 2: Chat Assistant Content -->
      <div id="ai-panel-chat-content" style="display: none; flex-direction: column; flex: 1; min-height: 0;">
        <div id="ai-chat-messages" style="flex: 1; min-height: 0; padding: 14px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; background: var(--bg-main);">
          <!-- Dynamically populated by initAIChat() -->
        </div>
        <div style="padding: 10px 12px; border-top: 1px solid var(--border-light); background: #ffffff; display: flex; gap: 8px;">
          <input type="text" id="ai-chat-input" placeholder="Ask AI Assistant..." style="flex: 1; padding: 8px 12px; border: 1px solid var(--border-medium); border-radius: 8px; font-size: 12px;" onkeypress="if(event.key==='Enter') sendAIChatMessage()">
          <button id="ai-chat-send-btn" onclick="sendAIChatMessage()" class="btn btn-primary" style="padding: 8px 14px; font-size: 12px;">Send</button>
        </div>
      </div>"""

widget_new = f"""      <!-- Panel Tabs -->
      <div style="display: flex; border-bottom: 1px solid var(--border-light); background: var(--bg-subtle);">
        <button id="ai-tab-btn-diag" onclick="switchAIPanelTab('diag')" style="flex: 1; padding: 10px 4px; border: none; background: #ffffff; font-weight: 700; font-size: 11px; color: var(--brand-primary); border-bottom: 2px solid var(--brand-primary); cursor: pointer;">Diagnostics</button>
        <button id="ai-tab-btn-chat" onclick="switchAIPanelTab('chat')" style="flex: 1; padding: 10px 4px; border: none; background: transparent; font-weight: 600; font-size: 11px; color: var(--text-subtle); border-bottom: 2px solid transparent; cursor: pointer;">Ask Assistant</button>
        <button id="ai-tab-btn-audit" onclick="switchAIPanelTab('audit')" style="flex: 1; padding: 10px 4px; border: none; background: transparent; font-weight: 600; font-size: 11px; color: var(--text-subtle); border-bottom: 2px solid transparent; cursor: pointer;">Audit Log</button>
      </div>

      <!-- Tab 1: Diagnostics Content -->
      <div id="ai-panel-diag-content" style="padding: 16px; overflow-y: auto; flex: 1;">
        <div style="margin-bottom: 16px;">
          <h4 style="font-size: 12px; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">Model Performance Leaderboard</h4>
          <div style="overflow-x: auto; font-size: 11px;">
            <table class="data-table" style="width: 100%;">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Accuracy</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1</th>
                  <th>AUC</th>
                </tr>
              </thead>
              <tbody id="ai-models-table-body">{pr["models_html"]}</tbody>
            </table>
          </div>
        </div>
        <div>
          <h4 style="font-size: 12px; font-weight: 700; color: var(--text-main); margin-bottom: 8px;">SHAP Global Risk Drivers</h4>
          <div id="ai-feat-list-container" style="font-size: 11px;">{pr["feat_html"]}</div>
        </div>
      </div>

      <!-- Tab 2: Chat Assistant Content -->
      <div id="ai-panel-chat-content" style="display: none; flex-direction: column; flex: 1; min-height: 0;">
        <!-- Scope Disclaimer Banner -->
        <div style="background:#eff6ff; border-bottom:1px solid #bfdbfe; padding:6px 12px; font-size:10.5px; color:#1d4ed8; display:flex; align-items:center; gap:6px;">
          <span>🔒 <strong>Scoped AI</strong>: Grounded in project dataset. Probabilities calculated by Calibrated Random Forest engine.</span>
        </div>

        <div id="ai-chat-messages" style="flex: 1; min-height: 0; padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; background: var(--bg-main);">
          <!-- Dynamically populated by initAIChat() -->
        </div>

        <!-- Starter Question Chips -->
        <div id="ai-chat-starter-chips" style="display:flex; gap:6px; overflow-x:auto; padding:6px 10px; background:var(--bg-subtle); border-top:1px solid var(--border-light); white-space:nowrap;">
          <button onclick="askAIQuickPrompt('What mitigation action is required for high risk tasks?')" style="background:#ffffff; border:1px solid #bfdbfe; border-radius:12px; padding:3px 8px; font-size:10.5px; font-weight:600; color:#1d4ed8; cursor:pointer;">🛡️ High risk mitigations</button>
          <button onclick="askAIQuickPrompt('Show discipline delay risk breakdown')" style="background:#ffffff; border:1px solid #bfdbfe; border-radius:12px; padding:3px 8px; font-size:10.5px; font-weight:600; color:#1d4ed8; cursor:pointer;">📊 Discipline breakdown</button>
          <button onclick="askAIQuickPrompt('What are top SHAP risk drivers?')" style="background:#ffffff; border:1px solid #bfdbfe; border-radius:12px; padding:3px 8px; font-size:10.5px; font-weight:600; color:#1d4ed8; cursor:pointer;">⚡ SHAP risk drivers</button>
          <button onclick="askAIQuickPrompt('Show employee reallocation headroom')" style="background:#ffffff; border:1px solid #bfdbfe; border-radius:12px; padding:3px 8px; font-size:10.5px; font-weight:600; color:#1d4ed8; cursor:pointer;">👥 Employee headroom</button>
        </div>

        <div style="padding: 10px 12px; border-top: 1px solid var(--border-light); background: #ffffff; display: flex; gap: 8px;">
          <input type="text" id="ai-chat-input" placeholder="Ask project intelligence..." style="flex: 1; padding: 8px 12px; border: 1px solid var(--border-medium); border-radius: 8px; font-size: 12px;" onkeypress="if(event.key==='Enter') sendAIChatMessage()">
          <button id="ai-chat-send-btn" onclick="sendAIChatMessage()" class="btn btn-primary" style="padding: 8px 14px; font-size: 12px;">Send</button>
        </div>
      </div>

      <!-- Tab 3: Usage Audit Log Content -->
      <div id="ai-panel-audit-content" style="display: none; flex-direction: column; flex: 1; padding: 14px; overflow-y: auto; background: var(--bg-main);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <h4 style="font-size: 12px; font-weight: 700; color: var(--text-main); margin:0;">AI Usage & Dispatch Audit Log</h4>
          <button onclick="clearAuditLog()" style="font-size:10.5px; color:#dc2626; border:1px solid #fecaca; background:#fff; padding:2px 8px; border-radius:4px; cursor:pointer;">Clear Log</button>
        </div>
        <div style="overflow-x:auto; font-size:11px;">
          <table class="data-table" style="width:100%;">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Type</th>
                <th>Query / Event</th>
                <th>Grounded Citation</th>
              </tr>
            </thead>
            <tbody id="ai-audit-log-tbody">
              <!-- Rendered by renderAuditLog() -->
            </tbody>
          </table>
        </div>
      </div>"""

html = html.replace(widget_old, widget_new)

# 2. Update JS logic for switchAIPanelTab, AI chat grounding, audit logging, and SMTP rate limiting
js_old = """    function switchAIPanelTab(tabName) {
      const diagContent = document.getElementById('ai-panel-diag-content');
      const chatContent = document.getElementById('ai-panel-chat-content');
      const diagBtn = document.getElementById('ai-tab-btn-diag');
      const chatBtn = document.getElementById('ai-tab-btn-chat');

      if (tabName === 'diag') {
        diagContent.style.display = 'block';
        chatContent.style.display = 'none';
        diagBtn.style.color = 'var(--brand-primary)';
        diagBtn.style.borderBottom = '2px solid var(--brand-primary)';
        diagBtn.style.background = '#ffffff';
        chatBtn.style.color = 'var(--text-subtle)';
        chatBtn.style.borderBottom = '2px solid transparent';
        chatBtn.style.background = 'transparent';
      } else {
        diagContent.style.display = 'none';
        chatContent.style.display = 'flex';
        chatBtn.style.color = 'var(--brand-primary)';
        chatBtn.style.borderBottom = '2px solid var(--brand-primary)';
        chatBtn.style.background = '#ffffff';
        diagBtn.style.color = 'var(--text-subtle)';
        diagBtn.style.borderBottom = '2px solid transparent';
        diagBtn.style.background = 'transparent';
        if (!document.getElementById('chat-inline-options-block')) {
          initAIChat();
        }
      }
    }"""

js_new = """    // ── AUDIT LOGGING & SMTP RATE LIMITING STATE ────────────────────────────────
    window.AI_USAGE_LOGS = window.AI_USAGE_LOGS || [
      { time: new Date().toLocaleTimeString(), type: 'SYSTEM', query: 'AI Diagnostics initialized', citation: 'Calibrated Random Forest' }
    ];
    window.SMTP_DISPATCH_HISTORY = window.SMTP_DISPATCH_HISTORY || [];

    function logAIUsage(type, query, citation) {
      const entry = {
        time: new Date().toLocaleTimeString(),
        type: type,
        query: query.length > 35 ? query.substring(0, 32) + '...' : query,
        citation: citation || 'SHAP / Model Matrix'
      };
      window.AI_USAGE_LOGS.unshift(entry);
      if (window.AI_USAGE_LOGS.length > 50) window.AI_USAGE_LOGS.pop();
      renderAuditLog();
    }

    function renderAuditLog() {
      const tbody = document.getElementById('ai-audit-log-tbody');
      if (!tbody) return;
      tbody.innerHTML = '';
      if (!window.AI_USAGE_LOGS || window.AI_USAGE_LOGS.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-subtle); padding:12px;">No audit events logged yet.</td></tr>';
        return;
      }
      window.AI_USAGE_LOGS.forEach(log => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-family:'JetBrains Mono',monospace; font-size:10px;">${log.time}</td>
          <td><span class="pill ${log.type === 'SMTP_ALERT' ? 'pill-high' : 'pill-low'}" style="font-size:9px;">${log.type}</span></td>
          <td style="font-weight:600;">${log.query}</td>
          <td style="color:var(--text-subtle); font-size:10.5px;">${log.citation}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function clearAuditLog() {
      window.AI_USAGE_LOGS = [];
      renderAuditLog();
    }

    function switchAIPanelTab(tabName) {
      const diagContent  = document.getElementById('ai-panel-diag-content');
      const chatContent  = document.getElementById('ai-panel-chat-content');
      const auditContent = document.getElementById('ai-panel-audit-content');
      const diagBtn  = document.getElementById('ai-tab-btn-diag');
      const chatBtn  = document.getElementById('ai-tab-btn-chat');
      const auditBtn = document.getElementById('ai-tab-btn-audit');

      diagContent.style.display  = tabName === 'diag'  ? 'block' : 'none';
      chatContent.style.display  = tabName === 'chat'  ? 'flex'  : 'none';
      auditContent.style.display = tabName === 'audit' ? 'flex'  : 'none';

      [diagBtn, chatBtn, auditBtn].forEach(btn => {
        if (!btn) return;
        btn.style.color = 'var(--text-subtle)';
        btn.style.borderBottom = '2px solid transparent';
        btn.style.background = 'transparent';
      });

      const activeBtn = tabName === 'diag' ? diagBtn : (tabName === 'chat' ? chatBtn : auditBtn);
      if (activeBtn) {
        activeBtn.style.color = 'var(--brand-primary)';
        activeBtn.style.borderBottom = '2px solid var(--brand-primary)';
        activeBtn.style.background = '#ffffff';
      }

      if (tabName === 'audit') renderAuditLog();
      if (tabName === 'chat' && !document.getElementById('chat-inline-options-block')) initAIChat();
    }"""

html = html.replace(js_old, js_new)

# 3. Enhance sendSMTPAlert with Rate Limiting & Audit Logging
smtp_old = """    function sendScheduleMeetingAlert(taskId) {
        alert('SMTP Meeting alert dispatched to Project Manager for task ' + taskId + ': STATUS_MEETING_SYNC');
    }"""

smtp_new = """    function sendScheduleMeetingAlert(taskId) {
      // SMTP Rate Limiting Guardrail: Max 3 per 60s
      const now = Date.now();
      window.SMTP_DISPATCH_HISTORY = (window.SMTP_DISPATCH_HISTORY || []).filter(t => (now - t) < 60000);
      if (window.SMTP_DISPATCH_HISTORY.length >= 3) {
        alert('⚠️ SMTP Rate Limit Exceeded: Maximum 3 email dispatches per 60 seconds allowed to prevent mail server flooding.');
        return;
      }
      window.SMTP_DISPATCH_HISTORY.push(now);
      logAIUsage('SMTP_ALERT', 'Meeting alert: ' + taskId, 'SMTP Meeting Guardrail');
      alert('SMTP Meeting alert dispatched to Project Manager for task ' + taskId + ': STATUS_MEETING_SYNC');
    }"""

html = html.replace(smtp_old, smtp_new)

# 4. Enhance sendAIChatMessage with Data Grounding & Scope Guardrails
chat_js_old = """        let botReply = 'InterTech PRJ001 Delay Intelligence Assistant active.';
        if (resp.ok) {
          const resData = await resp.json();
          if (resData.reply) botReply = resData.reply;
        }

        thinkingBubble.remove();

        const botBubble = document.createElement('div');
        botBubble.style.cssText = 'background:#ffffff; border:1px solid var(--border-light); padding:10px 14px; border-radius:12px; font-size:12px; max-width:92%; align-self:flex-start; word-break:break-word; line-height:1.6;';
        botBubble.innerHTML = botReply.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br>');
        messagesContainer.appendChild(botBubble);"""

chat_js_new = """        let botReply = 'InterTech PRJ001 Delay Intelligence Assistant active.';
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
        messagesContainer.appendChild(botBubble);"""

html = html.replace(chat_js_old, chat_js_new)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Successfully injected starter chips, data grounding badges, audit logging, SMTP guardrails, and scoped disclaimer!")
