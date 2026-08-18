/**
 * InterTech — Jira Cloud integration helper.
 * Pulls tasks from a Jira project via REST API v3 and maps them
 * to the InterTech task schema for delay risk prediction.
 *
 * Required env vars (set in .env.local):
 * JIRA_BASE_URL e.g. https://your-org.atlassian.net
 * JIRA_EMAIL Atlassian account email
 * JIRA_API_TOKEN Jira API token (https://id.atlassian.com/manage-profile/security/api-tokens)
 * JIRA_PROJECT Jira project key e.g. PRJ001
 */

const FIELD_MAP = {
 priority: { Highest: 'High', High: 'High', Medium: 'Medium', Low: 'Low', Lowest: 'Low' },
 risk: { Critical: 'High', High: 'High', Medium: 'Medium', Low: 'Low' }
};

/**
 * Fetch open issues from Jira and map to InterTech task schema.
 * @param {object} config - { baseUrl, email, apiToken, project, maxResults }
 * @returns {Promise<object[]>} Array of InterTech-schema task objects
 */
export async function fetchJiraTasks(config) {
 const { baseUrl, email, apiToken, project, maxResults = 100 } = config;
 if (!baseUrl || !email || !apiToken || !project) {
 throw new Error('Missing required Jira config: baseUrl, email, apiToken, project');
 }

 const auth = Buffer.from(`${email}:${apiToken}`).toString('base64');
 const jql = encodeURIComponent(`project = ${project} AND statusCategory != Done ORDER BY created ASC`);
 const fields = 'summary,priority,status,created,duedate,customfield_10016,labels,assignee,timeoriginalestimate';
 const url = `${baseUrl}/rest/api/3/search?jql=${jql}&maxResults=${maxResults}&fields=${fields}`;

 const response = await fetch(url, {
 headers: {
 'Authorization': `Basic ${auth}`,
 'Accept': 'application/json'
 }
 });

 if (!response.ok) {
 const err = await response.text();
 throw new Error(`Jira API error ${response.status}: ${err}`);
 }

 const data = await response.json();
 return (data.issues || []).map(issue => mapJiraIssue(issue, project));
}

/**
 * Map a single Jira issue to the InterTech task schema.
 */
function mapJiraIssue(issue, project) {
 const fields = issue.fields || {};
 const priorityName = fields.priority?.name || 'Medium';
 const priority = FIELD_MAP.priority[priorityName] || 'Medium';

 let risk = 'Medium';
 const labels = fields.labels || [];
 if (labels.some(l => /risk.?high/i.test(l))) risk = 'High';
 else if (labels.some(l => /risk.?low/i.test(l))) risk = 'Low';
 else risk = priority;

 const estSecs = fields.timeoriginalestimate || 0;
 const hours = estSecs > 0 ? Math.round(estSecs / 3600) : 40;

 let discipline = 'General';
 const discLabel = labels.find(l => /^disc:/i.test(l));
 if (discLabel) discipline = discLabel.split(':')[1];

 const created = fields.created ? fields.created.substring(0, 10) : new Date().toISOString().substring(0, 10);
 const target = fields.duedate || new Date(Date.now() + 7 * 86400000).toISOString().substring(0, 10);

 return {
 TaskID: issue.key,
 Description: fields.summary || 'Jira Issue',
 ProjectDiscipline: discipline,
 Priority: priority,
 Risk: risk,
 Hours: hours,
 Created: created,
 Target: target,
 Status: mapJiraStatus(fields.status?.name),
 Location: 'Site',
 _source: 'jira',
 _jira_url: `${issue.self.split('/rest/')[0]}/browse/${issue.key}`
 };
}

function mapJiraStatus(jiraStatus) {
 if (!jiraStatus) return 'Open';
 const s = jiraStatus.toLowerCase();
 if (s.includes('done') || s.includes('closed') || s.includes('resolved')) return 'Closed';
 if (s.includes('progress') || s.includes('review')) return 'In Progress';
 if (s.includes('hold') || s.includes('blocked')) return 'On Hold';
 return 'Open';
}

/**
 * Write risk scores back to Jira as a comment on each issue.
 * @param {object[]} scoredTasks - tasks with .TaskID and .delay_score, .risk_cat
 * @param {object} config - same config as fetchJiraTasks
 */
export async function pushRiskScoresToJira(scoredTasks, config) {
 const { baseUrl, email, apiToken } = config;
 const auth = Buffer.from(`${email}:${apiToken}`).toString('base64');
 const results = [];

 for (const task of scoredTasks) {
 if (!task.TaskID || task._source !== 'jira') continue;
 const commentBody = {
 body: {
 type: 'doc', version: 1,
 content: [{
 type: 'paragraph',
 content: [{
 type: 'text',
 text: `[InterTech AI] Delay Risk Score: ${task.delay_score}% (${task.risk_cat}). ` +
 `Top driver: ${task.shap_drivers?.[0]?.feature || 'N/A'}. ` +
 `Action: ${task.action || 'MONITOR_WEEKLY'}`
 }]
 }]
 }
 };
 try {
 const resp = await fetch(`${baseUrl}/rest/api/3/issue/${task.TaskID}/comment`, {
 method: 'POST',
 headers: { 'Authorization': `Basic ${auth}`, 'Content-Type': 'application/json', 'Accept': 'application/json' },
 body: JSON.stringify(commentBody)
 });
 results.push({ issueKey: task.TaskID, success: resp.ok, status: resp.status });
 } catch (e) {
 results.push({ issueKey: task.TaskID, success: false, error: e.message });
 }
 }
 return results;
}

