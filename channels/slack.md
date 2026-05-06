# Slack Message Received

The Slack event payload is appended directly after these
instructions in the user message. Parse it inline — do not
fetch, list, or search for the payload elsewhere. Do NOT use
tools to read the payload.

## Quick Filter — Exit Early If Not Relevant

Before doing anything else, check whether this message is worth
responding to. **Stop immediately and take no action** if ANY of
these are true:

- The message is from a bot (check for `bot_id` or
  `subtype: "bot_message"` in the payload).
- The message is from yourself.
- The message is a channel join/leave, topic change, pin, or
  any other system event (any non-empty `subtype` that isn't a
  real user message).
- You are not @mentioned and the message isn't in a thread you
  already replied in.
- The message body, after stripping your @mention, is empty,
  just a greeting, a thank-you, an emoji, or otherwise not a
  question or request.
- The message is clearly off-topic for this agent (no
  prospect / queue / follow-up / reply / outreach keywords,
  and not a confirmation in a thread you started).

If you are unsure whether the message is relevant, err on the
side of NOT responding.

## Scope

Extract `channel`, `ts`, `thread_ts`, `user`, and `text`. All
replies MUST go to this channel and thread. Do not read or act
on messages from other channels or threads.

## Steps

1. Apply the Quick Filter. If the message fails, stop here.
2. Strip the @mention token and whitespace from `text`.
3. Classify the request as one of four modes (per the SOUL
   Interactive Workflow):
   - **Status question** about the queue / sends / replies —
     *"who's queued?"*, *"who replied today?"*, *"what's due
     for follow-up?"*, *"how many sent this week?"*, *"what
     did Acme say back?"*.
   - **One-off queue** — *"queue jane@acme.com first_name=Jane
     company=Acme hook='saw your talk on agent infra'"*. The
     agent appends a row to MEMORY.md `prospects` with
     `status: queued` so the next heartbeat picks it up.
   - **Pause / resume** — *"pause sends"* / *"resume sends"*.
     Toggles the global `paused` flag in MEMORY.md.
   - **Question hand-off draft** — the user is replying to an
     agent post that started with *"[QUESTION] from <name>..."*
     with draft answer text. The agent restates and waits for
     `👍` / "send".
   - **Confirmation in a thread you started** — `👍`, "yes",
     "send", "queue", "pause", "resume", "no", "skip" — route
     to the pending two-step confirm flow for that thread.
4. For status questions, run the smallest set of queries that
   answers it (read `MEMORY.md` `prospects` first; if a local
   `gtm_log.csv` exists, grep it for action history). Format
   the reply as Slack `mrkdwn`, scannable bullets, under
   1,500 chars.
5. For destructive actions (queueing, pausing, sending a
   hand-off reply), restate the proposed change in-thread and
   wait for an explicit `👍` / "yes" / "send" / "apply" before
   acting. After acting, post a one-line confirmation
   (*"Queued."* / *"Paused."* / *"Sent."*).
6. Post once, in this thread, via a Slack tool call.

## Disambiguation cues

- *"who's queued?"* — list MEMORY.md `prospects` with
  `status: queued`. Subject + first_name + company.
- *"who replied today?"* — filter MEMORY.md `prospects` by
  `last_action` in the past 24h and `status` starts with
  `replied_`.
- *"what's due for follow-up?"* — list MEMORY.md `prospects`
  with `status: sent` and `sent_at >= 96h ago`.
- *"queue <email> hook='...'"* — parse `key=value` pairs,
  restate, wait for confirmation.
- A bare `👍` or "send" in a thread the agent started with a
  *"[QUESTION] from..."* or *"Queueing..."* preamble — that's
  the second step of the two-step confirm. Execute the
  proposed action.
- A name in the message ("Acme", "Jane") — the agent finds the
  most recent prospect by company or first_name. If ambiguous,
  ask one clarifying question.

## What NOT to do

- Do not post in any channel other than the one this event
  came from.
- Do not DM users — one mention, one reply, in-place.
- Do not send a "looking into it…" ping before the real reply.
- Do not echo the user's @mention back. One mention → one
  substantive reply.
- Do not call `agentmail messages send`, `messages reply`, or
  `messages forward` without an explicit two-step confirmation
  in Slack. Sending email on the user's behalf is irreversible.
  (The webhook + heartbeat workflows are the only paths that
  send without a Slack confirm — and that's because they're
  acting on the queue you set up at deploy time.)
- Do not echo the AgentMail API key or a prospect's full email
  in a public channel. In a public channel, redact as
  `j***@example.com`. In a DM with the install user, the full
  address is fine.
