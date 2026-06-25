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
conversations = {}

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
        "model": "rule-based + contextual composer",
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
    conversation_id = data.get("conversation_id")

    if conversation_id not in conversations:
        conversations[conversation_id] = []

    conversations[conversation_id].append(data.get("message", ""))

    message = data.get("message", "").lower()

    if any(word in message for word in ["yes", "go ahead", "interested", "ok", "okay"]):
        return {
        "action": "send",
        "body": "Great! I'll prepare the next steps and guide you through the process.",
        "cta": "open_ended",
        "rationale": "Merchant accepted the suggestion."
    }

    elif any(word in message for word in ["no", "not interested", "stop"]):
        return {
        "action": "end",
        "rationale": "Merchant declined further engagement."
    }

    elif "thank you for contacting" in message:
        return {
        "action": "end",
        "rationale": "Detected WhatsApp auto-reply."
    }

    else:
        return {
        "action": "send",
        "body": "Thanks for your response. Could you tell me a little more so I can help you better?",
        "cta": "open_ended",
        "rationale": "Continuing the conversation."
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
        category = merchant.get("category_slug", "")
        city = identity.get("city", "")
        locality = identity.get("locality", "")

        performance = merchant.get("performance", {})
        offers = merchant.get("offers", [])

        offer_title = "your current offer"

        if offers:
            offer_title = offers[0].get("title", "your current offer")

        if kind == "research_digest":
            body = f"Hi {merchant_name}, there's new research relevant to your business. Would you like a quick summary?"

        elif kind == "perf_spike":
            body = f"Great news {merchant_name}! Your business performance has improved recently. Would you like to see what's driving it?"

        elif kind == "perf_dip":
            
            metric = trigger.get("payload", {}).get("metric", "performance")
            delta = trigger.get("payload", {}).get("delta_pct", 0)

            body = (
                f"Hi {merchant_name}, I noticed your {metric} dropped by "
                f"{abs(int(delta * 100))}% over the last week. "
                f"Your offer '{offer_title}' could help bring more customers. "
                f"Would you like a few suggestions?"
            )

        elif kind == "recall_due":
            body = f"Hi {merchant_name}, one of your customers is due for a follow-up. Shall I prepare a reminder?"

        elif kind == "festival_upcoming":
            body = f"Hi {merchant_name}, an upcoming festival is a good opportunity to promote your business. Want campaign ideas?"

        else:

            if category == "dentists":
                body = (
                    f"Hi Dr. {merchant_name}, I found an update that may help improve patient engagement. "
                    "Would you like me to suggest a patient communication?"
                )

            elif category == "gyms":
                body = (
                    f"Hi {merchant_name}, I noticed an opportunity to attract more gym members. "
                    "Would you like some campaign ideas?"
                )

            elif category == "restaurants":
                body = (
                    f"Hi {merchant_name}, I found a marketing opportunity that could increase customer visits. "
                    "Would you like to see it?"
                )

            elif category == "salons":
                body = (
                    f"Hi {merchant_name}, I have a few ideas that could help bring more salon appointments this week. "
                    "Interested?"
                )

            elif category == "pharmacies":
                body = (
                    f"Hi {merchant_name}, I noticed an opportunity to improve customer engagement for your pharmacy. "
                    "Would you like some suggestions?"
                )

            else:
                body = (
                    f"Hi {merchant_name}, I noticed a {kind} update for your business. "
                    "Would you like me to help with the next step?"
                )

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
