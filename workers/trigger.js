/**
 * Common function to trigger GitHub Workflow
 */
async function triggerWorkflow(env, inputs) {
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
        inputs: inputs
      })
    }
  );

  if (!response.ok) {
    const text = await response.text();
    const errorMsg = `GitHub API Error: ${response.status} ${text}`;
    console.error(errorMsg);
    throw new Error(errorMsg);
  }

  console.log(`Triggered workflow with inputs: ${JSON.stringify(inputs)}`);
  return "Workflow triggered successfully";
}

export default {
  // 1. HTTP Request Handler (Manual Trigger)
  async fetch(request, env) {
    const url = new URL(request.url);

    // POST /: Trigger workflow manually
    if (request.method === "POST" && url.pathname === "/") {
        try {
            const payload = await request.json();
            
            // Allow manual override of any inputs (program_name, time_slot, etc.)
            const result = await triggerWorkflow(env, payload);
            return new Response(result, { status: 200 });
        } catch (e) {
            return new Response(`Error: ${e.message}`, { status: 500 });
        }
    }

    return new Response("EBS Record Worker Running (Trigger Only)", { status: 200 });
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
    
    console.log(`[Scheduled] Sending Trigger for Time Slot: ${timeKey}`);

    // Just send the time_slot. The GitHub Action (recorder.py) will handle schedule resolution.
    ctx.waitUntil(triggerWorkflow(env, {
        time_slot: timeKey
    }).catch(err => {
        console.error(`[Scheduled] Workflow trigger failed: ${err.message}`);
    }));
  }
};
