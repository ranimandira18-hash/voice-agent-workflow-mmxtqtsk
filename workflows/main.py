import os
import asyncio
import logging

from openai import OpenAI
from render_sdk import Workflows, Retry

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = Workflows()

_openai_client: OpenAI | None = None


def get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()
    return _openai_client

WORKFLOW_ID = os.getenv("WORKFLOW_SERVICE_ID", "claim-workflow")


def _hash_code(s: str) -> int:
    h = 0
    for ch in s:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
    return h if h < 0x80000000 else h - 0x100000000


# ============================================================================
# TASK DEFINITIONS
# ============================================================================


@app.task
async def verify_policy(phone: str) -> dict:
    """Verify customer policy by phone number."""
    logger.info(f"verify_policy START  phone={phone}")

    await asyncio.sleep(2)

    policy_id = (
        f"POL-{phone[-4:]}-{abs(_hash_code(phone)) % 10000:04d}"
    )

    loyalty = "Standard"
    claims = 0
    if "0100" in phone:
        loyalty, claims = "Gold", 0
    elif "0200" in phone:
        loyalty, claims = "Standard", 4
    elif "0300" in phone:
        loyalty, claims = "Platinum", 1
    elif "0400" in phone:
        loyalty, claims = "Standard", 2

    result = {
        "policy_id": policy_id,
        "phone": phone,
        "name": "Valued Customer",
        "status": "active",
        "coverage": {"collision": 50000, "deductible": 500},
        "loyalty_tier": loyalty,
        "previous_claims": claims,
    }
    logger.info(f"verify_policy DONE   policy_id={policy_id}")
    return result


PART_KEYWORDS = {
    "bumper": "bumper",
    "trunk": "trunk",
    "tail light": "tail_light",
    "taillight": "tail_light",
    "headlight": "headlight",
    "hood": "hood",
    "door": "door",
    "window": "window",
    "windshield": "windshield",
    "mirror": "mirror",
    "fender": "fender",
    "wheel": "wheel",
    "tire": "tire",
}


@app.task
async def analyze_damage(description: str) -> dict:
    """Analyze damage from description using AI vision processing."""
    logger.info(f"analyze_damage START  description={description!r}")

    await asyncio.sleep(8)

    lower = description.lower()
    parts: list[str] = []
    for keyword, part in PART_KEYWORDS.items():
        if keyword in lower and part not in parts:
            parts.append(part)

    if not parts:
        parts.append("unspecified_damage")

    if len(parts) >= 4:
        severity = "severe"
    elif len(parts) >= 2:
        severity = "moderate"
    else:
        severity = "minor"

    result = {
        "severity": severity,
        "parts": parts,
        "description": description,
        "confidence": 0.85,
    }
    logger.info(f"analyze_damage DONE  severity={severity} parts={parts}")
    return result


@app.task
async def fraud_check(claim_id: str) -> dict:
    """Run fraud detection model on claim."""
    logger.info(f"fraud_check START  claim_id={claim_id}")

    await asyncio.sleep(5)

    result = {
        "score": 12,
        "risk": "low",
        "flags": [],
        "risk_score": 0.12,
        "passed": True,
    }
    logger.info(f"fraud_check DONE  risk=low")
    return result


@app.task
async def generate_estimate(damage: dict) -> dict:
    """Generate repair cost estimate based on damage analysis."""
    logger.info(f"generate_estimate START  damage={damage}")

    await asyncio.sleep(6)

    result = {
        "total": 2347.0,
        "deductible": 500.0,
        "customer_owes": 500.0,
        "insurance_pays": 1847.0,
        "breakdown": {
            "rear_bumper": 850.0,
            "trunk_repair": 1200.0,
            "tail_light": 297.0,
        },
        "labor": 700.0,
    }
    logger.info(f"generate_estimate DONE  total={result['total']}")
    return result


@app.task
async def find_shops(zip_code: str) -> list:
    """Find approved repair shops near customer's location."""
    logger.info(f"find_shops START  zip_code={zip_code}")

    await asyncio.sleep(4)

    result = [
        {
            "name": "AutoFix Pro",
            "address": f"123 Main St, {zip_code}",
            "zip_code": zip_code,
            "distance": "1.2 mi",
            "rating": 4.8,
            "wait_days": 3,
        },
        {
            "name": "CarCare Center",
            "address": f"456 Oak Ave, {zip_code}",
            "zip_code": zip_code,
            "distance": "2.5 mi",
            "rating": 4.6,
            "wait_days": 2,
        },
        {
            "name": "Bay Auto Body",
            "address": f"789 Elm St, {zip_code}",
            "zip_code": zip_code,
            "distance": "3.1 mi",
            "rating": 4.9,
            "wait_days": 5,
        },
    ]
    logger.info(f"find_shops DONE  count={len(result)}")
    return result