/**
 * Create the response ticket used to coordinate a model-generated high-risk
 * alert. Keeping this in the Jira connector means the SMTP workflow does not
 * need to expose Jira credentials to the browser.
 */
export async function createHighRiskResponseTicket(task, config) {
 const { baseUrl, email, apiToken, project, issueType = 'Task' } = config;
 if (!baseUrl || !email || !apiToken || !project) {
  return { created: false, status: 'not_configured' };
 }

 const taskId = task.id || task.task_id || task.TaskID || 'HIGH-RISK-TASK';
 const score = Math.round(Number(task.score ?? task.delay_score ?? 0));
 const auth = Buffer.from(`${email}:${apiToken}`).toString('base64');
 const description = [
  `The delay model flagged ${taskId} as HIGH RISK (${score}%).`,
  '',
  'Required response:',
  '• Reallocate a resource from a closed or medium-risk task.',
  '• Hold a 15-minute Resource Review Call with the PM, Resource Manager, and task lead.',
  '• Record the reallocation confirmation with date/time, who moved, and why.',
  '• Run a 9:00 AM daily stand-up for the next two weeks.',
  '• Escalate if no PM confirmation is recorded within two hours.',
  '',
  'Tracking rule: alert when planned hours exceed 80% and task completion remains below 75%.',
  'Upon completion, record the outcome for model retraining.'
 ].join('\n');
 const payload = {
  fields: {
   project: { key: project },
   summary: `URGENT: Reallocate resources for ${taskId}`,
   issuetype: { name: issueType },
   labels: ['intertech-ai', 'high-risk', 'resource-reallocation'],
   description: {
    type: 'doc', version: 1,
    content: description.split('\n').map(text => ({
     type: 'paragraph',
     content: text ? [{ type: 'text', text }] : []
    }))
   }
  }
 };

 const response = await fetch(`${baseUrl.replace(/\/$/, '')}/rest/api/3/issue`, {
  method: 'POST',
  headers: {
   Authorization: `Basic ${auth}`,
   'Content-Type': 'application/json',
   Accept: 'application/json'
  },
  body: JSON.stringify(payload)
 });
 const data = await response.json().catch(() => ({}));
 if (!response.ok) {
  throw new Error(`Jira ticket creation failed (${response.status}): ${data.errorMessages?.join(', ') || data.message || 'unknown error'}`);
 }
 return {
  created: true,
  key: data.key,
  id: data.id,
  url: `${baseUrl.replace(/\/$/, '')}/browse/${data.key}`
 };
}

/** Log a PM's reallocation decision in the response ticket. */
export async function addHighRiskResponseLog(entry, config) {
 const { baseUrl, email, apiToken } = config;
 if (!baseUrl || !email || !apiToken || !entry.ticketKey) {
  return { logged: false, status: 'not_configured' };
 }
 const auth = Buffer.from(`${email}:${apiToken}`).toString('base64');
 const text = [
  '[InterTech AI] Resource reallocation confirmed',
  `Date/time: ${entry.loggedAt}`,
  `Confirmed by: ${entry.who}`,
  `Assignment: ${entry.assignment}`,
  `Reason: ${entry.why}`
 ].join('\n');
 const response = await fetch(`${baseUrl.replace(/\/$/, '')}/rest/api/3/issue/${encodeURIComponent(entry.ticketKey)}/comment`, {
  method: 'POST',
  headers: {
   Authorization: `Basic ${auth}`,
   'Content-Type': 'application/json',
   Accept: 'application/json'
  },
  body: JSON.stringify({
   body: {
    type: 'doc', version: 1,
    content: text.split('\n').map(line => ({
     type: 'paragraph', content: [{ type: 'text', text: line }]
    }))
   }
  })
 });
 if (!response.ok) {
  const detail = await response.text();
  throw new Error(`Jira response log failed (${response.status}): ${detail}`);
 }
 return { logged: true, ticketKey: entry.ticketKey };
}

/**
 * The bundled n8n escalation treats the Jira "In Progress" status as the
 * PM-confirmed signal. Move the response ticket there after the confirmation
 * comment is successfully recorded, when that transition exists in the
 * project's workflow.
 */
export async function markHighRiskResponseConfirmed(ticketKey, config) {
 const { baseUrl, email, apiToken } = config;
 if (!baseUrl || !email || !apiToken || !ticketKey) {
  return { updated: false, status: 'not_configured' };
 }
 const root = baseUrl.replace(/\/$/, '');
 const auth = Buffer.from(`${email}:${apiToken}`).toString('base64');
 const headers = { Authorization: `Basic ${auth}`, Accept: 'application/json' };
 const transitionsResponse = await fetch(`${root}/rest/api/3/issue/${encodeURIComponent(ticketKey)}/transitions`, { headers });
 if (!transitionsResponse.ok) {
  throw new Error(`Jira transition lookup failed (${transitionsResponse.status})`);
 }
 const transitions = (await transitionsResponse.json()).transitions || [];
 const target = transitions.find(item => String(item.to?.name || '').toLowerCase() === 'in progress');
 if (!target) return { updated: false, status: 'in_progress_transition_not_available' };
 const updateResponse = await fetch(`${root}/rest/api/3/issue/${encodeURIComponent(ticketKey)}/transitions`, {
  method: 'POST',
  headers: { ...headers, 'Content-Type': 'application/json' },
  body: JSON.stringify({ transition: { id: target.id } })
 });
 if (!updateResponse.ok) {
  const detail = await updateResponse.text();
  throw new Error(`Jira confirmation transition failed (${updateResponse.status}): ${detail}`);
 }
 return { updated: true, status: 'In Progress', ticketKey };
}
