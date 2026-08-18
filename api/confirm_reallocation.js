import { addHighRiskResponseLog, markHighRiskResponseConfirmed } from '../lib/jira_connector.js';

function jiraConfig(payload) {
 const config = payload.jira_config || {};
 return {
  baseUrl: config.baseUrl || process.env.JIRA_BASE_URL,
  email: config.email || process.env.JIRA_EMAIL,
  apiToken: config.apiToken || process.env.JIRA_API_TOKEN
 };
}

/**
 * Records the human confirmation required by Phase 3. In a configured Jira
 * project the log is written as a ticket comment, providing durable audit
 * history rather than relying on a serverless filesystem.
 */
export default async function handler(req, res) {
 res.setHeader('Access-Control-Allow-Origin', '*');
 res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
 res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
 if (req.method === 'OPTIONS') return res.status(200).end();
 if (req.method !== 'POST') return res.status(405).json({ success: false, error: 'POST only' });

 const payload = req.body || {};
 const taskId = String(payload.task_id || '').trim();
 const who = String(payload.who || '').trim();
 const assignment = String(payload.assignment || '').trim();
 const why = String(payload.why || '').trim();
 if (!taskId || !who || !assignment || !why) {
  return res.status(400).json({ success: false, error: 'task_id, who, assignment, and why are required.' });
 }

 const entry = {
  ticketKey: String(payload.jira_ticket_key || '').trim(),
  loggedAt: new Date().toISOString(),
  who,
  assignment,
  why
 };
 try {
  const config = jiraConfig(payload);
  const ticketLog = await addHighRiskResponseLog(entry, config);
  let confirmationStatus = { updated: false, status: 'not_started' };
  if (ticketLog.logged) {
   try { confirmationStatus = await markHighRiskResponseConfirmed(entry.ticketKey, config); }
   catch (error) { confirmationStatus = { updated: false, status: 'failed', error: error.message }; }
  }
  return res.status(200).json({
   success: true,
   task_id: taskId,
   logged_at: entry.loggedAt,
   persistent_log: ticketLog,
   confirmation_status: confirmationStatus,
   message: ticketLog.logged ? `Reallocation confirmation logged in Jira ticket ${entry.ticketKey}.` : 'Reallocation confirmation accepted; configure Jira to retain the shared audit log.'
  });
 } catch (error) {
  return res.status(502).json({ success: false, error: error.message });
 }
}