@app.task
async def send_notification(claim_id: str, results: dict) -> dict:
    """Send email/SMS notification with claim results."""
    logger.info(f"send_notification START  claim_id={claim_id}")

    await asyncio.sleep(3)

    estimate = results.get("estimate", {})
    logger.info(
        f"[EMAIL] Claim {claim_id} approved. Estimate: ${estimate.get('total', 0)}"
    )
    logger.info(f"[SMS] SafeDrive: Your claim {claim_id} has been approved.")

    return {"email_sent": True, "sms_sent": True}


@app.task
async def process_claim(claim_id: str, claim_data: dict) -> dict:
    """Main orchestration task that processes the entire claim."""
    logger.info(f"process_claim START  claim_id={claim_id}")

    # 1. Verify policy
    policy = await verify_policy(claim_data["phone"])

    # 2-3. Parallel: damage analysis + fraud check
    damage, fraud = await asyncio.gather(
        analyze_damage(claim_data["damage"]),
        fraud_check(claim_id),
    )

    # 4. Generate estimate (depends on damage)
    estimate = await generate_estimate(damage)

    # 5. Find repair shops
    shops = await find_shops(claim_data["zip"])

    # 6. Send notification
    await send_notification(
        claim_id,
        {"policy": policy, "damage": damage, "fraud": fraud, "estimate": estimate, "shops": shops},
    )

    result = {
        "claim_id": claim_id,
        "status": "approved",
        "policy": policy,
        "damage": damage,
        "fraud": fraud,
        "estimate": estimate,
        "shops": shops,
    }
    logger.info(f"process_claim DONE  claim_id={claim_id} status=approved")
    return result


# ============================================================================
# CONVERSATION TASK
# ============================================================================

SYSTEM_PROMPT = """You are Alex, a friendly and empathetic customer support agent at SafeDrive Insurance.
You help customers file auto insurance claims after accidents.

Your personality:
- Warm and reassuring - accidents are stressful
- Professional but not robotic
- Patient - ask for ONE piece of information at a time

CRITICAL RULES:
1. Ask for ONE piece of information at a time
2. Wait for the customer to respond before asking the next question
3. USE customer info to personalize your responses
4. Keep responses SHORT - this is a phone call
5. NEVER use markdown (no asterisks, bold, etc.) - this is spoken audio
6. Speak numbers naturally
7. ALWAYS respond with spoken text, even when calling tools - acknowledge what they said and ask the next question

Follow this EXACT flow:

1. If safety not confirmed: Ask "Are you and everyone involved safe?"

2. If no phone: Ask "Can I get the phone number on your account?"
   - If customer info is available, greet them by name and confirm their vehicle

3. If no location: Ask "Where did the accident happen?"

4. If no damage description: Ask "Can you describe the damage to your vehicle?"
   - Reference their vehicle make/model if known
   - Say "I'm analyzing that now" after they describe it

5. If no ZIP code: Ask "What's your ZIP code? I'll find repair shops near you."
   - Say "Looking for shops in your area" after they give it

6. If no other party info: Ask "Were any other vehicles involved?"

7. After ALL info collected, summarize and confirm the claim is being processed.

Guidelines:
- NEVER ask multiple questions at once
- USE the customer's first name after looking them up
- If customer is Platinum/Gold tier, acknowledge their loyalty"""

CONVERSATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_safety_status",
            "description": "Save that safety has been confirmed",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": "Whether safety was confirmed",
                    },
                },
                "required": ["confirmed"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_phone_number",
            "description": "Save the customer's phone number",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "The customer's phone number",
                    },
                },
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_accident_location",
            "description": "Save the accident location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The accident location",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_damage_description",
            "description": "Save the damage description",
            "parameters": {
                "type": "object",
                "properties": {
                    "damage": {
                        "type": "string",
                        "description": "Description of the vehicle damage",
                    },
                },
                "required": ["damage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_zip_code",
            "description": "Save the ZIP code",
            "parameters": {
                "type": "object",
                "properties": {
                    "zip_code": {
                        "type": "string",
                        "description": "The customer's ZIP code",
                    },
                },
                "required": ["zip_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_other_party_info",
            "description": "Save information about other vehicles/parties involved",
            "parameters": {
                "type": "object",
                "properties": {
                    "involved": {
                        "type": "boolean",
                        "description": "Whether other vehicles/parties were involved",
                    },
                    "info": {
                        "type": "string",
                        "description": "Details about other parties if involved",
                    },
                },
                "required": ["involved"],
            },
        },
    },
]


@app.task
async def conversation(input_data: dict) -> dict:
    """Process user input and generate agent response.

    This is the "brain" of the voice agent, running as a Render Workflow task.
    """
    logger.info("conversation START")

    transcript = input_data["transcript"]
    session_state = input_data["sessionState"]
    conversation_history = input_data["conversationHistory"]

    logger.info(f"  transcript={transcript!r}")
    logger.info(f"  collected={session_state.get('collected', {})}")
    logger.info(f"  history_len={len(conversation_history)}")

    collected_info = ", ".join(
        f"{k}: {v}" for k, v in session_state.get("collected", {}).items()
    )

    profile = session_state.get("profile")
    if profile:
        profile_context = (
            f"Customer: {profile.get('first_name', '')} {profile.get('name', '')}, "
            f"{profile.get('loyalty_tier', 'Standard')} member, "
            f"Vehicle: {profile.get('vehicle', 'unknown')}"
        )
    else:
        profile_context = "Customer not yet identified"

    contextual_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"CURRENT SESSION STATE:\n"
        f"- Collected information: {collected_info or 'none yet'}\n"
        f"- {profile_context}"
    )

    messages = [{"role": "system", "content": contextual_prompt}]
    for m in conversation_history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": transcript})

    logger.info("  calling OpenAI GPT-4o …")
    response = get_openai().chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=CONVERSATION_TOOLS,
        tool_choice="auto",
    )

    choice = response.choices[0]
    extracted_fields: list[dict] = []
    triggered_tasks: list[str] = []

    if choice.message.tool_calls:
        import json

        for tc in choice.message.tool_calls:
            args = json.loads(tc.function.arguments)
            logger.info(f"  tool_call: {tc.function.name} args={args}")

            match tc.function.name:
                case "save_safety_status":
                    extracted_fields.append({
                        "field": "safety_confirmed",
                        "value": "yes" if args["confirmed"] else "no",
                    })
                case "save_phone_number":
                    extracted_fields.append({"field": "phone", "value": args["phone"]})
                    triggered_tasks.append("verify_policy")
                case "save_accident_location":
                    extracted_fields.append({"field": "location", "value": args["location"]})
                case "save_damage_description":
                    extracted_fields.append({"field": "damage", "value": args["damage"]})
                    triggered_tasks.append("analyze_damage")
                case "save_zip_code":
                    extracted_fields.append({"field": "zip", "value": args["zip_code"]})
                    triggered_tasks.append("find_shops")
                case "save_other_party_info":
                    extracted_fields.append({
                        "field": "other_party",
                        "value": args.get("info", "yes") if args["involved"] else "none",
                    })

    collected = {**session_state.get("collected", {})}
    for f in extracted_fields:
        collected[f["field"]] = f["value"]

    has_phone = "phone" in collected
    has_damage = "damage" in collected
    if has_phone and has_damage and "fraud_check" not in triggered_tasks:
        triggered_tasks.append("fraud_check")

    response_text = choice.message.content or ""

    if not response_text and extracted_fields:
        logger.info("  no response text — generating follow-up from state")
        if "phone" not in collected:
            response_text = "Great, I'm glad everyone is safe. Can I get the phone number on your account?"
        elif "location" not in collected:
            response_text = "Thanks for that. Where did the accident happen?"
        elif "damage" not in collected:
            response_text = "Got it. Can you describe the damage to your vehicle?"
        elif "zip" not in collected:
            response_text = "I'm analyzing that now. What's your ZIP code? I'll find repair shops near you."
        elif "other_party" not in collected:
            response_text = "Looking for shops in your area. Were any other vehicles involved?"
        else:
            response_text = (
                "Perfect, I have all the information I need. "
                "Your claim is being processed and you'll receive a confirmation shortly."
            )

    logger.info(f"  response_text={response_text!r}")
    logger.info(f"  extracted_fields={extracted_fields}")
    logger.info(f"  triggered_tasks={triggered_tasks}")
    logger.info("conversation DONE")

    return {
        "responseText": response_text,
        "extractedFields": extracted_fields,
        "triggeredTasks": triggered_tasks,
    }


@app.task
async def generate_greeting() -> dict:
    """Generate initial greeting for a new conversation."""
    logger.info("generate_greeting START")

    response = get_openai().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Generate a brief, warm greeting to start the call. "
                    "Introduce yourself as Alex from SafeDrive Insurance and ask if "
                    "the caller and everyone involved are safe. "
                    "Keep it natural and under 30 words."
                ),
            },
        ],
    )

    response_text = response.choices[0].message.content or ""
    logger.info(f"generate_greeting DONE  text={response_text!r}")
    return {"responseText": response_text}


if __name__ == "__main__":
    app.start()
