/**
 * Vercel serverless handler for /api/sync_integration
 * Accepts { tool: 'jira', config: {...} } and returns predicted tasks.
 *
 * Note: The actual ML model scoring runs client-side (predictTasksClientSide)
 * since Vercel cannot run scikit-learn. This endpoint fetches and normalises
 * tasks from the PM tool; the frontend applies the scoring model.
 */
import { fetchJiraTasks } from './integrations/jira_connector.js';

export default async function handler(req, res) {
 res.setHeader('Access-Control-Allow-Origin', '*');
 res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
 res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

 if (req.method === 'OPTIONS') return res.status(200).end();
 if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

 const { tool, config } = req.body || {};

 try {
 let tasks = [];
 if (tool === 'jira') {
 const resolvedConfig = {
 baseUrl: config?.baseUrl || process.env.JIRA_BASE_URL,
 email: config?.email || process.env.JIRA_EMAIL,
 apiToken: config?.apiToken || process.env.JIRA_API_TOKEN,
 project: config?.project || process.env.JIRA_PROJECT || 'PRJ001',
 maxResults: config?.maxResults || 200
 };
 tasks = await fetchJiraTasks(resolvedConfig);
 } else {
 return res.status(400).json({
 success: false,
 error: `Unsupported tool: ${tool}. Supported: jira`
 });
 }

 return res.status(200).json({
 success: true,
 tool,
 total_fetched: tasks.length,
 tasks,
 message: `Fetched ${tasks.length} tasks from ${tool}. Apply ML scoring via the dashboard Import & Predict tab.`
 });
 } catch (err) {
 return res.status(500).json({ success: false, error: err.message });
 }
}
