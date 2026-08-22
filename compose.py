"""
LLM-powered composer for Vera.
"""
import os
import json
import anthropic

MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")
_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are Vera, magicpin's AI assistant for local merchant growth \
(dentists, salons, restaurants, gyms, pharmacies). Given structured JSON context \
about a category, a merchant, a trigger event, and optionally a customer, you \
decide the single next message Vera should send and write it.

You are graded on five dimensions, each 0-10:
1. Decision quality -- pick the ONE signal (from trigger + merchant state + \
   category context) that matters most right now. Do not list multiple facts.
2. Specificity -- use real numbers, offer names, dates, and facts that are \
   actually present in the given context. NEVER invent a number, name, or \
   claim that isn't grounded in the input JSON.
3. Category fit -- match tone to the business type (e.g. clinical and \
   reassuring for dentists/pharmacies, visual and aspirational for salons, \
   timely and appetite-driven for restaurants, motivational for gyms).
4. Merchant fit -- personalize using this merchant's own performance, offers, \
   and conversation history, not a generic template.
5. Engagement compulsion -- give ONE sharp, concrete reason to reply right now, \
   with a single low-friction next action (usually a yes/no or one-tap choice).

Hard rules:
- Never fabricate facts, numbers, or claims not present in the given context.
- Exactly one clear call-to-action per message.
- Keep messages short (roughly 1-3 sentences) -- this is a WhatsApp-style message, not an email.
- If a customer context is present, address the customer directly. If not, \
  address the merchant.

Respond with ONLY a JSON object, no other text, in exactly this shape:
{
  "body": "<the message text>",
  "cta": "<one of: open_ended, yes_no, book_now, view_offer>",
  "send_as": "<'vera' or 'merchant_on_behalf'>",
  "rationale": "<one sentence: which signal you chose and why>"
}
"""


def _fallback_compose(trigger, merchant, customer, category_context):
    identity = merchant.get("identity", {}) or {}
    name = identity.get("name", "there")
    kind = trigger.get("kind", "update")
    return {
        "body": f"Hi {name}, I have an update related to a '{kind.replace('_', ' ')}' event for your business. Want me to put together a specific recommendation using your current numbers?",
        "cta": "open_ended",
        "send_as": "merchant_on_behalf" if customer else "vera",
        "rationale": "Fallback composer used (LLM call failed or timed out).",
    }


def compose_message(trigger, merchant, customer, category_context):
    user_payload = {"trigger": trigger, "merchant": merchant, "customer": customer, "category_context": category_context}
    try:
        resp = _client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            timeout=20.0,
            messages=[{"role": "user", "content": "Compose the next Vera message from this context:\n\n" + json.dumps(user_payload, ensure_ascii=False)}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        assert "body" in parsed and parsed["body"]
        return parsed
    except Exception as e:
        print(f"[compose] LLM compose failed, using fallback: {e}")
        return _fallback_compose(trigger, merchant, customer, category_context)


REPLY_SYSTEM_PROMPT = """You are Vera continuing a WhatsApp-style conversation with \
a merchant or customer. You'll be given the conversation history and the latest \
incoming message, plus the original merchant/trigger context that started this thread.

Decide ONE of three actions:
- "send": reply now with a grounded, specific, short message and exactly one next step.
- "wait": the incoming message doesn't need an immediate reply.
- "end": the person declined, said stop, or the conversation has reached a natural close.

Treat hostile, sarcastic, or off-topic replies calmly.

Respond with ONLY a JSON object:
{"action": "send|wait|end", "body": "<message if action is send, else empty string>", "rationale": "<one sentence>"}
"""


def compose_reply(history, latest_message, origin_context):
    try:
        resp = _client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=REPLY_SYSTEM_PROMPT,
            timeout=20.0,
            messages=[{"role": "user", "content": json.dumps({"conversation_history": history, "latest_message": latest_message, "origin_context": origin_context}, ensure_ascii=False)}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        assert "action" in parsed
        return parsed
    except Exception as e:
        print(f"[compose_reply] LLM reply failed, using safe fallback: {e}")
        low = latest_message.lower()
        if any(w in low for w in ["stop", "not interested", "no thanks", "unsubscribe"]):
            return {"action": "end", "body": "", "rationale": "Fallback keyword match: opted out."}
        return {"action": "send", "body": "Thanks for the reply -- could you tell me a little more so I can help properly?", "rationale": "Fallback: LLM call failed, used safe generic continuation."}
