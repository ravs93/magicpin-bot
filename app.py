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

    return {
        "actions": []
    }
