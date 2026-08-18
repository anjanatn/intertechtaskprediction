module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });

  // Vercel serverless storage is ephemeral, so activating a durable model retrain
  // is intentionally available only through the local Python server.
  return res.status(409).json({
    success: false,
    code: 'LOCAL_TRAINING_REQUIRED',
    error: 'The prepared CSV can be downloaded here. Start the local Python server to activate it as the persistent training dataset.'
  });
};
