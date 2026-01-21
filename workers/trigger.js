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
  // 1. HTTP Request Handler (Trigger Only)
  async fetch(request, env) {
    const url = new URL(request.url);

    // POST /: Trigger workflow manually
    if (request.method === "POST" && url.pathname === "/") {
        try {
            const { program_name, stream_url, duration } = await request.json();
    
            if (!program_name || !duration) {
                return new Response(
                    "Missing required fields: program_name, duration",
                    { status: 400 }
                );
            }
    
            const result = await triggerWorkflow(env, { program_name, stream_url, duration });
            return new Response(result, { status: 200 });
        } catch (e) {
            return new Response(`Error: ${e.message}`, { status: 500 });
        }
    }

    return new Response("EBS Record Worker Running (Secure Mode)", { status: 200 });
  },

  // 2. Scheduled Cron Handler
  async scheduled(event, env, ctx) {
    const cron = event.cron;
    console.log(`[Scheduled] Triggered by cron: "${cron}"`);
    
    // Determine current UTC time from scheduledTime
    const scheduledDate = new Date(event.scheduledTime);
    const utcHours = String(scheduledDate.getUTCHours()).padStart(2, '0');
    const utcMinutes = String(scheduledDate.getUTCMinutes()).padStart(2, '0');
    const timeKey = `${utcHours}:${utcMinutes}`;
    
    console.log(`[Scheduled] Triggering Workflow for Time Slot: ${timeKey}`);

    const payload = {
        time_slot: timeKey
    };

    ctx.waitUntil(triggerWorkflow(env, payload).catch(err => {
        console.error(`[Scheduled] Workflow trigger failed: ${err.message}`);
    }));
  }
};
