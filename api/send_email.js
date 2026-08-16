// Serverless handler for Vercel API endpoint /api/send_email on intertechtaskprediction.vercel.app
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  }

  try {
    const payload = req.body || {};
    const tasks = payload.tasks || [];
    const recipient = payload.recipient || 'pm.intertech@gmail.com';

    let taskRowsHTML = '';
    tasks.forEach(t => {
      taskRowsHTML += `
        <tr>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0; font-weight:bold; color:#2563eb;">${t.id || t.task_id}</td>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0;">${t.desc || t.description}</td>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0;">${t.disc || t.discipline}</td>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0; font-weight:bold; color:#dc2626;">${t.score}%</td>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0; font-weight:bold; color:#d97706;">NOTIFY_PM + REALLOCATE_RESOURCE</td>
        </tr>
      `;
    });

    const htmlContent = `
    <html>
    <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <div style="max-width: 650px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
            <div style="background: #dc2626; color: #ffffff; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">CRITICAL PM ALERT: High-Risk Task Delay Predicted</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">InterTech Delay Intelligence Platform — Project PRJ001</p>
            </div>
            <div style="padding: 24px;">
                <p>Dear Project Manager,</p>
                <p>The ML Delay Prediction Engine has flagged <strong>${tasks.length} High-Risk Task(s)</strong> with high probability of completion delay.</p>
                
                <h3 style="color: #0f172a; margin-top: 20px;">High-Risk Task Breakdown</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                    <thead>
                        <tr style="background: #f8fafc; text-align: left;">
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Task ID</th>
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Description</th>
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Discipline</th>
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Risk Score</th>
                            <th style="padding: 10px; border-bottom: 2px solid #cbd5e1;">Action Proposal</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${taskRowsHTML}
                    </tbody>
                </table>
                
                <div style="background: #fef2f2; border: 1px solid #fecaca; padding: 15px; border-radius: 6px; margin-top: 20px;">
                    <strong style="color: #dc2626;">Action Required (per Problem Statement Mitigation Plan):</strong>
                    <ul style="margin: 5px 0 0 20px; color: #991b1b;">
                        <li>Reallocate senior personnel from closed or medium-risk projects immediately.</li>
                        <li>Schedule urgent site coordination sync with sub-contractor leads.</li>
                    </ul>
                </div>
            </div>
        </div>
    </body>
    </html>
    `;

    return res.status(200).json({
      success: true,
      sent_live: false,
      simulated: true,
      recipient: recipient,
      tasks_notified: tasks.length,
      html_preview: htmlContent,
      message: `[SMTP Alert Prepared] ${tasks.length} High-Risk task alert generated for PM (${recipient}).`
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}
