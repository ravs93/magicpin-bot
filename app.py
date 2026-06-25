from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

category_contexts = {}
merchant_contexts = {}
customer_contexts = {}
trigger_contexts = {}

contexts_loaded = {
    "category": 0,
    "merchant": 0,
    "customer": 0,
    "trigger": 0
}

@app.get("/")
def home():
    return {"status": "running"}

@app.get("/v1/healthz")
def healthz():
    return {
        "status": "ok",
        "uptime_seconds": 0,
        "contexts_loaded": contexts_loaded
    }

@app.get("/v1/metadata")
def metadata():
    return {
        "team_name": "Ravinder Singh",
        "team_members": ["Ravinder Singh"],
        "model": "gpt-4o",
        "approach": "context storage + trigger based message generation",
        "contact_email": "rs536091@gmail.com",
        "version": "1.0.0"
    }

@app.post("/v1/context")
def receive_context(data: dict):

    scope = data.get("scope")
    context_id = data.get("context_id")
    version = data.get("version", 1)
    payload = data.get("payload", {})

    if scope not in ["category", "merchant", "customer", "trigger"]:
        return {
            "accepted": False,
            "reason": "invalid_scope",
            "details": f"Unknown scope: {scope}"
        }

    if not context_id:
        return {
            "accepted": False,
            "reason": "missing_context_id"
        }

    store_map = {
        "category": category_contexts,
        "merchant": merchant_contexts,
        "customer": customer_contexts,
        "trigger": trigger_contexts
    }

    store = store_map[scope]
    existing = store.get(context_id)

    if existing and existing.get("_version", 0) > version:
        return {
            "accepted": False,
            "reason": "stale_version",
            "current_version": existing.get("_version", 0)
        }

    is_new = context_id not in store

    payload["_version"] = version
    store[context_id] = payload

    if is_new:
        contexts_loaded[scope] += 1

    return {
        "accepted": True,
        "ack_id": f"ack_{context_id}_v{version}",
        "stored_at": datetime.utcnow().isoformat() + "Z"
    }

@app.post("/v1/reply")
def reply(data: dict):

    return {
        "action": "send",
        "body": "Thanks for your response. I can help with the next step. Would you like me to continue?",
        "cta": "open_ended",
        "rationale": "Basic reply handler for merchant/customer responses"
    }

@app.post("/v1/tick")
def tick(data: dict):

    available_triggers = data.get("available_triggers", [])
    actions = []

    for trigger_id in available_triggers:
        trigger = trigger_contexts.get(trigger_id)

        if not trigger:
            continue

        merchant_id = trigger.get("merchant_id")
        customer_id = trigger.get("customer_id")
        kind = trigger.get("kind", "update")

        merchant = merchant_contexts.get(merchant_id, {})
        identity = merchant.get("identity", {})
        merchant_name = identity.get("name", "there")

        if kind == "research_digest":
            body = f"Hi {merchant_name}, there's new research relevant to your business. Would you like a quick summary?"

        elif kind == "perf_spike":
            body = f"Great news {merchant_name}! Your business performance has improved recently. Would you like to see what's driving it?"

        elif kind == "perf_dip":
            body = f"Hi {merchant_name}, I noticed a drop in your recent performance. I have a few suggestions that may help."

        elif kind == "recall_due":
            body = f"Hi {merchant_name}, one of your customers is due for a follow-up. Shall I prepare a reminder?"

        elif kind == "festival_upcoming":
            body = f"Hi {merchant_name}, an upcoming festival is a good opportunity to promote your business. Want campaign ideas?"

        else:
            body = f"Hi {merchant_name}, I noticed a {kind} update for your business. Would you like me to help with the next step?"

        actions.append({
            "conversation_id": f"conv_{merchant_id}_{trigger_id}",
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": "vera",
            "trigger_id": trigger_id,
            "template_name": "vera_basic_update_v1",
            "template_params": [merchant_name, kind],
            "body": body,
            "cta": "open_ended",
            "suppression_key": trigger.get("suppression_key", trigger_id),
            "rationale": f"Generated from trigger kind {kind} for merchant {merchant_id}"
        })

    return {
        "actions": actions
    }
