/**
 * InterTech — Jira Cloud Integration Connector
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
