<p align="center">
  <img src="https://agentmail.to/favicon.ico" alt="AgentMail" height="64" />
</p>

# AgentMail GTM Agent

Drop a CSV of prospects. The agent sends a personalized first-touch, follows up once at 96 hours, classifies inbound replies, and forwards the interested ones to your sales inbox.

## Prerequisites
- An [AgentMail](https://agentmail.to) account (mint an API key in the dashboard)
- A list of prospects as CSV with columns `email, first_name, company, hook` — one-line specific hooks beat generic compliments
- A sales-team email address for warm hand-offs
- A Slack workspace where you can install the agent's bot and invite it to one channel
- The ability to subscribe an AgentMail webhook to a public URL (the agent's webhook URL is provisioned automatically — you'll paste it into one CLI command after deploy)

<table>
  <tr>
    <td><strong>CHANNELS</strong></td>
    <td><code>slack</code> · <code>webhook</code> · <code>heartbeat</code></td>
  </tr>
  <tr>
    <td><strong>CONNECTORS</strong></td>
    <td><code>agentmail</code></td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <br />
      <a href="https://valet.dev/deploy?from=github.com/valet-agents/agentmail-gtm-agent">
        <img src="https://raw.githubusercontent.com/valet-agents/agentmail-gtm-agent/main/.github/deploy-button.svg" alt="Deploy Agent →" height="40" />
      </a>
      <br /><br />
    </td>
  </tr>
</table>

## How it works

1. You paste your prospect CSV into the `PROSPECTS_CSV` slot at deploy time. The agent picks it up on the next hourly heartbeat.
2. The heartbeat sends one queued first-touch per fire — a personalized 80-word email opened with the prospect's hook, one specific ask, no fluff.
3. After 96 hours with no reply, the heartbeat sends a single follow-up in the same thread. Then silent.
4. AgentMail fires a webhook on every inbound reply. The agent classifies it as `interested`, `not_interested`, `ooo`, or `question`.
5. Interested replies are forwarded to your `SALES_HANDOFF_EMAIL` with a short cover note. Declines and OOO bounces are silenced. Open questions are posted in Slack so a human handles them.
6. Anytime, @mention the agent's Slack bot to ask who's queued, who replied today, who's due for follow-up, or to queue a one-off prospect.

## Credits

Ported from the original [AgentMail GTM Agent](https://github.com/agentmail-to/agentmail-gtm-agent) template by AgentMail. MIT-licensed.
