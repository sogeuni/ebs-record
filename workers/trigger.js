// Schedule Configuration is now in wrangler.toml [vars] SCHEDULE_JSON

/**
 * Common function to trigger GitHub Workflow
 */
async function triggerWorkflow(env, { program_name, stream_url, duration }) {
  const githubToken = env.GITHUB_TOKEN;
  if (!githubToken) {
    console.error("GITHUB_TOKEN not configured");
    throw new Error("Server Error: GITHUB_TOKEN not configured");
  }

  const response = await fetch(
    "https://api.github.com/repos/sogeuni/ebs-record/actions/workflows/record.yml/dispatches",
    {
      method: "POST",
      headers: {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": `Bearer ${githubToken}`,
        "User-Agent": "Cloudflare-Worker"
      },
      body: JSON.stringify({
        ref: "main",
        inputs: {
          program_name,
          stream_url,
          duration: String(duration)
        }
      })
    }
  );

  if (!response.ok) {
    const text = await response.text();
    const errorMsg = `GitHub API Error: ${response.status} ${text}`;
    console.error(errorMsg);
    throw new Error(errorMsg);
  }

  console.log(`Triggered workflow for ${program_name}`);
  return "Workflow triggered successfully";
}

/**
 * Generate HTML for the Open Radio style viewer
 */
async function generateViewerHtml(env) {
    const githubToken = env.GITHUB_TOKEN;
    const repoOwner = "sogeuni";
    const repoName = "ebs-record";
    const branch = "main";
    const recordingsPath = "recordings";

    // CSS for Open Radio Style
    const css = `
        :root {
            --bg-color: #1a1a1a;
            --text-color: #e0e0e0;
            --accent-color: #ff5252;
            --card-bg: #2d2d2d;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            color: var(--accent-color);
            margin-bottom: 40px;
            font-size: 2.5rem;
            letter-spacing: 2px;
        }
        .program-card {
            background-color: var(--card-bg);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            transition: transform 0.2s;
        }
        .program-card:hover {
            transform: translateY(-2px);
        }
        .program-title {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 15px;
            color: #fff;
            border-bottom: 1px solid #444;
            padding-bottom: 10px;
        }
        .file-list {
            list-style: none;
            padding: 0;
        }
        .file-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #3d3d3d;
        }
        .file-item:last-child {
            border-bottom: none;
        }
        .file-name {
            font-size: 0.9rem;
            color: #aaa;
        }
        audio {
            height: 32px;
            max-width: 200px;
        }
        .download-link {
            color: var(--accent-color);
            text-decoration: none;
            margin-left: 10px;
            font-size: 0.8rem;
        }
        .loading {
            text-align: center;
            font-size: 1.2rem;
            margin-top: 50px;
        }
    `;

    try {
        // Fetch directory listing from GitHub API
        const apiUrl = `https://api.github.com/repos/${repoOwner}/${repoName}/contents/${recordingsPath}?ref=${branch}`;
        const headers = {
            "User-Agent": "Cloudflare-Worker",
            "Accept": "application/vnd.github.v3+json"
        };
        if (githubToken) {
            headers["Authorization"] = `Bearer ${githubToken}`;
        }

        const response = await fetch(apiUrl, { headers });
        if (!response.ok) {
            throw new Error(`Failed to fetch recordings: ${response.status}`);
        }
        const programs = await response.json();
        
        // Parallel fetch for subdirectories
        const programsHtmlPromises = programs
            .filter(item => item.type === "dir")
            .map(async (programDir) => {
                const subUrl = programDir.url;
                const subResp = await fetch(subUrl, { headers });
                const files = await subResp.json();
                
                const audioFiles = files
                    .filter(f => f.name.endsWith('.m4a'))
                    .sort((a, b) => b.name.localeCompare(a.name)); // Newest first

                if (audioFiles.length === 0) return "";

                const fileListHtml = audioFiles.map(file => `
                    <li class="file-item">
                        <span class="file-name">${file.name.replace('.m4a', '')}</span>
                        <div style="display:flex; align-items:center;">
                            <audio controls src="${file.download_url}"></audio>
                            <a href="${file.download_url}" class="download-link" download>⬇</a>
                        </div>
                    </li>
                `).join('');

                return `
                    <div class="program-card">
                        <div class="program-title">${programDir.name}</div>
                        <ul class="file-list">
                            ${fileListHtml}
                        </ul>
                    </div>
                `;
            });

        const programsHtml = (await Promise.all(programsHtmlPromises)).join('');

        return `
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Open Radio Archive</title>
                <style>${css}</style>
            </head>
            <body>
                <div class="container">
                    <h1>OPEN RADIO ARCHIVE</h1>
                    ${programsHtml || '<div class="loading">No recordings found.</div>'}
                </div>
            </body>
            </html>
        `;

    } catch (e) {
        return `<html><body><h1>Error</h1><p>${e.message}</p></body></html>`;
    }
}

export default {
  // 1. HTTP Request Handler
  async fetch(request, env) {
    const url = new URL(request.url);

    // POST /: Trigger workflow
    if (request.method === "POST") {
        try {
            const { program_name, stream_url, duration } = await request.json();
    
            if (!program_name || !stream_url || !duration) {
                return new Response(
                    "Missing required fields: program_name, stream_url, duration",
                    { status: 400 }
                );
            }
    
            const result = await triggerWorkflow(env, { program_name, stream_url, duration });
            return new Response(result, { status: 200 });
        } catch (e) {
            return new Response(`Error: ${e.message}`, { status: 500 });
        }
    }

    // GET /: Show Viewer
    // or GET /list if prefered, but user asked for simplicity.
    // Let's assume GET on root shows viewer.
    if (request.method === "GET") {
        const html = await generateViewerHtml(env);
        return new Response(html, {
            headers: { "Content-Type": "text/html; charset=utf-8" }
        });
    }

    return new Response("Method Not Allowed", { status: 405 });
  },

  // 2. Scheduled Cron Handler
  async scheduled(event, env, ctx) {
    const cron = event.cron;
    console.log(`[Scheduled] Triggered by cron: "${cron}"`);
    
    let scheduleMap = {};
    try {
        if (env.SCHEDULE_JSON) {
            scheduleMap = JSON.parse(env.SCHEDULE_JSON);
        }
    } catch (e) {
        console.error("[Scheduled] Failed to parse SCHEDULE_JSON", e);
        return;
    }

    // Robust matching: Normalize spaces
    // Cloudflare cron strings might differ slightly in spacing from our JSON keys
    const normalizeCron = (str) => str.replace(/\s+/g, ' ').trim();
    const targetCron = normalizeCron(cron);

    // Find task by normalized key comparison
    let task = null;
    for (const key of Object.keys(scheduleMap)) {
        if (normalizeCron(key) === targetCron) {
            task = scheduleMap[key];
            console.log(`[Scheduled] Match found for key: "${key}"`);
            break;
        }
    }

    if (task) {
      console.log(`[Scheduled] Executing task for program: ${task.program_name}`);
      ctx.waitUntil(triggerWorkflow(env, task).catch(err => {
          console.error(`[Scheduled] Workflow trigger failed: ${err.message}`);
      }));
    } else {
      console.log(`[Scheduled] No matching task found for cron: "${cron}". Available keys: ${Object.keys(scheduleMap).join(', ')}`);
    }
  }
};
