// Serverless handler for Vercel API endpoint /api/n8n_webhook on intertechtaskprediction.vercel.app
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
    const webhookUrl = payload.webhook_url || 'http://localhost:5678/webhook/high-risk-delay-alert';
    const recipient = payload.recipient || 'pm.intertech@gmail.com';

    return res.status(200).json({
      success: true,
      n8n_triggered: false,
      simulated: true,
      webhook_url: webhookUrl,
      recipient: recipient,
      tasks_count: tasks.length,
      n8n_workflow_template: 'public/intertech_n8n_workflow.json',
      message: `[n8n Workflow Prepared] High-Risk task payload formatted for n8n. Target webhook: ${webhookUrl}`
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
}
