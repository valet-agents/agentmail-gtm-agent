# Heartbeat — Hourly Sweep

The heartbeat fires once per hour. Each fire does a small,
bounded amount of work — one queued first-touch and one due
follow-up at most. The next hour picks up the next ones. This
keeps outbound predictable and avoids thundering-herd sends
when several prospects get queued together.

Hourly resolution is fine: outreach windows aren't
minute-sensitive, and a one-hour latency between "queue this
prospect" and "first-touch goes out" is well below human
response cadence.

## Quick Filter — Skip This Fire If Not Useful

Before doing anything, **stop immediately and take no action**
if ANY of these are true:

- `MEMORY.md` `paused: true` — the user paused sends in Slack.
  Don't send anything until they resume.
- The agent has no inbox yet (`MEMORY.md` `inbox_id` unset)
  AND the AgentMail bootstrap fails (no API key, network
  error). Try discovery once via the agentmail skill; if it
  fails, log and stop. The next fire retries.
- MEMORY.md `prospects` is empty. Nothing to do — wait for the
  user to queue a prospect from Slack.

## Steps

1. **Bootstrap once.** If `MEMORY.md` `inbox_id` is unset, run
   `PAGER=cat agentmail --format json inboxes list`. If exactly
   one inbox exists, cache it. If none exist, create a
   dedicated outbound inbox via `inboxes create --display-name
   "GTM agent"` and cache the returned `inbox_id` and `email`.

2. **Send one queued first-touch.**
   - Scan MEMORY.md `prospects` for rows with `status: queued`.
   - Skip rows whose `hook` is empty (post a one-line Slack note
     in the channel the agent was last @mentioned in, asking
     the user to add a hook before the agent sends — then move
     on to the follow-up phase). Never first-touch with an
     empty hook.
   - Pick the first eligible queued prospect. Compose the
     personalized first-touch (cap at the **First-touch word
     cap** value in SOUL.md Configuration, one ask, no fluff —
     see SOUL Personality).
   - Send via the agentmail skill's
     `agentmail messages send` shape. Capture the returned
     `thread_id`.
   - Update MEMORY.md `prospects[email]` to
     `status: sent, sent_at: <iso>, thread_id: <thr_xxx>`.
   - Stop after one. Don't loop the queue.

3. **Send one follow-up due.**
   - Scan MEMORY.md `prospects` for rows with `status: sent`
     and `sent_at` older than the **Follow-up delay** value in
     SOUL.md Configuration (default 96h).
   - Pick the first one. Compose the follow-up (shorter than
     the first touch, references the first email lightly,
     adds a tiny new value).
   - Send via `agentmail messages reply` (in-thread, not a new
     send) using the cached `thread_id`.
   - Update MEMORY.md `prospects[email]` to
     `status: followed_up, last_action: <iso>`.
   - Stop after one.

4. **Do not post to Slack on every fire.** Slack visibility is
   on-demand. The user @mentions "what's queued?" or "who's
   due?" when they want to see the queue.

## Cursor Logic

The heartbeat doesn't keep an explicit cursor — MEMORY.md
`prospects[email].status` IS the cursor:

- `queued` → eligible for first-touch (skip if hook is empty).
- `sent` with `sent_at` older than the **Follow-up delay** value
  → eligible for follow-up.
- `followed_up`, `replied_*`, `q_and_a` → terminal, skip.
- `no_reply` → terminal (set manually if the user wants to
  retire a row without replying).

If two heartbeats fire close together (clock skew, retries),
the status update from fire N is visible to fire N+1 — so the
same prospect can't get two first-touches.

## What NOT to do

- Do not blast the entire queue in one fire. One first-touch +
  one follow-up per fire, max.
- Do not auto-resume after a pause. The pause is intentional;
  let the user lift it.
- Do not send a follow-up on a prospect that already replied —
  check MEMORY.md `status` before composing.
- Do not subject-line the follow-up with a fresh hook — it's an
  in-thread `Re:` reply. The thread carries the subject.
- Do not echo the AgentMail API key or the webhook URL in
  any log or message.
