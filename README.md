# MailMind — AI Email Triage & Draft Engine

MailMind reads every incoming email, **classifies urgency and intent**, and
**drafts a reply in your tone** — you review, edit, and approve. Inbox zero as an
agentic workflow, with a human in the loop on every send.

**Live demo:** _(deployed on Vercel)_

## Pipeline (LangGraph)
```
incoming email → Classifier (urgency + intent) → Drafter (your tone)
   → Tone-critic (self-check, rewrites if it drifts) → Human approves → Send
```
- **Classifier** — urgency (high / medium / low) + intent (question / complaint /
  request / sales / fyi), with a confidence score and a one-line reason.
- **Drafter** — a reply matching the requested tone (professional / friendly /
  concise) and the email's intent (empathetic for a complaint, warm for a thank-you).
- **Tone-critic** — a self-correction loop that rewrites the draft if the tone drifts.
- **Human-in-the-loop** — nothing sends automatically; a person approves every reply.
- **Traced** — every step (classify, draft, critic) traced in Langfuse.

## Measured (12-email labelled set, GPT-4o)
- **83%** urgency accuracy · **83%** intent accuracy vs. human labels
- **~$3.77 / 1,000 emails** · ~5s per email

## Modes
- **GPT-4o live** — set `OPENAI_API_KEY` (+ `LANGFUSE_*`). Real classification, drafting, tone-critic.
- **Cached demo** — the inbox ships pre-processed so the dashboard loads instantly; "Regenerate" and tone changes call the live model.

> Demo uses a synthetic inbox. A real **Gmail API (OAuth)** integration — reading the
> inbox and creating drafts — is the production path; the demo generates a downloadable
> `.eml` draft on approval so the full flow is demonstrable without account access.

## Stack
Python · FastAPI · LangGraph · GPT-4o · Langfuse

Built by **Adel Atya** — adelatya.vercel.app

---

Built by **Adel Atya**, AI engineer: AI voice agents, agentic systems and automation for businesses. [adelatya.com](https://adelatya.com)
