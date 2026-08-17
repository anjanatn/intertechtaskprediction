// Vercel serverless handler for /api/model_registry
// GET → returns the model version registry manifest
// POST → activates a specific version (rollback)
export default async function handler(req, res) {
 res.setHeader('Access-Control-Allow-Origin', '*');
 res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
 res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

 if (req.method === 'OPTIONS') return res.status(200).end();

 if (req.method === 'GET') {
 return res.status(200).json({
 info: 'Model registry is managed by the local Python server. ' +
 'Deploy to local server (python server.py) to use version rollback.',
 registry: [],
 vercel_mode: true
 });
 }

 if (req.method === 'POST') {
 return res.status(200).json({
 success: false,
 message: 'Version rollback requires local Python server deployment. ' +
 'Run: python server.py and use http://localhost:8080'
 });
 }

 return res.status(405).json({ error: 'Method not allowed' });
}
