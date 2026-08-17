import nodemailer from 'nodemailer';

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
    const recipient = payload.recipient || process.env.MANAGER_EMAIL || 'pm.intertech@gmail.com';
    const smtpConfig = payload.smtp_config || {};
    const isSiteInspectionMeeting = payload.alert_type === 'site_inspection_meeting';
    const isScheduleMeeting = isSiteInspectionMeeting || payload.alert_type === 'schedule_meeting';

    const host = smtpConfig.host || process.env.SMTP_HOST || 'smtp.gmail.com';
    const port = parseInt(smtpConfig.port || process.env.SMTP_PORT || '587');
    const user = smtpConfig.user || process.env.SMTP_USER || '';
    const pass = smtpConfig.pass || process.env.SMTP_PASS || '';
    const sender = smtpConfig.sender || process.env.SMTP_SENDER || user || 'alerts@intertech.com';

    let taskRowsHTML = '';
    tasks.forEach(t => {
      const facFlags = t._facilityFlags && t._facilityFlags.length ? `<div style="font-size:11px; color:#dc2626; margin-top:2px;"><strong>Needed Facilities:</strong> ${t._facilityFlags.join(', ')}</div>` : '';
      const facilityChecklist = t._facilityChecklist && t._facilityChecklist.length
        ? `<div style="font-size:11px; color:#475569; margin-top:4px;"><strong>Facility checklist:</strong> ${t._facilityChecklist.join('; ')}</div>`
        : '';
      const rootCause = t.root_cause
        ? `<div style="font-size:11px; color:#92400e; margin-top:2px;"><strong>Root cause:</strong> ${t.root_cause}</div>`
        : '';
      taskRowsHTML += `
        <tr>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0; font-weight:bold; color:#2563eb;">${t.id || t.task_id}</td>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0;">${t.desc || t.description}${rootCause}${facFlags}${facilityChecklist}</td>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0;">${t.disc || t.discipline}</td>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0; font-weight:bold; color:#dc2626;">${t.score}%</td>
          <td style="padding:10px; border-bottom:1px solid #e2e8f0; font-weight:bold; color:#d97706;">${t.action || 'NOTIFY_PM + REALLOCATE_RESOURCE'}</td>
        </tr>
      `;
    });

    const alertHeading = isSiteInspectionMeeting
      ? 'SITE INSPECTION REQUIRED: Schedule High-Risk Status Meeting'
      : isScheduleMeeting
      ? 'ACTION REQUIRED: Schedule Status Meeting'
      : 'CRITICAL PM ALERT: High-Risk Task Delay Predicted';
    const alertIntro = isSiteInspectionMeeting
      ? `A high-risk task has no confirmed root cause. Please schedule a status meeting and inspect the site before selecting a mitigation plan.`
      : isScheduleMeeting
      ? `Please schedule a status meeting to review the identified delay risk, agree corrective actions, and assign owners.${tasks.some(t => t._no_facility_shortage) ? ' The facility checklist found no shortage; the inspection classification and checklist are included below.' : ''}`
      : `The ML Delay Prediction Engine has flagged <strong>${tasks.length} High-Risk Task(s)</strong> with high probability of completion delay.`;
    const actionRequired = isSiteInspectionMeeting
      ? `<li>Schedule a status meeting with the project manager, discipline lead, and site supervisor.</li>
         <li>Inspect the site and record the root cause, constraints, and required corrective action.</li>
         <li>Confirm the mitigation owner and due date after the inspection.</li>`
      : isScheduleMeeting
      ? `<li>Schedule a status meeting with the project manager and delivery leads.</li>
         <li>Confirm the mitigation owner, due date, and follow-up update cadence.</li>`
      : `<li>Reallocate senior personnel from closed or medium-risk projects immediately.</li>
         <li>Schedule urgent site coordination sync with sub-contractor leads.</li>`;
    const subject = isSiteInspectionMeeting
      ? `ACTION REQUIRED: Schedule Site Inspection Meeting (${tasks.length} High-Risk Task${tasks.length === 1 ? '' : 's'})`
      : isScheduleMeeting
      ? `ACTION REQUIRED: Schedule Status Meeting (${tasks.length} Task${tasks.length === 1 ? '' : 's'})`
      : `URGENT: High-Risk Project Delay Alert (${tasks.length} Tasks Flagged)`;

    const htmlContent = `
    <html>
    <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <div style="max-width: 650px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
            <div style="background: #dc2626; color: #ffffff; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">${alertHeading}</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">InterTech Delay Intelligence Platform - Project PRJ001</p>
            </div>
            <div style="padding: 24px;">
                <p>Dear Project Manager,</p>
                <p>${alertIntro}</p>
                
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
                        ${actionRequired}
                    </ul>
                </div>
            </div>
        </div>
    </body>
    </html>
    `;

    if (user && pass) {
      const transporter = nodemailer.createTransport({
        host: host,
        port: port,
        secure: port === 465,
        auth: { user: user, pass: pass },
        connectionTimeout: 10000
      });

      await transporter.sendMail({
        from: sender,
        to: recipient,
        subject,
        html: htmlContent
      });

      return res.status(200).json({
        success: true,
        sent_live: true,
        recipient: recipient,
        tasks_notified: tasks.length,
        message: `SMTP email alert successfully sent to ${recipient}`
      });
    } else {
      return res.status(200).json({
        success: false,
        sent_live: false,
        simulated: true,
        requires_credentials: true,
        recipient: recipient,
        tasks_notified: tasks.length,
        html_preview: htmlContent,
        message: `SMTP Credentials Missing. Please provide SMTP Username & App Password to send live email to ${recipient}.`
      });
    }
  } catch (err) {
    return res.status(500).json({
      success: false,
      sent_live: false,
      error: err.message,
      message: `SMTP dispatch error (${err.message}). Please check SMTP host, port, user, and password/app password.`
    });
  }
}
