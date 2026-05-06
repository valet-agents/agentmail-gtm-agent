# Slack Message Received

The Slack event payload is appended directly after these
instructions in the user message. Parse it inline — do not
fetch, list, or search for the payload elsewhere. Do NOT use
tools to read the payload.

Slack is the agent's primary prospect-queueing interface. The
operator @mentions the bot to add a prospect, list the queue,
pause sends, or remove a row. The canonical store is MEMORY.md
`prospects` — the heartbeat sweeps it on the next fire.

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
3. Classify the request as one of these modes (per the SOUL
   Interactive Workflow):
   - **Queue request** — the primary mode. Three input shapes:
     - **Single:** *"queue jane@acme.com hook: saw your post on
       distributed systems"* — email plus hook.
     - **Mass with shared hook:** *"queue with hook: <hook
       text>"* followed by a bulleted or newline-separated list
       of emails.
     - **Mass paste:** one email per line with no hook prefix
       — every prospect goes in with an empty hook (the agent
       will refuse to first-touch any row whose hook is empty;
       the user adds hooks later via @mention or by editing
       MEMORY.md).
   - **Status question** about the queue / sends / replies —
     *"who's queued?"*, *"who replied today?"*, *"what's due
     for follow-up?"*, *"how many sent this week?"*, *"what
     did Acme say back?"*.
   - **Pause / resume** — *"pause sends"* / *"resume sends"*.
     Toggles the global `paused` flag in MEMORY.md.
   - **Remove** — *"remove jane@acme.com"*. Confirm-then-delete
     the row from MEMORY.md `prospects`.
   - **Question hand-off draft** — the user is replying to an
     agent post that started with *"[QUESTION] from <name>..."*
     with draft answer text. The agent restates and waits for
     `👍` / "send".
   - **Confirmation in a thread you started** — `👍`, "yes",
     "send", "queue", "pause", "resume", "remove", "no", "skip"
     — route to the pending two-step confirm flow for that
     thread.
4. For status questions, read `MEMORY.md` `prospects` and
   format the reply as Slack `mrkdwn`, scannable bullets,
   under 1,500 chars.
5. For destructive actions (queueing, pausing, removing,
   sending a hand-off reply), restate the proposed change
   in-thread and wait for an explicit `👍` / "yes" / "send" /
   "apply" before acting. After acting, post a one-line
   confirmation (*"Queued 3 prospects."* / *"Paused."* /
   *"Removed."* / *"Sent."*).
6. Post once, in this thread, via a Slack tool call.

## Queue request — preprocessing

The agent treats the queue request as the most common mode.
Extract prospects from the message, derive defaults, restate,
wait for confirmation, then write to MEMORY.md `prospects`.

**Default extraction (do this BEFORE asking the user):**

- `first_name` from the email username: capitalize the segment
  before the first `.` or `_`.
  - `jane@acme.com` → `Jane`
  - `jane.smith@acme.com` → `Jane`
  - `j_smith@acme.com` → `J`
- `company` from the domain: capitalize the domain root, strip
  the TLD and any leading `mail.` / `www.` prefix.
  - `acme.com` → `Acme`
  - `mail.acme.co` → `Acme`
- `hook` from the parsed text after `hook:` (single mode) or
  the shared `hook:` prefix (mass-with-shared-hook). For mass
  paste with no hook, leave the field empty.

**Override with `key=value` pairs.** The user can override any
default by writing `first_name=Jane`, `company=Acme`, or
`hook='...'` after the email.

**Restate every prospect being queued** in the confirmation
message. For mass queues, list every row so the user can spot
parsing mistakes before confirming.

## Disambiguation cues

- *"queue <email> hook: ..."* — single queue. Parse, restate,
  confirm.
- *"queue with hook: ..."* + email list — mass queue with
  shared hook. Apply the hook to every parsed email.
- A bare list of emails (newlines or bullets) — mass paste.
  Hooks are empty; warn the user the agent won't first-touch
  rows without hooks.
- *"who's queued?"* — list MEMORY.md `prospects` with
  `status: queued`. Subject + first_name + company.
- *"who replied today?"* — filter MEMORY.md `prospects` by
  `last_action` in the past 24h and `status` starts with
  `replied_`.
- *"what's due for follow-up?"* — list MEMORY.md `prospects`
  with `status: sent` and `sent_at` older than the SOUL.md
  Configuration **Follow-up delay** value.
- *"remove <email>"* — confirm-then-delete from MEMORY.md.
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
  `messages forward` on a manual-send request without an
  explicit two-step confirmation in Slack. Sending email on
  the user's behalf is irreversible. (The webhook + heartbeat
  workflows are the only paths that send without a Slack
  confirm — and that's because they're acting on the queue
  the user already populated and on inbound replies on threads
  the agent already started.)
- Do not echo the AgentMail API key or a prospect's full email
  in a public channel. In a public channel, redact as
  `j***@example.com`. In a DM with the install user, the full
  address is fine.
- Do not write to MEMORY.md `prospects` without an explicit
  user confirmation in-thread. Queue requests are destructive
  by definition — they queue real outbound email.
