The connector name `agentmail` IS the CLI command on PATH. Never
invoke `npx agentmail-cli`, `agentmail-cli`, or any npm package
name — always just `agentmail`. The CLI is preconfigured with
`AGENTMAIL_API_KEY` from the connector slot, so you do not pass
`--api-key` at the command line.

─── Running commands non-interactively ──────────────────────────

Always invoke the CLI with this shape:

  PAGER=cat agentmail <root-flags> <resource> <subcommand> <subcommand-flags>

Three rules that bite if you get them wrong:

1. Disable the pager. When stdout is a TTY, the CLI may pipe
   output through `$PAGER` (default `less`) and hang waiting for
   keypresses. Prefix every invocation with `PAGER=cat` (or pipe
   to `| cat`).

2. Root flags go BEFORE the resource, subcommand flags go AFTER.
   `--format`, `--debug`, `--yes` / `-y` are root flags on
   `agentmail` itself — placing them after the subcommand makes
   them unknown flags.

3. Always request structured output. Pass `--format json` (single
   envelope) or `--format jsonl` (one record per line, easier to
   pipe). Never parse the human-readable default — it is for
   humans, not agents.

Confirm the exact subcommand surface with
`PAGER=cat agentmail --help` and `PAGER=cat agentmail <resource>
--help` on first use, then cache the resolved shape.

─── Resources you actually use ──────────────────────────────────

  inboxes        List, create, and read inboxes.
  threads        List threads in an inbox; read a single thread.
  messages       Send (NEW thread), reply (in-thread), forward,
                 list, read, mark read.
  webhooks       List, create, and delete webhook subscriptions.

─── First-fire bootstrap ────────────────────────────────────────

On the first webhook or heartbeat fire after deploy (no
`inbox_id` in `MEMORY.md`):

1. List inboxes:

     PAGER=cat agentmail --format json inboxes list

2. If exactly one inbox exists, use it. If none exist, create a
   dedicated outbound inbox:

     PAGER=cat agentmail --format json inboxes create \
       --display-name "GTM agent"

   The CLI returns an inbox with `inbox_id` and `email`. Cache
   both into `MEMORY.md`.

3. If multiple inboxes exist, prefer the one whose username
   contains `outreach`, `gtm`, or `sales`; otherwise pick the
   first returned and cache it. The user can override by
   deleting the `inbox_id` line in MEMORY and re-firing.

─── Sending a first-touch (NEW thread to a prospect) ────────────

The first-touch is a brand-new thread — there's no prior
message to reply to. Use `messages send` (NOT `messages reply`):

  PAGER=cat agentmail --format json messages send \
    --inbox $INBOX_ID \
    --to $PROSPECT_EMAIL \
    --subject "$SUBJECT" \
    --text "$BODY"

The CLI returns the sent message with a fresh `thread_id` and
`message_id`. Cache `thread_id` in MEMORY.md so the follow-up
and any inbound reply can be matched by it.

Subject-line hint: derive a short, lowercase subject from the
prospect's hook (60 chars max). Example:

  hook="Acme just announced a Series B and is hiring 5 sales reps"
  subject="quick note on Acme's Series B + 5 reps"

Never use generic subjects like "checking in" or "quick
question" — they tank open rates.

─── Sending a follow-up (in-thread reply on the existing thread) ─

Use `messages reply` to keep the follow-up in the original
thread. The cached `thread_id` is from MEMORY.md; the
`message_id` you reply to is the agent's own first-touch (look
it up via `threads get` and pick the most recent outbound
message in the thread):

  PAGER=cat agentmail --format json threads get \
    --inbox $INBOX_ID \
    --id $THREAD_ID

  # ... pick the latest outbound (from == $INBOX_EMAIL) message,
  # call it $LAST_OUTBOUND_MSG_ID

  PAGER=cat agentmail --format json messages reply \
    --inbox $INBOX_ID \
    --id $LAST_OUTBOUND_MSG_ID \
    --text "$FOLLOWUP_BODY"

Do NOT use `messages send` for follow-ups — that creates a new
thread and breaks subject-line continuity in the prospect's
inbox.

─── Reading an inbound reply (the webhook payload) ──────────────

The webhook payload includes the message id and thread id of
the inbound. Fetch the full thread so you have the full
back-and-forth:

  PAGER=cat agentmail --format json threads get \
    --inbox $INBOX_ID \
    --id $THREAD_ID

Pick the latest inbound message (`from` ≠ inbox email) — that's
the one the prospect just sent. Strip quoted-reply blocks (lines
prefixed with `>`) and signature blocks before classifying.

─── Forwarding an interested reply to the sales hand-off ────────

When the classifier marks a reply `interested`, forward the
original inbound to `SALES_HANDOFF_EMAIL` with a short cover
line. Use `messages forward`:

  PAGER=cat agentmail --format json messages forward \
    --inbox $INBOX_ID \
    --id $INBOUND_MESSAGE_ID \
    --to $SALES_HANDOFF_EMAIL \
    --text "$COVER_NOTE"

Cover-note shape (keep it tight, 3-4 lines):

  [INTERESTED LEAD]

  Prospect: <first_name> at <company> (<email>).
  They said: <one-line summary of the reply>.

  Original reply quoted below.

CRITICAL: Never invent a salesperson's name in the cover note.
Refer to "our team" or "our sales team" generically. Naming a
specific person risks hallucinating someone who isn't on the
sales rotation.

The agent does NOT also reply to the prospect on the agent's
behalf when forwarding — sales owns the warm conversation. The
prospect will get a real human reply from the sales team.

─── Marking the inbound read ────────────────────────────────────

After routing an inbound (interested forward, not_interested
update, ooo update, question Slack post), mark the message
read so duplicate webhook fires don't re-trigger the flow:

  PAGER=cat agentmail messages update \
    --inbox $INBOX_ID \
    --id $INBOUND_MESSAGE_ID \
    --remove-label unread \
    --add-label <interested|not_interested|ooo|question>

The label captures the classification for Slack queries that
ask "what got classified as X today".

─── Subscribing AgentMail webhooks to the agent ─────────────────

Once after deploy, the user (or the agent on first run) registers
a webhook so AgentMail starts pushing each new email:

  PAGER=cat agentmail webhooks create \
    --url "$AGENT_WEBHOOK_URL" \
    --event message.received

The agent webhook URL is shown in the dashboard after deploy.

─── Hygiene ─────────────────────────────────────────────────────

- Never call any send / reply / forward subcommand on a Slack
  *manual send* request without an explicit in-thread `👍` or
  "send" from the user. The webhook + heartbeat workflows are
  the only paths that send without a Slack confirm — and
  that's because they're acting on the queue you set up at
  deploy time (the CSV) and on inbound replies on threads the
  agent already started.
- Always pass `--format json` or `--format jsonl` for parseable
  output.
- Cache the resolved inbox id and email in `MEMORY.md` so
  subsequent fires skip discovery.
- Mark inbound messages read after routing so duplicate
  webhooks de-duplicate cleanly.
- Use `messages send` for first-touches (NEW thread). Use
  `messages reply` for follow-ups (in-thread). Use
  `messages forward` for the sales hand-off. Confusing the
  three is the easiest way to make the agent look broken.
- Redact obvious PII when re-posting reply contents to a public
  Slack channel (mask the prospect's address as
  `j***@example.com`). Full address is fine in a DM with the
  install user.
- Never echo the AgentMail API key in any output, log, or reply.
