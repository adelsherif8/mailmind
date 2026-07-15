"""Langfuse tracing for the classify -> draft -> critic pipeline."""
import os

_lf = None


def configured() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def _client():
    global _lf
    if _lf is None:
        from langfuse import Langfuse
        _lf = Langfuse()
    return _lf


def trace_email(email: dict, state: dict) -> str | None:
    if not configured():
        return None
    try:
        lf = _client()
        with lf.start_as_current_observation(
            as_type="span", name="email-triage",
            input={"from": email.get("from"), "subject": email.get("subject")},
        ) as root:
            for st in state.get("trace", []):
                with lf.start_as_current_observation(
                        as_type="generation", name=st["node"],
                        model=os.getenv("MM_MODEL", "gpt-4o"),
                        input={"summary": st["summary"]}) as g:
                    g.update(output=st.get("detail"),
                             usage_details={"total": st.get("tokens", 0)})
            root.update(output={"urgency": state.get("urgency"), "intent": state.get("intent"),
                                "tone_ok": state.get("tone_ok"), "cost": state.get("usage", {}).get("cost")})
            url = lf.get_trace_url()
        lf.flush()
        return url
    except Exception:
        return None
