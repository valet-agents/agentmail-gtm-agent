This folder contains the source for a Skilled Agent originally built for the Valet runtime. Changes should follow the Skilled Agent open standard.

Ported from the upstream [AgentMail GTM Agent](https://github.com/agentmail-to/agentmail-gtm-agent) (MIT). Same product idea — cold outreach that ships, follows up once, and routes the warm replies — re-architected on top of the Valet platform: webhooks instead of polling, Slack as the operator console, dashboard slots instead of `.env` editing, a one-hour heartbeat that sweeps the queue instead of a tight `while True` poll loop.

## Setup

### Connectors

- **agentmail**: The AgentMail CLI, preconfigured with the API key from the connector slot. The connector name `agentmail` IS the CLI command on PATH — invoke it as `agentmail`, never as `npx agentmail-cli` or any npm package name. The agent uses it to list/create the dedicated outbound inbox, send first-touches via `messages send` (NEW thread), follow up via `messages reply` (in-thread), forward interested replies via `messages forward`, and label inbound messages by classification. See `skills/agentmail/SKILL.md` for invocation patterns.

The prospect-list bookkeeping is handled by `skills/gtm/prospects.py` — a stdlib-only Python helper vendored from the upstream AgentMail template. It exposes a CLI with `queued`, `due`, `update`, and `log` subcommands so the agent can shell out without import plumbing. Requires `python3` on the agent runtime — no `pip install` needed.

### Channels

- **slack** (slack): The agent's per-agent Slack bot — your console for the queue. Listens for @mentions and replies in-thread. Four modes: status questions ("who's queued?"), one-off queues ("queue jane@acme.com hook=..."), pause/resume sends, and question hand-off drafts (the user replies to a `[QUESTION] from...` post with their answer; the agent restates and waits for `👍` before sending). All sends require an explicit two-step confirm. Slack writes use the auto-injected outbound Slack connector.
- **webhook** (webhook): The generic webhook channel. AgentMail pushes each `message.received` event to the agent's webhook URL, and the agent's per-event reply-classification flow runs on receipt — see `channels/webhook.md`.
- **heartbeat** (1h, UTC): The hourly sweep that sends one queued first-touch and one due follow-up per fire — see `channels/heartbeat.md`. Bounded by design: even if the queue is huge, the agent never burst-sends.

### Secrets

- **AGENTMAIL_API_KEY** — required, sourced from the AgentMail dashboard at agentmail.to. The connector slot collects it during the dashboard setup flow.
- **PROSPECTS_CSV** — required, the prospect list as CSV. Required columns: `email, first_name, company, hook`. The agent on first heartbeat fire writes this slot's content to a working `prospects.csv` file under the runtime cwd, then uses `prospects.py` against it.
- **SALES_HANDOFF_EMAIL** — required, where the agent forwards interested replies.

The Slack bot is provisioned via OAuth in the dashboard, so no other secrets are required.

### External Setup

1. Sign up for AgentMail at agentmail.to and mint an API key (Settings → API Keys). Paste it into the `AGENTMAIL_API_KEY` slot during deploy. The agent creates its own dedicated outbound inbox the first time the heartbeat or webhook fires — you don't need to create one upfront.
2. Build your prospect CSV. The schema is `email, first_name, company, hook, status, sent_at, followup_at, replied_at, classification, thread_id` — leave the last six columns empty for new rows. See `skills/gtm/prospects.example.csv` for a starter. **Hook quality drives email quality** — write specific signals ("just announced a Series B and is hiring 5 sales reps"), not generic compliments ("admire what you're doing"). Paste the CSV content into the `PROSPECTS_CSV` slot during deploy.
3. Decide where interested replies should go. Paste that email address into `SALES_HANDOFF_EMAIL`.
4. Install the agent's Slack bot from the dashboard. Invite it to one channel where you want a window into the queue. Status questions ("who replied today?"), one-off queues, pause/resume, and question hand-offs all happen via @mention in that channel.
5. After deploy, copy the agent's webhook URL from the dashboard, then run this once from your terminal (with your AgentMail API key in the environment):

   ```sh
   PAGER=cat agentmail webhooks create \
     --url "<agent-webhook-url>" \
     --event message.received
   ```

   AgentMail starts pushing each new email to the agent in real time. Test by sending a reply to one of the agent's first-touch emails (you'll see the classification land in Slack as a `[QUESTION]` post or a hand-off forward, and the prospect's row in MEMORY.md will update).

## Customizing

- **Refresh the prospect list**: The `PROSPECTS_CSV` slot is the deploy-time source of truth. To add new prospects, edit the slot in the dashboard and redeploy — the agent on the next heartbeat will sync the new content to its working `prospects.csv` file. Prospects already in MEMORY.md keep their runtime status across redeploys; new rows in the CSV start as `queued`. (For a true at-runtime queue, @mention the Slack bot with `queue jane@acme.com hook='...'` — that appends to MEMORY.md without redeploy. The CSV is the bulk-import path; Slack is the one-off path.)
- **Change the follow-up cadence**: SOUL Phase 3 + `channels/heartbeat.md` use 96 hours (4 days). Bump up to 168h (7 days) for a longer wait, or down to 48h for more aggressive cadence. Update both files together.
- **Tighten or loosen the OOO regex**: the *Quick Filter* in `channels/webhook.md` routes out-of-office replies as `ooo`. Add patterns for languages or templates your inbox sees regularly.
- **Change the email-body word cap**: SOUL Personality caps first-touches at 80 words. Drop to 60 for a tighter voice, raise for a more conversational one.
- **Pin a specific inbox**: if your AgentMail account already has multiple inboxes and you don't want auto-creation, set the `INBOX_ID` env var on the agent (or pre-populate `MEMORY.md` `inbox_id`). The first-fire bootstrap in `skills/agentmail/SKILL.md` will skip discovery.
- **Drop the heartbeat entirely**: if you'd rather queue every prospect manually via Slack, remove the `heartbeat` channel from `valet.yaml`, drop `channels/heartbeat.md`, and trim the *Heartbeat Workflow* section from `SOUL.md`. The webhook flow runs unchanged; the agent just won't send anything on its own.
- **Change the personality**: edit the *Personality* section of `SOUL.md`. The default voice is concise, no corporate-speak, one specific ask. Adjust the word caps, the sign-off shape, or the tone — the agent reads SOUL on every fire, so changes take effect on the next heartbeat or webhook.
