import nodemailer from 'nodemailer';
import { createHighRiskResponseTicket } from './integrations/jira_connector.js';

const escapeHtml = value => String(value ?? '')
 .replace(/&/g, '&amp;')
 .replace(/</g, '&lt;')
 .replace(/>/g, '&gt;')
 .replace(/"/g, '&quot;')
 .replace(/'/g, '&#039;');

const taskValue = (task, ...keys) => {
 for (const key of keys) {
  if (task?.[key] !== undefined && task[key] !== null && task[key] !== '') return task[key];
 }
 return '';
};

const taskId = task => taskValue(task, 'id', 'task_id', 'TaskID') || 'HIGH-RISK-TASK';
const taskScore = task => Math.round(Number(taskValue(task, 'score', 'delay_score') || 0));
const icsUtc = date => date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
const uniqueEmails = emails => [...new Set(emails.filter(email => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email || '')))];
const icsEscape = value => String(value ?? '').replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');

function makeCalendarInvite({ uid, summary, description, start, end, attendees, sender, recurrence }) {
 const attendeeLines = attendees.map(email => `ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:${email}`).join('\r\n');
 return [
  'BEGIN:VCALENDAR',
  'VERSION:2.0',
  'PRODID:-//InterTech//High Risk Response//EN',
  'CALSCALE:GREGORIAN',
  'METHOD:REQUEST',
  'BEGIN:VEVENT',
  `UID:${uid}`,
  `DTSTAMP:${icsUtc(new Date())}`,
  `DTSTART:${icsUtc(start)}`,
  `DTEND:${icsUtc(end)}`,
  `SUMMARY:${icsEscape(summary)}`,
  `DESCRIPTION:${icsEscape(description)}`,
  `ORGANIZER:mailto:${sender}`,
  attendeeLines,
  recurrence || '',
  'BEGIN:VALARM',
  'TRIGGER:-PT15M',
  'ACTION:DISPLAY',
  `DESCRIPTION:${icsEscape(summary)}`,
  'END:VALARM',
  'END:VEVENT',
  'END:VCALENDAR'
 ].filter(Boolean).join('\r\n');
}

function dateAtHourInTimeZone(timeZone, hour) {
 const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
 const formatParts = date => Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
  timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23', minute: '2-digit'
 }).formatToParts(date).filter(part => part.type !== 'literal').map(part => [part.type, part.value]));
 const localDate = formatParts(tomorrow);
 const targetAsUtc = Date.UTC(Number(localDate.year), Number(localDate.month) - 1, Number(localDate.day), hour, 0, 0);
 const provisional = new Date(targetAsUtc);
 const provisionalLocal = formatParts(provisional);
 const provisionalAsUtc = Date.UTC(Number(provisionalLocal.year), Number(provisionalLocal.month) - 1, Number(provisionalLocal.day), Number(provisionalLocal.hour), Number(provisionalLocal.minute), 0);
 return new Date(provisional.getTime() + targetAsUtc - provisionalAsUtc);
}

function highRiskCalendarAttachments(task, attendees, sender, timeZone) {
 const now = new Date();
 const reviewStart = new Date(now.getTime() + 60 * 60 * 1000);
 const reviewEnd = new Date(reviewStart.getTime() + 15 * 60 * 1000);
 const standupStart = dateAtHourInTimeZone(timeZone, 9);
 const standupEnd = new Date(standupStart.getTime() + 15 * 60 * 1000);
 const id = taskId(task);
 const score = taskScore(task);
 const agenda = [
  `Resource Review Call for ${id} (${score}% HIGH RISK).`,
  'Agenda:',
  '1. Identify who to reallocate from closed or medium-risk tasks.',
  '2. Set daily stand-up ownership and cadence.',
  '3. Agree the escalation path if resources are unavailable.'
 ].join('\n');

 return [
  {
   filename: `${id}-resource-review.ics`,
   contentType: 'text/calendar; charset=UTF-8; method=REQUEST',
   content: makeCalendarInvite({
    uid: `${id}-resource-review-${reviewStart.getTime()}@intertech`,
    summary: `Resource Review Call — ${id} HIGH RISK`,
    description: agenda,
    start: reviewStart,
    end: reviewEnd,
    attendees,
    sender
   })
  },
  {
   filename: `${id}-daily-standup.ics`,
   contentType: 'text/calendar; charset=UTF-8; method=REQUEST',
   content: makeCalendarInvite({
    uid: `${id}-daily-standup-${standupStart.getTime()}@intertech`,
    summary: `Daily Stand-up — ${id} Resource Recovery`,
    description: `Daily 9:00 AM ${timeZone} stand-up for ${id} for the next two weeks. Review risks, staffing, hours versus plan, and completion progress.`,
    start: standupStart,
    end: standupEnd,
    attendees,
    sender,
    recurrence: 'RRULE:FREQ=DAILY;COUNT=14'
   })
  }
 ];
}

