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

export default {
  // 1. HTTP Request Handler
  async fetch(request, env) {
    const url = new URL(request.url);

    // POST /: Trigger workflow
    if (request.method === "POST" && url.pathname === "/") {
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

    // GET Proxy: Serve files from GitHub Pages
    // Map /program/file -> PAGES_URL/recordings/program/file
    // Map /recordings/program/file -> PAGES_URL/recordings/program/file (Support both if user includes recordings/)
    if (request.method === "GET") {
        const pagesUrl = env.PAGES_URL || "https://sogeuni.github.io/record-stream";
        
        // Handle root request
        if (url.pathname === "/") {
             return new Response("EBS Record Worker is Running.", { status: 200 });
        }

        let targetPath = url.pathname;
        
        // If the path already starts with /recordings, we just append it to pagesUrl (assuming pagesUrl is root)
        // BUT pagesUrl is `.../recordings`? No, pagesUrl is `.../record-stream` usually.
        // Let's assume env.PAGES_URL is "https://sogeuni.github.io/record-stream"
        
        // Strategy: We want to support:
        // 1. /test/feed.xml -> gets /recordings/test/feed.xml
        // 2. /recordings/test/feed.xml -> gets /recordings/test/feed.xml (idempotent)
        
        let finalTargetUrl = "";
        
        if (targetPath.startsWith("/recordings/")) {
             finalTargetUrl = `${pagesUrl}${targetPath}`;
        } else {
             finalTargetUrl = `${pagesUrl}/recordings${targetPath}`;
        }
        
        console.log(`[Proxy] Fetching: ${finalTargetUrl}`);

        try {
            const response = await fetch(finalTargetUrl, {
                headers: {
                    "User-Agent": "Cloudflare-Worker-Proxy"
                }
            });

            return new Response(response.body, {
                status: response.status,
                statusText: response.statusText,
                headers: response.headers
            });
        } catch (e) {
            console.error(`[Proxy] Error: ${e.message}`);
            return new Response("Failed to fetch content", { status: 502 });
        }
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
