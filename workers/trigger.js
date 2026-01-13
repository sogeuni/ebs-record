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

    return new Response("Method Not Allowed. Only POST / is supported for manual triggers.", { status: 405 });
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
