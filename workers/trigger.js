// Schedule Configuration is now in wrangler.toml [vars] SCHEDULE_JSON

/**
 * Common function to trigger GitHub Workflow
 */
async function triggerWorkflow(env, { program_name, stream_url, duration, scheduled_time }) {
  const githubToken = env.GITHUB_TOKEN;
  if (!githubToken) {
    console.error("GITHUB_TOKEN not configured");
    throw new Error("Server Error: GITHUB_TOKEN not configured");
  }

  // Use task-specific URL or Fallback to Common URL
  const finalStreamUrl = stream_url || env.COMMON_STREAM_URL;

  if (!finalStreamUrl) {
      throw new Error("No stream_url provided and no COMMON_STREAM_URL configured.");
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
          stream_url: finalStreamUrl,
          duration: String(duration),
          scheduled_time: scheduled_time || "" // KST HH:MM
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

    // GET Proxy: Serve files from GitHub Raw (Private Repo Support)
    // Needs GITHUB_TOKEN in headers
    if (request.method === "GET") {
        const rawUrl = env.RAW_URL || "https://raw.githubusercontent.com/sogeuni/ebs-record/publish";
        
        if (url.pathname === "/") {
             return new Response("EBS Record Worker (Private Proxy) is Running.", { status: 200 });
        }

        let targetPath = url.pathname;
        let finalTargetUrl = "";
        
        // We expect path like /test/feed.xml -> Raw URL is now root of publish branch
        // So we just append the path directly.
        finalTargetUrl = `${rawUrl}${targetPath}`;
        
        console.log(`[Proxy] Fetching Raw: ${finalTargetUrl}`);

        try {
            const response = await fetch(finalTargetUrl, {
                headers: {
                    "User-Agent": "Cloudflare-Worker-Proxy",
                    "Authorization": `Bearer ${env.GITHUB_TOKEN}` // AUTHENTICATION!
                }
            });
            
            if (!response.ok) {
                 console.error(`[Proxy] Upstream Error: ${response.status}`);
                 if (response.status === 404) return new Response("File not found on GitHub", { status: 404 });
                 if (response.status === 403) return new Response("Access Denied (Token Error?)", { status: 403 });
            }

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

    // Determine current UTC time from scheduledTime
    const scheduledDate = new Date(event.scheduledTime);
    const utcHours = String(scheduledDate.getUTCHours()).padStart(2, '0');
    const utcMinutes = String(scheduledDate.getUTCMinutes()).padStart(2, '0');
    const timeKey = `${utcHours}:${utcMinutes}`;
    const utcDay = scheduledDate.getUTCDay(); // 0=Sun ... 6=Sat
    
    console.log(`[Scheduled] Time Key: ${timeKey}, UTC Day: ${utcDay}`);

    let entry = scheduleMap[timeKey];
    let taskToRun = null;

    if (entry) {
        if (Array.isArray(entry)) {
            // Find task matching current day
            taskToRun = entry.find(t => !t.days || t.days.includes(utcDay));
            if (!taskToRun) {
                console.log(`[Scheduled] No matching task for day ${utcDay} in array list.`);
            }
        } else {
            // Single task object
            taskToRun = entry;
            // Optional: Check 'days' if present even on single object
            if (taskToRun.days && !taskToRun.days.includes(utcDay)) {
                console.log(`[Scheduled] Task skipped: Day ${utcDay} not in ${taskToRun.days}`);
                taskToRun = null;
            }
        }
    }

    if (taskToRun) {
      console.log(`[Scheduled] Executing task for program: ${taskToRun.program_name}`);
      ctx.waitUntil(triggerWorkflow(env, taskToRun).catch(err => {
          console.error(`[Scheduled] Workflow trigger failed: ${err.message}`);
      }));
    } else {
      console.log(`[Scheduled] No task found or matched for time: "${timeKey}"`);
    }
  }
};
