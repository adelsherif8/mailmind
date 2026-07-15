"""MailMind — AI email triage & draft engine. API + dashboard."""

import os
import json
import base64

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app import llm, tracing
from app.graph import process

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(_HERE, "templates"))

INBOX = json.load(open(os.path.join(_HERE, "data", "inbox.json")))
try:
    PROCESSED = json.load(open(os.path.join(_HERE, "data", "inbox_processed.json")))
except FileNotFoundError:
    PROCESSED = []
try:
    METRICS = json.load(open(os.path.join(_HERE, "data", "metrics.json")))
except FileNotFoundError:
    METRICS = None

SENT: dict[str, dict] = {}

app = FastAPI(title="MailMind")


def _make_eml(to_name: str, to_email: str, subject: str, body: str) -> str:
    subj = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    raw = (f"To: {to_name} <{to_email}>\r\nSubject: {subj}\r\n"
           f"Content-Type: text/plain; charset=utf-8\r\n\r\n{body}")
    return "data:message/rfc822;base64," + base64.b64encode(raw.encode()).decode()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "mode": llm.mode(), "langfuse": tracing.configured(),
        "inbox": PROCESSED or INBOX, "metrics": METRICS,
    })


@app.post("/regenerate")
async def regenerate(request: Request):
    body = await request.json()
    eid, tone = body.get("id"), body.get("tone", "professional")
    email = next((e for e in INBOX if e["id"] == eid), None)
    if not email:
        return JSONResponse({"error": "unknown email"}, status_code=404)
    if not llm.live():
        return JSONResponse({"error": "Regenerate needs the live API key."}, status_code=400)
    s = process(email, tone=tone)
    trace_url = tracing.trace_email(email, s)
    return {"id": eid, "tone": tone, "draft": s["draft"], "urgency": s["urgency"],
            "intent": s["intent"], "confidence": round(s["confidence"], 2),
            "tone_ok": s.get("tone_ok", True), "critic_note": s.get("critic_note", ""),
            "trace": s["trace"], "cost": s["usage"]["cost"], "ms": s["ms"], "trace_url": trace_url}


@app.post("/send")
async def send(request: Request):
    body = await request.json()
    eid = body.get("id")
    email = next((e for e in INBOX if e["id"] == eid), None)
    draft = body.get("draft", "")
    if not email or not draft:
        return JSONResponse({"error": "bad request"}, status_code=400)
    SENT[eid] = {"to": email["email"]}
    eml = _make_eml(email["from"], email["email"], email["subject"], draft)
    return {"sent": True, "id": eid, "eml_url": eml}


@app.get("/metrics")
def metrics():
    return METRICS or JSONResponse({"error": "no metrics"}, status_code=404)


@app.get("/health")
def health():
    return {"ok": True, "mode": llm.mode(), "langfuse": tracing.configured()}
