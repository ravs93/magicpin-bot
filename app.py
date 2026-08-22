from fastapi import FastAPI, Request
from datetime import datetime, timezone

import storage
import compose

app = FastAPI()

VALID_SCOPES = {"category", "merchant", "customer", "trigger"}


@app.get("/")
def home():
    return {"status": "running"}


@app.get("/v1/healthz")
def healthz():
    return {
        "status": "ok",
        "uptime_seconds": storage.uptime_seconds(),
        "contexts_loaded": {
            "category": storage.count_prefix("category:"),
            "merchant": storage.count_prefix("merchant:"),
            "customer": storage.count_prefix("customer:"),
            "trigger": storage.count_prefix("trigger:"),
        },
        "persistent_storage": storage.is_persistent(),
    }


@app.get("/v1/metadata")
def metadata():
    return {
        "team_name": "Ravinder Singh",
        "team_members": ["Ravinder Singh"],
        "model": compose.MODEL,
        "approach": "LLM-composed messages grounded in full context JSON, "
                    "persistent external storage, LLM-based reply handling",
        "contact_email": "rs536091@gmail.com",
        "version": "2.0.0",
    }


@app.post("/v1/context")
async def receive_context(request: Request):
    data = await request.json()
    scope = data.get("scope")
    context_id = data.get("context_id")
    version = data.get("version", 1)
    payload = data.get("payload", {})

    if scope not in VALID_SCOPES:
        return {"accepted": False, "reason": "invalid_scope", "details": f"Unknown scope: {scope}"}
    if not context_id:
        return {"accepted": False, "reason": "missing_context_id"}

    key = f"{scope}:{context_id}"
    existing = storage.get_json(key)

    if existing and existing.get("_version", 0) > version:
        return {"accepted": False, "reason": "stale_version", "current_version": existing.get("_version", 0)}

    if existing and existing.get("_version", 0) == version:
        # Re-posting the same version is a no-op per spec.
        return {
            "accepted": True,
            "ack_id": f"ack_{context_id}_v{version}",
            "stored_at": existing.get("_stored_at"),
        }

    stored_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = dict(payload)
    payload["_version"] = version
    payload["_stored_at"] = stored_at
    storage.set_json(key, payload)

    return {"accepted": True, "ack_id": f"ack_{context_id}_v{version}", "stored_at": stored_at}


@app.post("/v1/reply")
async def reply(request: Request):
    data = await request.json()
    conversation_id = data.get("conversation_id")
    message = data.get("message", "")

    history = storage.append_conversation(conversation_id, {"role": "incoming", "message": message})
    origin_context = storage.get_json(f"conv_origin:{conversation_id}") or {}

    result = compose.compose_reply(history, message, origin_context)

    storage.append_conversation(conversation_id, {"role": "vera", "action": result.get("action"), "body": result.get("body", "")})

    out = {"action": result.get("action", "send"), "rationale": result.get("rationale", "")}
    if result.get("action") == "send":
        out["body"] = result.get("body", "")
    return out


@app.post("/v1/tick")
async def tick(request: Request):
    data = await request.json()
    available_triggers = data.get("available_triggers", [])
    actions = []

    for trigger_id in available_triggers:
        trigger = storage.get_json(f"trigger:{trigger_id}")
        if not trigger:
            continue

        merchant_id = trigger.get("merchant_id")
        customer_id = trigger.get("customer_id")
        kind = trigger.get("kind", "update")

        merchant = storage.get_json(f"merchant:{merchant_id}") if merchant_id else None
        if not merchant:
            continue
        customer = storage.get_json(f"customer:{customer_id}") if customer_id else None

        category_slug = merchant.get("category_slug", "")
        category_context = storage.get_json(f"category:{category_slug}") or {}

        composed = compose.compose_message(trigger, merchant, customer, category_context)

        conversation_id = f"conv_{merchant_id}_{trigger_id}"
        # Remember what this conversation originated from, so /v1/reply has context later.
        storage.set_json(
            f"conv_origin:{conversation_id}",
            {"trigger": trigger, "merchant": merchant, "customer": customer, "category_context": category_context},
        )

        actions.append({
            "conversation_id": conversation_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": composed.get("send_as", "merchant_on_behalf" if customer_id else "vera"),
            "trigger_id": trigger_id,
            "template_name": f"vera_{kind}_v3",
            "template_params": [merchant.get("identity", {}).get("name", ""), kind],
            "body": composed.get("body", ""),
            "cta": composed.get("cta", "open_ended"),
            "suppression_key": trigger.get("suppression_key", trigger_id),
            "rationale": composed.get("rationale", ""),
        })

        if len(actions) >= 20:  # tick cap per the spec
            break

    return {"actions": actions}
