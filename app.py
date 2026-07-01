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
        category_context = category_contexts.get(category, {})
        city = identity.get("city", "")
        locality = identity.get("locality", "")

        performance = merchant.get("performance", {})
        offers = merchant.get("offers", [])

        offer_title = "your current offer"

        if offers:
            offer_title = offers[0].get("title", "your current offer")

        if kind == "research_digest":

            payload = trigger.get("payload", {})
            digest_items = category_context.get("digest", [])
            top_item_id = payload.get("top_item_id")

            digest_item = None

            for item in digest_items:
                if item.get("id") == top_item_id:
                    digest_item = item
                    break

            if not digest_item and digest_items:
                digest_item = digest_items[0]

            title = digest_item.get("title", "a new industry update") if digest_item else "a new industry update"
            source = digest_item.get("source", "") if digest_item else ""

            customer_aggregate = merchant.get("customer_aggregate", {})
            high_risk_count = customer_aggregate.get("high_risk_adult_count")

            relevance = "your business"
            if category == "dentists" and high_risk_count:
                relevance = f"your {high_risk_count} high-risk adult patients"
            elif category == "gyms":
                relevance = "your members"
            elif category == "restaurants":
                relevance = "your customers"
            elif category == "salons":
                relevance = "your clients"
            elif category == "pharmacies":
                relevance = "your repeat customers"

            source_text = f" — {source}" if source else ""

            body = (
                f"Hi {merchant_name}, I found this update relevant for {relevance}: "
                f"{title}{source_text}. "
                f"Would you like me to summarize it and draft a WhatsApp message you can use?"
            )

        elif kind == "perf_spike":

            payload = trigger.get("payload", {})
            metric = payload.get("metric", "performance")
            delta = abs(int(payload.get("delta_pct", 0) * 100)) if payload.get("delta_pct") else None

            peer_stats = category_context.get("peer_stats", {})
            avg_ctr = peer_stats.get("avg_ctr")
            ctr = performance.get("ctr")

            active_offer = offer_title
            if not offers:
                catalog = category_context.get("offer_catalog", [])
                if catalog:
                    active_offer = catalog[0].get("title", "a category-relevant offer")

            delta_text = f" by {delta}%" if delta else ""
            peer_text = ""

            if ctr and avg_ctr:
                peer_text = f" Your CTR is {round(ctr * 100, 1)}% vs category benchmark {round(avg_ctr * 100, 1)}%."

            body = (
                f"Great news {merchant_name}, your {metric} improved{delta_text} recently."
                f"{peer_text} This is a good moment to push '{active_offer}' while interest is warm. "
                f"Want me to draft a WhatsApp campaign for this?"
            )       

        elif kind == "recall_due":
            body = f"Hi {merchant_name}, one of your customers is due for a follow-up. Shall I prepare a reminder?"

        elif kind == "festival_upcoming":

            payload = trigger.get("payload", {})
            festival = payload.get("festival", "an upcoming festival")
            days_until = payload.get("days_until")
            category_relevance = payload.get("category_relevance", [])

            relevance_text = ""
            if category_relevance:
                relevance_text = f" This is especially relevant for {', '.join(category_relevance)}."

            days_text = f" in {days_until} days" if days_until else ""

            body = (
                f"Hi {merchant_name}, {festival} is coming up{days_text}."
                f"{relevance_text} This could be a good time to run a category-specific campaign around '{offer_title}'. "
                f"Want me to draft one WhatsApp campaign you can review?"
            )

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
