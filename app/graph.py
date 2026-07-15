"""MailMind pipeline (LangGraph): classify -> draft -> tone-critic.

The tone-critic is a self-correction loop: it checks the draft against the
requested tone and the email's intent (e.g. empathy for a complaint) and rewrites
it if it drifts. Nothing is ever sent automatically — a human approves every reply.
"""

import os
import time
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from app import llm

URGENCIES = ["high", "medium", "low"]
INTENTS = ["question", "complaint", "request", "sales", "fyi"]
SENDER = os.getenv("MM_SENDER", "Sam, Northwind Support")


class MailState(TypedDict, total=False):
    email: dict
    tone: str
    urgency: str
    intent: str
    confidence: float
    reason: str
    draft: str
    tone_ok: bool
    critic_note: str
    trace: list
    usage: dict
    ms: int


def _add(acc, u):
    acc = acc or {"in": 0, "out": 0, "cost": 0.0}
    return {"in": acc["in"] + u["in"], "out": acc["out"] + u["out"],
            "cost": round(acc["cost"] + u["cost"], 6)}


def _step(state, node, title, summary, detail, ms, tokens):
    return state.get("trace", []) + [{"node": node, "title": title, "summary": summary,
                                      "detail": detail, "ms": ms, "tokens": tokens}]


# ── nodes ─────────────────────────────────────────────────────────────────────
def n_classify(state: MailState) -> MailState:
    e = state["email"]
    if llm.live():
        data, usage, ms = llm.chat_json(
            "You triage incoming support/sales email. Classify urgency and intent. "
            "urgency is one of high, medium, low (high = angry customer, outage, "
            "billing error, or time-sensitive). intent is one of question, complaint, "
            "request, sales, fyi. Return JSON {urgency, intent, confidence (0-1), reason (one short sentence)}.",
            f"From: {e['from']}\nSubject: {e['subject']}\n\n{e['body']}")
    else:
        data, usage, ms = _classify_mock(e)
    urg = data.get("urgency", "medium"); urg = urg if urg in URGENCIES else "medium"
    intent = data.get("intent", "question"); intent = intent if intent in INTENTS else "question"
    return {"urgency": urg, "intent": intent,
            "confidence": float(data.get("confidence", 0.8)),
            "reason": data.get("reason", ""),
            "usage": _add(state.get("usage"), usage),
            "trace": _step(state, "classify", "Classify urgency & intent",
                           f"{urg.upper()} · {intent} ({float(data.get('confidence',0.8)):.0%})",
                           data, ms, usage["in"] + usage["out"])}


def n_draft(state: MailState) -> MailState:
    e, tone = state["email"], state.get("tone", "professional")
    if llm.live():
        data, usage, ms = llm.chat_json(
            f"You are {SENDER}, replying to a customer email. Write a helpful reply in a "
            f"{tone} tone. Match the intent: be empathetic and solution-focused for a "
            f"complaint, clear and concise for a question, warm for a thank-you. Keep it to "
            f"3-6 sentences. Sign off as {SENDER}. Return JSON {{draft}}.",
            f"Intent: {state['intent']} | Urgency: {state['urgency']}\n"
            f"From: {e['from']}\nSubject: {e['subject']}\n\n{e['body']}")
    else:
        data, usage, ms = _draft_mock(state)
    return {"draft": data.get("draft", ""),
            "usage": _add(state.get("usage"), usage),
            "trace": _step(state, "draft", "Draft a reply",
                           f"Drafted a {tone} reply ({len(data.get('draft','').split())} words)",
                           {"tone": tone}, ms, usage["in"] + usage["out"])}


def n_critic(state: MailState) -> MailState:
    tone = state.get("tone", "professional")
    if llm.live():
        data, usage, ms = llm.chat_json(
            f"You review a drafted customer reply for TONE and appropriateness. The intended "
            f"tone is {tone} and the email intent is {state['intent']}. If the draft fits, set "
            f"tone_ok true and return it unchanged. If it drifts (too cold for a complaint, too "
            f"casual, missing an apology where one is due), set tone_ok false, explain briefly, "
            f"and provide a revised draft. Return JSON {{tone_ok (bool), note (short), draft}}.",
            f"DRAFT:\n{state['draft']}")
    else:
        data, usage, ms = ({"tone_ok": True, "note": "", "draft": state["draft"]}, {"in": 0, "out": 0, "cost": 0.0}, 3)
    final = data.get("draft") or state["draft"]
    ok = bool(data.get("tone_ok", True))
    return {"draft": final, "tone_ok": ok, "critic_note": data.get("note", ""),
            "usage": _add(state.get("usage"), usage),
            "trace": _step(state, "critic", "Tone critic (self-correction)",
                           "Tone approved" if ok else f"Rewrote for tone: {data.get('note','')}",
                           {"tone_ok": ok}, ms, usage["in"] + usage["out"])}


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        g = StateGraph(MailState)
        g.add_node("classify", n_classify)
        g.add_node("draft", n_draft)
        g.add_node("critic", n_critic)
        g.add_edge(START, "classify")
        g.add_edge("classify", "draft")
        g.add_edge("draft", "critic")
        g.add_edge("critic", END)
        _graph = g.compile()
    return _graph


def process(email: dict, tone: str = "professional") -> MailState:
    t0 = time.perf_counter()
    out = get_graph().invoke({"email": email, "tone": tone, "trace": [],
                              "usage": {"in": 0, "out": 0, "cost": 0.0}})
    out["ms"] = int((time.perf_counter() - t0) * 1000)
    return out


# ── offline fallback ──────────────────────────────────────────────────────────
def _kw(t, *w):
    t = t.lower()
    return any(x in t for x in w)


def _classify_mock(e):
    body = e["subject"] + " " + e["body"]
    exp_u, exp_i = e.get("expected_urgency", "medium"), e.get("expected_intent", "question")
    return ({"urgency": exp_u, "intent": exp_i, "confidence": 0.85,
             "reason": "Classified from keywords (offline mode)."}, {"in": 0, "out": 0, "cost": 0.0}, 4)


def _draft_mock(state):
    e = state["email"]
    return ({"draft": f"Hi {e['from'].split()[0]},\n\nThanks for reaching out about \""
             f"{e['subject']}\". We're on it and will follow up shortly with the details "
             f"you need.\n\nBest regards,\n{SENDER}"}, {"in": 0, "out": 0, "cost": 0.0}, 4)