function taskRows(tasks) {
 return tasks.map(task => {
  const facilityFlags = Array.isArray(task._facilityFlags) && task._facilityFlags.length
   ? `<div style="font-size:11px;color:#b91c1c;margin-top:3px"><strong>Protocol exceptions:</strong> ${escapeHtml(task._facilityFlags.join(', '))}</div>`
   : '';
  const checklist = Array.isArray(task._facilityChecklist) && task._facilityChecklist.length
   ? `<div style="font-size:11px;color:#475569;margin-top:4px"><strong>Inspection protocol:</strong> ${escapeHtml(task._facilityChecklist.join('; '))}</div>`
   : '';
  const rootCause = task.root_cause
   ? `<div style="font-size:11px;color:#92400e;margin-top:3px"><strong>Root cause:</strong> ${escapeHtml(task.root_cause)}</div>`
   : '';
  return `<tr>
   <td style="padding:10px;border-bottom:1px solid #e2e8f0;font-weight:700;color:#2563eb">${escapeHtml(taskId(task))}</td>
   <td style="padding:10px;border-bottom:1px solid #e2e8f0">${escapeHtml(taskValue(task, 'desc', 'description', 'Description'))}${rootCause}${facilityFlags}${checklist}</td>
   <td style="padding:10px;border-bottom:1px solid #e2e8f0">${escapeHtml(taskValue(task, 'disc', 'discipline', 'ProjectDiscipline') || 'General')}</td>
   <td style="padding:10px;border-bottom:1px solid #e2e8f0;font-weight:800;color:#dc2626">${taskScore(task)}%</td>
   <td style="padding:10px;border-bottom:1px solid #e2e8f0;font-weight:700;color:#b45309">${escapeHtml(task.action || 'NOTIFY_PM + REALLOCATE_RESOURCE')}</td>
  </tr>`;
 }).join('');
}

const taskTable = tasks => `<h3 style="color:#0f172a;margin-top:20px">High-Risk Task Breakdown</h3><table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="background:#f8fafc;text-align:left"><th style="padding:10px;border-bottom:2px solid #cbd5e1">Task ID</th><th style="padding:10px;border-bottom:2px solid #cbd5e1">Description</th><th style="padding:10px;border-bottom:2px solid #cbd5e1">Discipline</th><th style="padding:10px;border-bottom:2px solid #cbd5e1">Risk score</th><th style="padding:10px;border-bottom:2px solid #cbd5e1">Action</th></tr></thead><tbody>${taskRows(tasks)}</tbody></table>`;

