This folder contains the source for a Skilled Agent originally built for the Valet runtime. Changes should follow the Skilled Agent open standard.

Ported from the upstream [AgentMail GTM Agent](https://github.com/agentmail-to/agentmail-gtm-agent) (MIT). Same product idea — cold outreach that ships, follows up once, and routes the warm replies — re-architected on top of the Valet platform: webhooks instead of polling, Slack as the operator console AND the prospect-queueing interface, dashboard slots only for the API key, a one-hour heartbeat that sweeps MEMORY.md instead of a tight `while True` poll loop.

## Setup

### Connectors

- **agentmail**: The AgentMail CLI, preconfigured with the API key from the connector slot. The connector name `agentmail` IS the CLI command on PATH — invoke it as `agentmail`, never as `npx agentmail-cli` or any npm package name. The agent uses it to list/create the dedicated outbound inbox, send first-touches via `messages send` (NEW thread), follow up via `messages reply` (in-thread), forward interested replies via `messages forward`, and label inbound messages by classification. See `skills/agentmail/SKILL.md` for invocation patterns.

The prospect store is `MEMORY.md` `prospects` — a markdown-backed map the agent updates in place each fire. There is no CSV, no helper script: the agent reads and writes the map directly. Slack is the queueing interface; the heartbeat sweeps the map.

### Channels

- **slack** (slack): The agent's per-agent Slack bot — your console for the queue AND the way you add new prospects. Listens for @mentions and replies in-thread. Modes: queue requests (single, mass-with-shared-hook, or email-per-line paste), status questions ("who's queued?"), pause/resume, remove a prospect, and question hand-off drafts (the user replies to a `[QUESTION] from...` post with their answer; the agent restates and waits for `👍` before sending). All sends require an explicit two-step confirm. Slack writes use the auto-injected outbound Slack connector.
- **webhook** (webhook): The generic webhook channel. AgentMail pushes each `message.received` event to the agent's webhook URL, and the agent's per-event reply-classification flow runs on receipt — see `channels/webhook.md`.
- **heartbeat** (1h, UTC): The hourly sweep that sends one queued first-touch and one due follow-up per fire — see `channels/heartbeat.md`. Bounded by design: even if the queue is huge, the agent never burst-sends.

### Secrets

- **AGENTMAIL_API_KEY** — required, sourced from the AgentMail dashboard at agentmail.to. The connector slot collects it during the dashboard setup flow. This is the ONLY connector slot.

The Slack bot is provisioned via OAuth in the dashboard, so no other secrets are required. The sales handoff email is a SOUL.md Configuration value (not a slot) — edit `## Configuration — edit before deploy` in `SOUL.md` before deploy. Prospects are queued via Slack ad-hoc; there is no deploy-time prospect list.

### External Setup

1. Sign up for AgentMail at agentmail.to and mint an API key (Settings → API Keys). Paste it into the `AGENTMAIL_API_KEY` slot during deploy. The agent creates its own dedicated outbound inbox the first time the heartbeat or webhook fires — you don't need to create one upfront.
2. Edit `SOUL.md` `## Configuration — edit before deploy`. Set the **Sales handoff email** to the inbox where interested replies should land. Adjust the **First-touch word cap** (default 80) or **Follow-up delay** (default 96 hours) if you want a different cadence.
3. Install the agent's Slack bot from the dashboard. Invite it to one channel where you want a window into the queue. Queueing prospects, status questions, pause/resume, removes, and question hand-offs all happen via @mention in that channel.
4. After deploy, copy the agent's webhook URL from the dashboard, then run this once from your terminal (with your AgentMail API key in the environment):

   ```sh
   PAGER=cat agentmail webhooks create \
     --url "<agent-webhook-url>" \
     --event message.received
   ```

   AgentMail starts pushing each new email to the agent in real time.
5. Queue your first prospect by @mentioning the bot in Slack:

   ```
   @gtm queue jane@acme.com hook: saw your post on distributed systems
   ```

   The agent restates the parsed prospect (`Jane / Acme`, derived from the email), waits for `👍`, then writes to MEMORY.md. The next heartbeat sends the first-touch.

## Customizing

- **Add prospects**: @mention the Slack bot. Single (`queue jane@acme.com hook: ...`), mass-with-shared-hook (`queue with hook: ...` then a list of emails), or paste one email per line. The agent stores them in MEMORY.md — no redeploy. Empty hooks are accepted but won't first-touch until the user adds one.
- **Remove prospects**: @mention the bot with `remove jane@acme.com`. The agent confirms, then deletes the row from MEMORY.md.
- **Change the follow-up cadence**: edit the **Follow-up delay** value in SOUL.md `## Configuration`. Bump to `168 hours` (7 days) for a longer wait, or down to `48 hours` for more aggressive cadence.
- **Change the email-body word cap**: edit the **First-touch word cap** value in SOUL.md `## Configuration`. Drop to `60` for a tighter voice, raise for a more conversational one.
- **Change the sales handoff email**: edit the **Sales handoff email** value in SOUL.md `## Configuration` and redeploy.
- **Tighten or loosen the OOO regex**: the *Quick Filter* in `channels/webhook.md` routes out-of-office replies as `ooo`. Add patterns for languages or templates your inbox sees regularly.
- **Pin a specific inbox**: if your AgentMail account already has multiple inboxes and you don't want auto-creation, set the `INBOX_ID` env var on the agent (or pre-populate `MEMORY.md` `inbox_id`). The first-fire bootstrap in `skills/agentmail/SKILL.md` will skip discovery.
- **Drop the heartbeat entirely**: if you'd rather queue every prospect and trigger every send manually via Slack, remove the `heartbeat` channel from `valet.yaml`, drop `channels/heartbeat.md`, and trim the *Heartbeat Workflow* section from `SOUL.md`. The webhook flow runs unchanged; the agent just won't send on its own.
- **Change the personality**: edit the *Personality* section of `SOUL.md`. The default voice is concise, no corporate-speak, one specific ask. The agent reads SOUL on every fire, so changes take effect on the next heartbeat or webhook.
