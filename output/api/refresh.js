// Vercel serverless function — triggers GitHub Actions workflow_dispatch
// Env var required: GITHUB_WORKFLOW_TOKEN (fine-grained PAT, actions:write scope)

const OWNER = 'MarGarcia20';
const REPO  = 'CoEDashboard';
const WORKFLOW_FILE = 'refresh.yml';
const REF = 'main';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const token = process.env.GITHUB_WORKFLOW_TOKEN;
  if (!token) {
    console.error('GITHUB_WORKFLOW_TOKEN not set');
    return res.status(500).json({ error: 'Refresh not configured — contact admin' });
  }

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