function standardEmail(tasks, alertType) {
 const isSiteInspection = alertType === 'site_inspection_meeting';
 const isMeeting = isSiteInspection || alertType === 'schedule_meeting';
 const heading = isSiteInspection
  ? 'SITE INSPECTION REQUIRED: Schedule High-Risk Status Meeting'
  : isMeeting ? 'ACTION REQUIRED: Schedule Status Meeting' : 'CRITICAL PM ALERT: High-Risk Task Delay Predicted';
 const intro = isSiteInspection
  ? 'A high-risk task has no confirmed root cause. Schedule a status meeting and inspect the site before choosing a mitigation plan.'
  : isMeeting ? 'Schedule a status meeting to review the identified delay risk, assign owners, and agree the update cadence.'
  : `The ML Delay Prediction Engine has flagged <strong>${tasks.length} High-Risk Task(s)</strong> with a high probability of completion delay.`;
 const actions = isMeeting
  ? '<li>Schedule the status meeting with the project manager and delivery leads.</li><li>Confirm the mitigation owner, due date, and follow-up cadence.</li>'
  : '<li>Reallocate senior personnel from closed or medium-risk tasks immediately.</li><li>Schedule the urgent site coordination sync with delivery leads.</li>';
 return {
  subject: isMeeting ? `ACTION REQUIRED: Schedule Status Meeting (${tasks.length} Task${tasks.length === 1 ? '' : 's'})` : `URGENT: High-Risk Project Delay Alert (${tasks.length} Tasks Flagged)`,
  html: `<html><body style="font-family:Arial,sans-serif;color:#0f172a;line-height:1.6"><div style="max-width:650px;margin:0 auto;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden"><div style="background:#dc2626;color:#fff;padding:20px;text-align:center"><h2 style="margin:0">${heading}</h2><p style="margin:5px 0 0;font-size:14px">InterTech Delay Intelligence Platform — PRJ001</p></div><div style="padding:24px"><p>Dear Project Manager,</p><p>${intro}</p>${taskTable(tasks)}<div style="background:#fef2f2;border:1px solid #fecaca;padding:15px;border-radius:6px;margin-top:20px"><strong style="color:#dc2626">Action required:</strong><ul style="margin:5px 0 0 20px;color:#991b1b">${actions}</ul></div></div></div></body></html>`
 };
}

function highRiskResponseEmail(tasks, ticket, dueAt) {
 const primary = tasks[0];
 const id = taskId(primary);
 const score = taskScore(primary);
 const ticketLink = ticket?.created ? `<a href="${escapeHtml(ticket.url)}" style="color:#2563eb;font-weight:700">${escapeHtml(ticket.key)}</a>` : 'Jira ticket was not configured';
 return {
  subject: `${id} HIGH RISK`,
  html: `<html><body style="font-family:Arial,sans-serif;color:#0f172a;line-height:1.55"><div style="max-width:680px;margin:0 auto;border:1px solid #fecaca;border-radius:9px;overflow:hidden"><div style="background:#b91c1c;color:#fff;padding:22px;text-align:center"><div style="font-size:12px;letter-spacing:.08em;font-weight:700">IMMEDIATE RESPONSE REQUIRED</div><h1 style="font-size:25px;margin:4px 0">${escapeHtml(id)} HIGH RISK (${score}%)</h1><p style="margin:0;font-size:13px">InterTech Delay Intelligence Platform — PRJ001</p></div><div style="padding:24px"><p>Dear Project Manager,</p><p>The model has flagged <strong>${escapeHtml(id)}</strong> as <strong style="color:#b91c1c">HIGH RISK (${score}%)</strong>. This message is the immediate email notification in place of Slack.</p>${taskTable(tasks)}<div style="margin-top:20px;border-left:4px solid #dc2626;background:#fef2f2;padding:14px 16px"><strong>PHASE 1 — IMMEDIATE ALERT (Hour 0)</strong><ul><li>PM alert issued: <strong>${escapeHtml(id)} HIGH RISK</strong>.</li><li>Action notification issued by email: <strong>Needs action NOW</strong>.</li><li>Ticket: ${ticketLink} — <strong>URGENT: Reallocate resources for ${escapeHtml(id)}</strong>.</li></ul></div><div style="margin-top:12px;border-left:4px solid #2563eb;background:#eff6ff;padding:14px 16px"><strong>PHASE 2 — STRUCTURED ACTION (Hour 1)</strong><ul><li>A 15-minute <strong>Resource Review Call</strong> invitation is attached for the PM, Resource Manager, and ${escapeHtml(id)} Lead.</li><li>Agenda: identify staff to reallocate from closed/medium-risk tasks; set daily stand-ups; agree an escalation path if resources are unavailable.</li><li>A calendar reminder is included with the invitation.</li></ul></div><div style="margin-top:12px;border-left:4px solid #b45309;background:#fffbeb;padding:14px 16px"><strong>PHASE 3 — EXECUTION TRACKING (Hour 2+)</strong><ul><li>Reply/record the reallocation confirmation in the ticket: <em>who moved, when, and why</em>.</li><li>A daily 9:00 AM stand-up invitation for the next 14 days is attached.</li><li>Tracking rule: alert if planned hours are above 80% while task completion is below 75%.</li><li>PM confirmation is due by <strong>${escapeHtml(dueAt.toLocaleString('en-GB', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' }))} IST</strong>; otherwise the escalation workflow notifies the resource manager.</li></ul></div><div style="margin-top:12px;border-left:4px solid #475569;background:#f8fafc;padding:14px 16px"><strong>PHASE 4 — ONGOING MONITORING</strong><ul><li>Log daily stand-up notes and review hours versus plan weekly.</li><li>Escalate again if the tracking threshold is exceeded.</li><li>On completion, log the outcome for model-retraining review.</li></ul></div></div></div></body></html>`
 };
}

