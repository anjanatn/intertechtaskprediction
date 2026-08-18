const dns = require('dns').promises;
const net = require('net');

const MAX_BYTES = 3_500_000;
const SUPPORTED_EXTENSIONS = new Set(['csv', 'tsv', 'json', 'xlsx', 'xls']);

function isPrivateAddress(address) {
  if (net.isIP(address) === 4) {
    const [a, b] = address.split('.').map(Number);
    return a === 0 || a === 10 || a === 127 || a >= 224 ||
      (a === 100 && b >= 64 && b <= 127) ||
      (a === 169 && b === 254) ||
      (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && (b === 0 || b === 168)) ||
      (a === 198 && (b === 18 || b === 19));
  }
  const value = String(address).toLowerCase();
  return value === '::1' || value === '::' || value.startsWith('fc') || value.startsWith('fd') || value.startsWith('fe80:') || value.startsWith('::ffff:127.');
}

async function validateUrl(value) {
  const url = new URL(value);
  if (url.protocol !== 'https:') throw new Error('Only public HTTPS dataset URLs are accepted.');
  if (!url.hostname || url.hostname === 'localhost' || url.hostname.endsWith('.local')) {
    throw new Error('The dataset URL must point to a public host.');
  }
  const records = await dns.lookup(url.hostname, { all: true, verbatim: true });
  if (!records.length || records.some(record => isPrivateAddress(record.address))) {
    throw new Error('The dataset URL resolved to a non-public address.');
  }
  return url;
}

async function fetchPublicDataset(value) {
  let target = String(value || '');
  for (let redirect = 0; redirect <= 3; redirect += 1) {
    await validateUrl(target);
    const response = await fetch(target, { redirect: 'manual', headers: { 'User-Agent': 'InterTechDatasetImporter/1.0' } });
    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get('location');
      if (!location) throw new Error('The dataset host returned a redirect without a location.');
      target = new URL(location, target).toString();
      continue;
    }
    if (!response.ok) throw new Error(`Could not download the public dataset (${response.status}).`);

    const finalUrl = await validateUrl(response.url || target);
    const extension = finalUrl.pathname.split('.').pop().toLowerCase();
    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    if (!SUPPORTED_EXTENSIONS.has(extension) && !/(csv|json|spreadsheet|excel|tab-separated)/.test(contentType)) {
      throw new Error('Use a direct .csv, .tsv, .json, .xlsx, or .xls dataset download URL, not a catalogue or landing page.');
    }
    const declaredLength = Number(response.headers.get('content-length') || 0);
    if (declaredLength > MAX_BYTES) throw new Error('The public dataset is larger than the 3.5 MB import limit.');
    const data = Buffer.from(await response.arrayBuffer());
    if (data.length > MAX_BYTES) throw new Error('The public dataset is larger than the 3.5 MB import limit.');
    const rawName = decodeURIComponent(finalUrl.pathname.split('/').pop() || 'public_dataset.csv');
    const filename = rawName.replace(/[^a-zA-Z0-9._-]/g, '_') || 'public_dataset.csv';
    return { data, filename, contentType: response.headers.get('content-type') || 'application/octet-stream' };
  }
  throw new Error('The public dataset redirected too many times.');
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });

  try {
    const payload = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
    const result = await fetchPublicDataset(payload.url);
    res.setHeader('Content-Type', result.contentType);
    res.setHeader('Content-Disposition', `attachment; filename="${result.filename}"`);
    res.setHeader('X-Dataset-Filename', encodeURIComponent(result.filename));
    return res.status(200).send(result.data);
  } catch (error) {
    return res.status(400).json({ success: false, error: error.message });
  }
};
