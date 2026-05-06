# AgentMail Webhook (`message.received`)

The webhook payload is appended directly after these instructions
in the user message. Parse it inline — do not refetch the message
via the API. The payload is a JSON object with at least
`event_type: "message.received"` and `message: { ... }`.

## Quick Filter — Exit Early If Not Relevant

Before doing anything else, check whether this event is worth
acting on. **Stop immediately and take no action** if ANY of
these are true:

- `event_type` is anything other than `message.received`.
- `message.from` matches the agent's own inbox address (echo /
  loop guard — sent mail occasionally re-fires).
- The message has an out-of-office indicator (the `auto-replied`
  header, an `Auto-Submitted: auto-replied` value, or a body
  matching the OOO regex below). Route as `ooo` instead of
  ignoring (so MEMORY.md captures the pause).
- The message is a delivery-failure bounce (`mailer-daemon@`,
  `postmaster@`, or `Subject: Undelivered Mail Returned to
  Sender`). Same: route as `ooo`.
- The body, after stripping signature and quoted-reply blocks,
  is empty.
- The thread cannot be matched to a tracked prospect in
  `MEMORY.md` `prospects` (look up by `message.thread_id`). The
  agent only handles replies on threads it started — if a
  human accidentally hits the inbox, mark the message read with
  an `unknown` label and stop.
- The latest message in the thread (after this one is appended)
  is from the agent (this webhook is stale — a newer reply
  already went out).

If you are unsure whether the message is relevant, err on the
side of NOT replying. It's better to miss one and let the user
@mention "what's pending" later than to send an off-tone reply.

OOO regex (case-insensitive, match anywhere in the body):
`out of (the )?office|on vacation|away from email|out until|annual leave|parental leave`.

## Steps

1. Apply the Quick Filter. If the message fails any check, stop.
2. Resolve the inbox: read `MEMORY.md` `inbox_id`. If unset, run
   the agentmail discovery flow (see `skills/agentmail/SKILL.md`)
   and cache.
3. Match the inbound to a prospect. The thread the prospect was
   first emailed on is in `MEMORY.md` `prospects[email].thread_id`
   — look up by `message.thread_id`. If no match, mark read with
   label `unknown` and stop.
4. Fetch the full thread via `agentmail threads get` so you have
   the complete back-and-forth. Strip quoted-reply blocks and
   signatures from each message.
5. Classify the latest inbound (per the SOUL Webhook Workflow
   Phase 3): one of `interested`, `not_interested`, `ooo`,
   `question`. When the reply mixes positive interest AND a
   question, default to `interested`.
6. Route per the SOUL Webhook Workflow Phase 4:
   - `interested` → forward to `SALES_HANDOFF_EMAIL` with a
     brief cover line. Do NOT reply to the prospect.
   - `not_interested` → update MEMORY.md, no send.
   - `ooo` → update MEMORY.md, no send.
   - `question` → post in Slack so a human handles it, then
     wait for the user's draft + explicit confirmation before
     sending anything.
7. Mark the inbound message read so duplicate webhook fires
   don't re-trigger the flow.
8. Update `MEMORY.md` `prospects[email]` with the new status
   and `last_action`.

## What NOT to do

- Do not refetch the message body — it's already in the payload.
- Do not list the entire inbox; only the thread for this event.
- Do not auto-pitch a response to a `question` — that's the
  Slack hand-off path, not an automated reply.
- Do not reply to declines or OOO replies.
- Do not send a status update to Slack on every webhook fire.
  Slack visibility is on-demand: the user @mentions "what
  replied today?" when they want to see.
- Do not retry on transient failures inside the webhook handler.
  The next inbound (or the user's "what replied today?" check)
  is the recovery.
- Do not echo the AgentMail API key, the webhook URL, or any
  other secret in a Slack post or email reply.
