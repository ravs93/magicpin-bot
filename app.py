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
def compose_context_message(trigger, merchant, customer, category_context):
    kind = trigger.get("kind", "update")
    payload = trigger.get("payload", {})

    identity = merchant.get("identity", {})
    merchant_name = identity.get("name", "there")
    category = merchant.get("category_slug", "")

    performance = merchant.get("performance", {})
    offers = merchant.get("offers", [])
    signals = merchant.get("signals", [])
    customer_aggregate = merchant.get("customer_aggregate", {})

    peer_stats = category_context.get("peer_stats", {})
    digest = category_context.get("digest", [])
    offer_catalog = category_context.get("offer_catalog", [])
    seasonal_beats = category_context.get("seasonal_beats", [])
    trend_signals = category_context.get("trend_signals", [])

    offer_title = "a relevant offer"
    if offers:
        offer_title = offers[0].get("title", offer_title)
    elif offer_catalog:
        offer_title = offer_catalog[0].get("title", offer_title)

    signal_text = ""
    if signals:
        signal_text = signals[0].replace("_", " ")

    peer_text = ""
    ctr = performance.get("ctr")
    avg_ctr = peer_stats.get("avg_ctr")
    if ctr and avg_ctr:
        peer_text = f" Your CTR is {round(ctr * 100, 1)}% vs category benchmark {round(avg_ctr * 100, 1)}%."

    if kind == "research_digest":
        top_item_id = payload.get("top_item_id")
        item = None

        for d in digest:
            if d.get("id") == top_item_id:
                item = d
                break

        if not item and digest:
            item = digest[0]

        title = item.get("title", "a new category update") if item else "a new category update"
        source = item.get("source", "") if item else ""
        source_text = f" — {source}" if source else ""

        relevance = "your business"
        if category == "dentists" and customer_aggregate.get("high_risk_adult_count"):
            relevance = f"your {customer_aggregate.get('high_risk_adult_count')} high-risk adult patients"
        elif category == "gyms":
            relevance = "your members"
        elif category == "restaurants":
            relevance = "your customers"
        elif category == "salons":
            relevance = "your clients"
        elif category == "pharmacies":
            relevance = "your repeat customers"

        return (
            f"Hi {merchant_name}, I found this update relevant for {relevance}: "
            f"{title}{source_text}. Want me to summarize it and draft a WhatsApp message you can use?"
        )

    if kind == "perf_dip":
        metric = payload.get("metric", "performance")
        delta = abs(int(payload.get("delta_pct", 0) * 100))

        suggestion = f"promoting '{offer_title}'"
        if "no_active_offers" in signals:
            suggestion = "creating a new customer offer"
        elif "no_recent_post" in signals or any("stale_posts" in s for s in signals):
            suggestion = "posting fresh updates"
        elif signal_text:
            suggestion = f"acting on the signal: {signal_text}"

        return (
            f"Hi {merchant_name}, your {metric} dropped by {delta}% over the last 7 days."
            f"{peer_text} One practical recovery step is {suggestion}. "
            f"Want me to prepare a specific recommendation?"
        )

    if kind == "perf_spike":
        metric = payload.get("metric", "performance")
        delta = abs(int(payload.get("delta_pct", 0) * 100)) if payload.get("delta_pct") else None
        delta_text = f" by {delta}%" if delta else ""

        return (
            f"Great news {merchant_name}, your {metric} improved{delta_text} recently."
            f"{peer_text} This is a good moment to push '{offer_title}' while interest is warm. "
            f"Want me to draft one campaign?"
        )

    if kind == "recall_due":
        customer_identity = customer.get("identity", {}) if customer else {}
        customer_name = customer_identity.get("name", "there")
        language_pref = customer_identity.get("language_pref", "")

        service_due = payload.get("service_due", "follow-up").replace("_", " ")
        slots = payload.get("available_slots", [])
        slot_text = ""

        if slots:
            labels = [s.get("label") for s in slots if s.get("label")]
            if labels:
                slot_text = " Available slots: " + " or ".join(labels[:2]) + "."

        if "hi-en" in language_pref:
            return (
                f"Hi {customer_name}, {merchant_name} se reminder hai — your {service_due} is due."
                f" {offer_title} available hai.{slot_text} Reply YES to book, or suggest another time."
            )

        return (
            f"Hi {customer_name}, this is a reminder from {merchant_name} — your {service_due} is due."
            f" {offer_title} is available.{slot_text} Reply YES to book, or suggest another time."
        )

    if kind == "festival_upcoming":
        festival = payload.get("festival", "an upcoming festival")
        days_until = payload.get("days_until")
        days_text = f" in {days_until} days" if days_until else ""

        return (
            f"Hi {merchant_name}, {festival} is coming up{days_text}. "
            f"This is a good window to promote '{offer_title}' with a category-specific WhatsApp campaign. "
            f"Want me to draft one?"
        )

    if seasonal_beats:
        seasonal_note = seasonal_beats[0].get("note", "")
        return (
            f"Hi {merchant_name}, quick observation for {category}: {seasonal_note}. "
            f"Based on your current context, '{offer_title}' could be a useful angle. Want me to draft a message?"
        )

    if trend_signals:
        trend = trend_signals[0]
        query = trend.get("query", "customer demand")
        delta_yoy = trend.get("delta_yoy")
        trend_text = f"{query}"
        if delta_yoy:
            trend_text += f" is up {round(delta_yoy * 100)}% YoY"

        return (
            f"Hi {merchant_name}, I noticed a category trend: {trend_text}. "
            f"This could be useful for your next WhatsApp campaign. Want me to draft one?"
        )

    return (
        f"Hi {merchant_name}, I noticed a {kind} update for your business. "
        f"Want me to suggest the next best action?"
    )
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
        customer = customer_contexts.get(customer_id, {})

        if not merchant:
            continue

        identity = merchant.get("identity", {})
        merchant_name = identity.get("name", "there")
        category = merchant.get("category_slug", "")
        category_context = category_contexts.get(category, {})

        body = compose_context_message(
            trigger,
            merchant,
            customer,
            category_context
        )

        actions.append({
            "conversation_id": f"conv_{merchant_id}_{trigger_id}",
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": "merchant_on_behalf" if customer_id else "vera",
            "trigger_id": trigger_id,
            "template_name": f"vera_{kind}_v2",
            "template_params": [merchant_name, kind],
            "body": body,
            "cta": "open_ended",
            "suppression_key": trigger.get("suppression_key", trigger_id),
            "rationale": f"Composed using trigger, merchant, customer, and category context for {kind}"
        })

    return {
        "actions": actions
    }