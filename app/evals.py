"""Batch-process the demo inbox once with real GPT-4o -> cached processed inbox
(instant, cheap dashboard on Vercel) + measured metrics: classification agreement
vs. human labels, avg processing time, and cost per email."""

import os
import json
from app.graph import process
from app import llm

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(save: bool = True) -> dict:
    inbox = json.load(open(os.path.join(_HERE, "data", "inbox.json")))
    processed, urg_hit, int_hit = [], 0, 0
    total_ms, total_cost, rewrites = 0, 0.0, 0
    for e in inbox:
        s = process(e, tone="professional")
        urg_hit += 1 if s["urgency"] == e.get("expected_urgency") else 0
        int_hit += 1 if s["intent"] == e.get("expected_intent") else 0
        total_ms += s["ms"]; total_cost += s["usage"]["cost"]
        rewrites += 0 if s.get("tone_ok", True) else 1
        processed.append({
            "id": e["id"], "from": e["from"], "email": e["email"],
            "subject": e["subject"], "body": e["body"],
            "urgency": s["urgency"], "intent": s["intent"],
            "confidence": round(s["confidence"], 2), "reason": s["reason"],
            "draft": s["draft"], "tone_ok": s.get("tone_ok", True),
            "critic_note": s.get("critic_note", ""),
            "trace": s["trace"], "ms": s["ms"], "cost": s["usage"]["cost"],
        })
    n = len(inbox)
    metrics = {
        "mode": llm.mode(), "emails": n,
        "urgency_accuracy": round(urg_hit / n, 3),
        "intent_accuracy": round(int_hit / n, 3),
        "avg_ms_per_email": round(total_ms / n),
        "avg_cost_per_email": round(total_cost / n, 5),
        "cost_per_1000": round(total_cost / n * 1000, 2),
        "tone_rewrites": rewrites,
    }
    if save:
        json.dump(processed, open(os.path.join(_HERE, "data", "inbox_processed.json"), "w"), indent=2)
        json.dump(metrics, open(os.path.join(_HERE, "data", "metrics.json"), "w"), indent=2)
    return metrics


if __name__ == "__main__":
    m = run()
    print(f"mode={m['mode']} emails={m['emails']}")
    print(f"urgency accuracy: {m['urgency_accuracy']*100:.0f}%  intent accuracy: {m['intent_accuracy']*100:.0f}%")
    print(f"avg {m['avg_ms_per_email']} ms/email  ${m['avg_cost_per_email']:.4f}/email  (${m['cost_per_1000']}/1000)")
    print(f"tone rewrites: {m['tone_rewrites']}/{m['emails']}")