function jiraConfig(payload) {
 const config = payload.jira_config || {};
 return {
  baseUrl: config.baseUrl || process.env.JIRA_BASE_URL,
  email: config.email || process.env.JIRA_EMAIL,
  apiToken: config.apiToken || process.env.JIRA_API_TOKEN,
  project: config.project || process.env.JIRA_PROJECT || 'PRJ001',
  issueType: config.issueType || process.env.JIRA_HIGH_RISK_ISSUE_TYPE || 'Task'
 };
}

async function queueTwoHourEscalation(payload) {
 const webhookUrl = payload.escalation_webhook_url || process.env.N8N_HIGH_RISK_WEBHOOK_URL || process.env.N8N_WEBHOOK_URL;
 if (!webhookUrl) return { queued: false, status: 'not_configured' };
 try {
  const response = await fetch(webhookUrl, {
   method: 'POST',
   headers: { 'Content-Type': 'application/json' },
   body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`Webhook returned ${response.status}`);
  return { queued: true, status: 'queued' };
 } catch (error) {
  return { queued: false, status: 'failed', error: error.message };
 }
}

// Serverless handler for /api/send_email.
export default async function handler(req, res) {
 res.setHeader('Access-Control-Allow-Origin', '*');
 res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
 res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
 if (req.method === 'OPTIONS') return res.status(200).end();
 if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });

 try {
  const payload = req.body || {};
  const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
  if (!tasks.length) return res.status(400).json({ success: false, message: 'No high-risk tasks supplied for notification.' });

  const recipient = payload.recipient || process.env.MANAGER_EMAIL || 'pm.intertech@gmail.com';
  const smtpConfig = payload.smtp_config || {};
  const host = smtpConfig.host || process.env.SMTP_HOST || 'smtp.gmail.com';
  const port = Number.parseInt(smtpConfig.port || process.env.SMTP_PORT || '587', 10);
  const user = smtpConfig.user || process.env.SMTP_USER || '';
  const pass = smtpConfig.pass || process.env.SMTP_PASS || '';
  const sender = smtpConfig.sender || process.env.SMTP_SENDER || user || 'alerts@intertech.com';
  const alertType = payload.alert_type || 'high_risk_response';
  const isHighRiskResponse = alertType === 'high_risk_response';
  const resourceManager = payload.resource_manager_email || smtpConfig.resource_manager_email || process.env.RESOURCE_MANAGER_EMAIL || '';
  const taskLead = payload.task_lead_email || smtpConfig.task_lead_email || process.env.TASK_LEAD_EMAIL || '';
  const calendarTimeZone = payload.calendar_timezone || smtpConfig.calendar_timezone || process.env.CALENDAR_TIMEZONE || 'Asia/Kolkata';
  const attendees = uniqueEmails([recipient, resourceManager, taskLead]);
  const missingCalendarRoles = [!resourceManager && 'Resource Manager', !taskLead && `${taskId(tasks[0])} Lead`].filter(Boolean);
  const dueAt = new Date(Date.now() + 2 * 60 * 60 * 1000);

  let ticket = { created: false, status: 'not_requested' };
  let ticketError;
  if (isHighRiskResponse && user && pass) {
   try { ticket = await createHighRiskResponseTicket(tasks[0], jiraConfig(payload)); }
   catch (error) { ticketError = error.message; ticket = { created: false, status: 'failed' }; }
  }

  const email = isHighRiskResponse ? highRiskResponseEmail(tasks, ticket, dueAt) : standardEmail(tasks, alertType);
  if (!user || !pass) {
   return res.status(200).json({
    success: false,
    sent_live: false,
    simulated: true,
    requires_credentials: true,
    recipient,
    tasks_notified: tasks.length,
    html_preview: email.html,
    workflow: isHighRiskResponse ? { ticket: { created: false, status: 'not_started_until_smtp_is_configured' }, calendar: { scheduled: false }, escalation: { queued: false } } : undefined,
    message: `SMTP credentials are missing. Add an SMTP username and app password before sending the ${taskId(tasks[0])} response.`
   });
  }

  const transporter = nodemailer.createTransport({
   host,
   port,
   secure: port === 465,
   auth: { user, pass },
   connectionTimeout: 10000
  });
  const attachments = isHighRiskResponse ? highRiskCalendarAttachments(tasks[0], attendees, sender, calendarTimeZone) : [];
  await transporter.sendMail({
   from: sender,
   to: recipient,
   cc: uniqueEmails([resourceManager, taskLead]).filter(email => email !== recipient).join(', ') || undefined,
   subject: email.subject,
   html: email.html,
   attachments
  });

  const escalation = isHighRiskResponse && ticket.created ? await queueTwoHourEscalation({
   event: 'HIGH_RISK_PM_CONFIRMATION_DUE',
   project_id: payload.project_id || 'PRJ001',
   task: tasks[0],
   task_id: taskId(tasks[0]),
   risk_score: taskScore(tasks[0]),
   manager_email: recipient,
   resource_manager_email: resourceManager || recipient,
   task_lead_email: taskLead || '',
   jira_ticket: ticket,
   confirmation_due_at: dueAt.toISOString(),
   tracking_rule: 'Alert if Hours >80% without task completion >75%'
  }) : isHighRiskResponse ? { queued: false, status: 'ticket_required' } : undefined;

  return res.status(200).json({
   success: true,
   sent_live: true,
   recipient,
   tasks_notified: tasks.length,
   subject: email.subject,
   workflow: isHighRiskResponse ? {
    phase1: { pm_email: 'sent', action_notification: 'sent_by_email', jira_ticket: ticket, jira_error: ticketError },
    phase2: { resource_review_invite: 'sent', calendar_reminder: 'sent', attendees, missing_roles: missingCalendarRoles },
    phase3: { daily_standup_invite: 'sent', daily_standup_timezone: calendarTimeZone, confirmation_due_at: dueAt.toISOString(), tracking_rule: 'Alert if Hours >80% without task completion >75%', escalation },
    phase4: { daily_notes: 'record in response ticket', weekly_review: 'included in ticket tracking rule', model_retraining_outcome: 'record on task completion' }
   } : undefined,
   message: `SMTP high-risk response sent to ${recipient}.`
  });
 } catch (error) {
  return res.status(500).json({
   success: false,
   sent_live: false,
   error: error.message,
   message: `SMTP dispatch error (${error.message}). Check the SMTP host, port, user, and app password.`
  });
 }
}
