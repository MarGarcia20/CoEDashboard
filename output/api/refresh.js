// Vercel serverless function — triggers GitHub Actions workflow_dispatch
// Env vars required:
//   GITHUB_WORKFLOW_TOKEN  — fine-grained PAT with actions:write on the repo
//   ALLOWED_ORIGIN         — (optional) exact origin allowed to trigger refresh.
//                            When unset, any *.vercel.app origin is accepted.

const OWNER = 'MarGarcia20';
const REPO  = 'CoEDashboard';
const WORKFLOW_FILE = 'refresh.yml';
const REF = 'main';

function isAllowedOrigin(origin, allowed) {
  if (!origin) return false;
  if (allowed) return origin === allowed;
  // Default: accept any *.vercel.app origin (useful for preview + production deploys)
  try {
    const url = new URL(origin);
    return url.hostname.endsWith('.vercel.app');
  } catch {
    return false;
  }
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // ── Origin check ──────────────────────────────────────────
  // Require same-origin call from the dashboard (or ALLOWED_ORIGIN if set).
  const origin = req.headers.origin || req.headers.referer || '';
  const allowed = process.env.ALLOWED_ORIGIN;
  if (!isAllowedOrigin(origin, allowed)) {
    console.warn(`Rejected refresh from origin: ${origin || '(none)'}`);
    return res.status(403).json({ error: 'Forbidden origin' });
  }

  // ── CSRF-style header check ───────────────────────────────
  // The dashboard's fetch() always sends this. External crawlers won't.
  if (req.headers['x-requested-with'] !== 'coe-dashboard') {
    console.warn(`Rejected refresh — missing/invalid X-Requested-With`);
    return res.status(403).json({ error: 'Invalid request' });
  }

  // ── GitHub token check ────────────────────────────────────
  const token = process.env.GITHUB_WORKFLOW_TOKEN;
  if (!token) {
    console.error('GITHUB_WORKFLOW_TOKEN not set');
    return res.status(500).json({ error: 'Refresh not configured — contact admin' });
  }

  // ── Trigger GitHub Actions workflow ───────────────────────
  try {
    const response = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ref: REF }),
      }
    );

    if (response.status === 204) {
      return res.status(200).json({
        ok: true,
        message: 'Refresh triggered — dashboard updates in ~60 seconds',
      });
    }

    const text = await response.text();
    console.error('GitHub API error:', response.status, text);
    return res.status(502).json({ error: `GitHub API returned ${response.status}` });

  } catch (err) {
    console.error('Fetch error:', err);
    return res.status(500).json({ error: 'Network error contacting GitHub' });
  }
}
