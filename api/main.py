import os
import json
import uuid
import asyncio
import logging
import traceback
import base64
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from livekit import api
from openai import AsyncOpenAI
from render_sdk import RenderAsync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# STARTUP
# ============================================================================

logger.info("=" * 60)
logger.info("[STARTUP] Insurance Claim API starting...")
logger.info("[STARTUP] Environment check:")
logger.info(f"  - OPENAI_API_KEY: {'set' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")
logger.info(f"  - RENDER_API_KEY: {'set' if os.getenv('RENDER_API_KEY') else 'NOT SET'}")
logger.info(f"  - WORKFLOW_SERVICE_ID: {os.getenv('WORKFLOW_SERVICE_ID') or 'NOT SET'}")
logger.info(f"  - RENDER_USE_LOCAL_DEV: {os.getenv('RENDER_USE_LOCAL_DEV') or 'NOT SET'}")
logger.info(f"  - RENDER_LOCAL_DEV_URL: {os.getenv('RENDER_LOCAL_DEV_URL') or 'NOT SET'}")
logger.info(f"  - RENDER_SDK_SOCKET_PATH: {os.getenv('RENDER_SDK_SOCKET_PATH') or 'NOT SET'}")
logger.info(f"  - render_sdk version: {__import__('render_sdk').__version__}")
logger.info("=" * 60)

app = FastAPI(title="Insurance Claim API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai_client = AsyncOpenAI()

# In-memory storage (would use PostgreSQL in production)
claims_db: dict = {}
call_sessions: dict = {}
voice_sessions: dict = {}

# ============================================================================
# DEMO CUSTOMER PROFILES
# ============================================================================
CUSTOMER_PROFILES = {
    "555-0100": {
        "name": "Sarah Johnson",
        "first_name": "Sarah",
        "policy_id": "POL-94102-7721",
        "policy_status": "active",
        "coverage": "$100,000",
        "deductible": 500,
        "member_since": "2019",
        "previous_claims": 0,
        "risk_score": 0.08,
        "fraud_flags": [],
        "loyalty_tier": "Gold",
        "vehicle": {
            "year": 2022,
            "make": "Toyota",
            "model": "Camry",
            "color": "Silver",
            "vin": "4T1B11HK5NU123456",
        },
        "address": {"city": "San Francisco", "state": "CA", "zip": "94102"},
    },
    "555-0200": {
        "name": "Mike Thompson",
        "first_name": "Mike",
        "policy_id": "POL-88451-3392",
        "policy_status": "active",
        "coverage": "$50,000",
        "deductible": 1000,
        "member_since": "2021",
        "previous_claims": 4,
        "claim_history": [
            {"date": "2022-03", "type": "collision", "amount": 3200},
            {"date": "2022-11", "type": "collision", "amount": 1800},
            {"date": "2023-06", "type": "vandalism", "amount": 950},
            {"date": "2024-02", "type": "collision", "amount": 4100},
        ],
        "risk_score": 0.67,
        "fraud_flags": ["multiple_claims_short_period"],
        "loyalty_tier": "Standard",
        "vehicle": {
            "year": 2019,
            "make": "Ford",
            "model": "F-150",
            "color": "Black",
            "vin": "1FTEW1EP5KFA12345",
        },
        "address": {"city": "Beverly Hills", "state": "CA", "zip": "90210"},
    },
    "555-0300": {
        "name": "Emma Rodriguez",
        "first_name": "Emma",
        "policy_id": "POL-PLAT-0042",
        "policy_status": "active",
        "coverage": "$250,000",
        "deductible": 250,
        "member_since": "2015",
        "previous_claims": 1,
        "claim_history": [
            {"date": "2020-08", "type": "weather", "amount": 2100},
        ],
        "risk_score": 0.05,
        "fraud_flags": [],
        "loyalty_tier": "Platinum",
        "perks": ["priority_processing", "free_rental_car", "concierge_service"],
        "vehicle": {
            "year": 2024,
            "make": "BMW",
            "model": "X5",
            "color": "Midnight Blue",
            "vin": "5UXCR6C55R9A98765",
        },
        "address": {"city": "Manhattan", "state": "NY", "zip": "10001"},
    },
    "555-0400": {
        "name": "James Wilson",
        "first_name": "James",
        "policy_id": "POL-66201-8844",
        "policy_status": "payment_overdue",
        "coverage": "$75,000",
        "deductible": 750,
        "member_since": "2022",
        "previous_claims": 2,
        "risk_score": 0.45,
        "fraud_flags": [],
        "loyalty_tier": "Standard",
        "account_notes": ["payment_30_days_overdue", "requires_payment_before_claim"],
        "vehicle": {
            "year": 2020,
            "make": "Honda",
            "model": "Civic",
            "color": "White",
            "vin": "2HGFC2F69LH567890",
        },
        "address": {"city": "Miami", "state": "FL", "zip": "33101"},
    },
}

DEFAULT_PROFILE = {
    "name": "Valued Customer",
    "first_name": "there",
    "policy_id": "POL-TEMP-0001",
    "policy_status": "active",
    "coverage": "$50,000",
    "deductible": 500,
    "member_since": "2023",
    "previous_claims": 0,
    "risk_score": 0.15,
    "fraud_flags": [],
    "loyalty_tier": "Standard",
    "vehicle": None,
    "address": None,
}


def get_customer_profile(phone: str) -> dict:
    normalized = "".join(c for c in phone if c.isdigit())
    for known_phone, profile in CUSTOMER_PROFILES.items():
        known_normalized = "".join(c for c in known_phone if c.isdigit())
        if normalized.endswith(known_normalized) or known_normalized in normalized:
            return profile
    return DEFAULT_PROFILE


# ============================================================================
# RENDER WORKFLOW HELPERS
# ============================================================================


def _unwrap_result(results):
    """Render Workflows sometimes wraps results in an array."""
    return results[0] if isinstance(results, list) else results


def _task_id(task_name: str) -> str:
    """Build the task identifier. Local dev uses bare task names; remote uses slug/task."""
    if os.getenv("RENDER_USE_LOCAL_DEV", "").lower() == "true":
        return task_name
    wid = os.getenv("WORKFLOW_SERVICE_ID")
    if not wid:
        raise RuntimeError("WORKFLOW_SERVICE_ID not configured")
    return f"{wid}/{task_name}"


async def run_workflow_task(room: str, task_name: str, args: list):
    """Run a Render Workflow task and update the session when complete."""
    try:
        task_identifier = _task_id(task_name)
    except RuntimeError:
        logger.error(f"[WORKFLOW] WORKFLOW_SERVICE_ID not set, cannot run {task_name}")
        return
    logger.info(f"[WORKFLOW] Triggering {task_identifier} args={args}")

    try:
        render = RenderAsync()
        task_run = await render.workflows.run_task(task_identifier, args)

        result = _unwrap_result(task_run.results)
        logger.info(
            f"[WORKFLOW] {task_name} completed  run_id={task_run.id} status={task_run.status}"
        )

        # Update whichever session owns this room
        vs = voice_sessions.get(room)
        cs = call_sessions.get(room)

        if vs:
            vs["tasks"][task_name] = {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now().isoformat(),
                "task_run_id": task_run.id,
            }
            ws = vs.get("ws")
            if ws:
                await _ws_send(ws, {
                    "type": "session_update",
                    "data": {
                        "collected": vs["collected"],
                        "tasks": vs["tasks"],
                        "profile": vs["profile"],
                    },
                })
        elif cs:
            cs["tasks"][task_name] = {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now().isoformat(),
                "task_run_id": task_run.id,
            }

    except Exception as e:
        logger.error(f"[WORKFLOW] {task_name} failed: {type(e).__name__}: {e}")
        traceback.print_exc()

        for store in (voice_sessions, call_sessions):
            sess = store.get(room)
            if sess:
                sess["tasks"][task_name] = {
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.now().isoformat(),
                }
                break


# ============================================================================
# VOICE WEBSOCKET HELPERS
# ============================================================================


async def _ws_send(ws: WebSocket, msg: dict):
    try:
        await ws.send_json(msg)
    except Exception:
        pass


async def speech_to_text(audio_bytes: bytes) -> str:
    logger.info(f"[STT] Processing {len(audio_bytes)} bytes")
    transcription = await openai_client.audio.transcriptions.create(
        file=("audio.webm", audio_bytes, "audio/webm"),
        model="whisper-1",
        language="en",
    )
    logger.info(f"[STT] Result: {transcription.text!r}")
    return transcription.text


async def text_to_speech(text: str) -> bytes:
    logger.info(f"[TTS] Generating speech for: {text[:60]!r}…")
    response = await openai_client.audio.speech.create(
        model="tts-1",
        voice="marin",
        input=text,
        response_format="mp3",
        speed=1.1,
    )
    audio_bytes = await response.aread()
    logger.info(f"[TTS] Generated {len(audio_bytes)} bytes")
    return audio_bytes


def _get_task_argument(task_name: str, session: dict) -> Optional[str]:
    match task_name:
        case "verify_policy":
            return session["collected"].get("phone")
        case "analyze_damage":
            return session["collected"].get("damage")
        case "find_shops":
            return session["collected"].get("zip")
        case "fraud_check":
            return session["room_id"]
        case _:
            return None


async def process_voice_turn(ws: WebSocket, session: dict, audio_bytes: bytes):
    """STT -> conversation workflow -> TTS"""
    render = RenderAsync()

    try:
        # 1. Speech to Text
        await _ws_send(ws, {"type": "processing", "step": "stt"})
        transcript = await speech_to_text(audio_bytes)
        if not transcript.strip():
            return

        await _ws_send(ws, {"type": "transcript", "text": transcript, "role": "user"})

        # 2. Call conversation workflow task
        await _ws_send(ws, {"type": "processing", "step": "llm"})
        logger.info("[VOICE] Calling conversation workflow task…")

        conversation_input = {
            "transcript": transcript,
            "sessionState": {
                "roomId": session["room_id"],
                "collected": session["collected"],
                "profile": session["profile"],
            },
            "conversationHistory": session["conversation_history"],
        }

        task_run = await render.workflows.run_task(
            _task_id("conversation"),
            [conversation_input],
        )
        result = _unwrap_result(task_run.results)
        if not result:
            raise RuntimeError(f"Invalid workflow response: {task_run.results}")

        response_text = result.get("responseText") or "Got it."
        extracted_fields = result.get("extractedFields", [])
        triggered_tasks = result.get("triggeredTasks", [])

        logger.info(f"[VOICE] Response: {response_text!r}")

        # Update session with extracted fields
        for field_info in extracted_fields:
            field, value = field_info["field"], field_info["value"]
            session["collected"][field] = value
            if field == "phone":
                profile = get_customer_profile(value)
                if profile is not DEFAULT_PROFILE:
                    session["profile"] = profile

        session["conversation_history"].append({"role": "user", "content": transcript})
        session["conversation_history"].append({"role": "assistant", "content": response_text})

        # Trigger background tasks
        for task_name in triggered_tasks:
            if task_name not in session["tasks"]:
                session["tasks"][task_name] = {
                    "status": "running",
                    "started_at": datetime.now().isoformat(),
                }
                arg = _get_task_argument(task_name, session)
                if arg is not None:
                    asyncio.create_task(
                        run_workflow_task(session["room_id"], task_name, [arg])
                    )

        await _ws_send(ws, {
            "type": "session_update",
            "data": {
                "collected": session["collected"],
                "tasks": session["tasks"],
                "profile": session["profile"],
            },
        })
        await _ws_send(ws, {"type": "transcript", "text": response_text, "role": "assistant"})

        # 3. Text to Speech
        await _ws_send(ws, {"type": "processing", "step": "tts"})
        audio_response = await text_to_speech(response_text)
        await _ws_send(ws, {
            "type": "audio",
            "data": base64.b64encode(audio_response).decode(),
        })

    except Exception as e:
        logger.error(f"[VOICE] Error processing voice turn: {e}")
        traceback.print_exc()
        await _ws_send(ws, {
            "type": "error",
            "message": f"Failed to run task: {e}",
        })


async def generate_greeting(ws: WebSocket, session: dict):
    """Call the generate_greeting workflow task and stream TTS back."""
    render = RenderAsync()

    try:
        await _ws_send(ws, {"type": "processing", "step": "llm"})
        logger.info("[VOICE] Generating greeting…")

        task_run = await render.workflows.run_task(
            _task_id("generate_greeting"), []
        )
        result = _unwrap_result(task_run.results)
        if not result or not result.get("responseText"):
            raise RuntimeError(f"Invalid greeting response: {task_run.results}")

        response_text = result["responseText"]
        logger.info(f"[VOICE] Greeting: {response_text!r}")

        session["conversation_history"].append(
            {"role": "assistant", "content": response_text}
        )

        await _ws_send(ws, {"type": "transcript", "text": response_text, "role": "assistant"})

        await _ws_send(ws, {"type": "processing", "step": "tts"})
        audio_response = await text_to_speech(response_text)
        await _ws_send(ws, {
            "type": "audio",
            "data": base64.b64encode(audio_response).decode(),
        })

    except Exception as e:
        logger.error(f"[VOICE] Error generating greeting: {e}")
        traceback.print_exc()
        await _ws_send(ws, {"type": "error", "message": str(e)})


# ============================================================================
# MODELS
# ============================================================================


class ClaimData(BaseModel):
    phone: str
    location: str
    damage: str
    zip: str
    other_party: Optional[str] = None


class ClaimCreate(BaseModel):
    claim_data: ClaimData
    transcript: Optional[str] = None


class TokenRequest(BaseModel):
    room_name: Optional[str] = None
    participant_name: Optional[str] = "customer"


class SessionUpdate(BaseModel):
    room_name: str
    field: str
    value: str


# ============================================================================
# ROUTES
# ============================================================================


@app.get("/")
async def root():
    return {"status": "ok", "service": "Insurance Claim API"}


@app.post("/api/token")
async def get_token(request: TokenRequest):
    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_url, api_key, api_secret]):
        raise HTTPException(status_code=500, detail="LiveKit not configured")

    room_name = request.room_name or f"claim-{uuid.uuid4().hex[:8]}"

    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(request.participant_name)
        .with_name(request.participant_name)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
    )

    return {
        "token": token.to_jwt(),
        "room_name": room_name,
        "livekit_url": livekit_url,
    }


# ============================================================================
# VOICE WEBSOCKET
# ============================================================================


@app.websocket("/ws/voice")
async def voice_websocket(ws: WebSocket):
    await ws.accept()
    logger.info("[WS] New voice WebSocket connection")

    session: Optional[dict] = None

    try:
        while True:
            raw = await ws.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type")
            logger.info(f"[WS] Received message type: {msg_type}")

            if msg_type == "start_session":
                room_id = message.get("roomId") or f"voice-{uuid.uuid4().hex[:8]}"
                session = {
                    "room_id": room_id,
                    "conversation_history": [],
                    "collected": {},
                    "tasks": {},
                    "profile": None,
                    "created_at": datetime.now().isoformat(),
                    "ws": ws,
                }
                voice_sessions[room_id] = session
                logger.info(f"[WS] Created voice session: {room_id}")
                await _ws_send(ws, {"type": "session_started", "roomId": room_id})
                await generate_greeting(ws, session)

            elif msg_type == "audio" and session:
                audio_bytes = base64.b64decode(message["data"])
                await process_voice_turn(ws, session, audio_bytes)

    except WebSocketDisconnect:
        if session:
            logger.info(f"[WS] Voice session closed: {session['room_id']}")
    except Exception as e:
        logger.error(f"[WS] WebSocket error: {e}")
        traceback.print_exc()


# ============================================================================
# CLAIMS
# ============================================================================


@app.post("/api/claims")
async def create_claim(request: ClaimCreate):
    claim_id = f"CLM-{datetime.now().year}-{uuid.uuid4().hex[:4].upper()}"

    claim = {
        "id": claim_id,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "claim_data": request.claim_data.model_dump(),
        "transcript": request.transcript,
        "workflow_status": {
            "current_step": "verify_policy",
            "steps": {
                "verify_policy": {"status": "pending", "result": None},
                "analyze_damage": {"status": "pending", "result": None},
                "fraud_check": {"status": "pending", "result": None},
                "generate_estimate": {"status": "pending", "result": None},
                "find_shops": {"status": "pending", "result": None},
                "send_notification": {"status": "pending", "result": None},
            },
        },
        "result": None,
    }
    claims_db[claim_id] = claim

    is_local = os.getenv("RENDER_USE_LOCAL_DEV", "").lower() == "true"
    if not is_local:
        if not os.getenv("WORKFLOW_SERVICE_ID"):
            raise HTTPException(
                status_code=500,
                detail="WORKFLOW_SERVICE_ID not configured. Set it in render-config env group.",
            )
        if not os.getenv("RENDER_API_KEY"):
            raise HTTPException(
                status_code=500,
                detail="RENDER_API_KEY not configured. Set it in render-config env group.",
            )

    try:
        render = RenderAsync()
        task_identifier = _task_id("process_claim")
        logger.info(f"[WORKFLOW] Triggering {task_identifier}")

        task_run = await render.workflows.run_task(
            task_identifier,
            [claim_id, request.claim_data.model_dump()],
        )
        claim["task_run_id"] = task_run.id
        logger.info(f"[WORKFLOW] process_claim completed  run_id={task_run.id}")

    except Exception as e:
        logger.error(f"[WORKFLOW] process_claim failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Workflow trigger failed: {type(e).__name__}: {e}",
        )

    return {"claim_id": claim_id, "status": "processing"}


@app.get("/api/claims/{claim_id}")
async def get_claim(claim_id: str):
    if claim_id not in claims_db:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim = claims_db[claim_id]

    if claim.get("task_run_id"):
        try:
            render = RenderAsync()
            task_run = await render.workflows.get_task_run(claim["task_run_id"])
            if task_run.status == "completed":
                claim["status"] = "completed"
                claim["result"] = task_run.results
            elif task_run.status == "failed":
                claim["status"] = "failed"
        except Exception:
            pass

    return claim


@app.post("/api/claims/{claim_id}/steps/{step_name}")
async def update_step(claim_id: str, step_name: str, status: str, result: dict = None):
    if claim_id not in claims_db:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim = claims_db[claim_id]
    if step_name in claim["workflow_status"]["steps"]:
        claim["workflow_status"]["steps"][step_name] = {
            "status": status,
            "result": result,
            "completed_at": datetime.now().isoformat() if status == "completed" else None,
        }

        steps_order = [
            "verify_policy",
            "analyze_damage",
            "fraud_check",
            "generate_estimate",
            "find_shops",
            "send_notification",
        ]
        for step in steps_order:
            if claim["workflow_status"]["steps"][step]["status"] == "pending":
                claim["workflow_status"]["current_step"] = step
                break
        else:
            claim["workflow_status"]["current_step"] = "completed"
            claim["status"] = "completed"

    return {"status": "updated"}


@app.get("/api/claims/latest")
async def get_latest_claim():
    if not claims_db:
        raise HTTPException(status_code=404, detail="No claims found")
    return max(claims_db.values(), key=lambda c: c["created_at"])


# ============================================================================
# SESSIONS
# ============================================================================


@app.post("/api/session/update")
async def update_session(update: SessionUpdate, background_tasks: BackgroundTasks):
    logger.info(f"[SESSION] room={update.room_name} field={update.field} value={update.value}")
    room = update.room_name

    if room not in call_sessions:
        call_sessions[room] = {
            "collected": {},
            "tasks": {},
            "profile": None,
            "created_at": datetime.now().isoformat(),
        }

    session = call_sessions[room]
    session["collected"][update.field] = update.value

    if update.field == "phone" and "verify_policy" not in session["tasks"]:
        session["profile"] = get_customer_profile(update.value)
        session["tasks"]["verify_policy"] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
        }
        background_tasks.add_task(run_workflow_task, room, "verify_policy", [update.value])

    elif update.field == "damage" and "analyze_damage" not in session["tasks"]:
        session["tasks"]["analyze_damage"] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
        }
        background_tasks.add_task(run_workflow_task, room, "analyze_damage", [update.value])

    elif update.field == "zip" and "find_shops" not in session["tasks"]:
        session["tasks"]["find_shops"] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
        }
        background_tasks.add_task(run_workflow_task, room, "find_shops", [update.value])

    if (
        "fraud_check" not in session["tasks"]
        and "phone" in session["collected"]
        and "damage" in session["collected"]
    ):
        session["tasks"]["fraud_check"] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
        }
        background_tasks.add_task(run_workflow_task, room, "fraud_check", [room])

    return {"status": "updated", "session": session}


@app.get("/api/session/{room_name}")
async def get_session(room_name: str):
    if room_name not in call_sessions:
        return {"collected": {}, "tasks": {}}
    return call_sessions[room_name]


# ============================================================================
# CUSTOMER LOOKUP & DEMO PROFILES
# ============================================================================


@app.get("/api/customer/lookup/{phone}")
async def lookup_customer(phone: str):
    profile = get_customer_profile(phone)

    vehicle = profile.get("vehicle")
    vehicle_desc = None
    if vehicle:
        vehicle_desc = f"{vehicle['year']} {vehicle['color']} {vehicle['make']} {vehicle['model']}"

    return {
        "found": profile is not DEFAULT_PROFILE,
        "first_name": profile["first_name"],
        "full_name": profile["name"],
        "loyalty_tier": profile["loyalty_tier"],
        "member_since": profile["member_since"],
        "vehicle": vehicle_desc,
        "vehicle_details": vehicle,
        "policy_status": profile["policy_status"],
        "previous_claims": profile["previous_claims"],
        "deductible": profile["deductible"],
        "has_issues": profile["policy_status"] != "active"
        or len(profile.get("account_notes", [])) > 0,
        "account_notes": profile.get("account_notes", []),
        "perks": profile.get("perks", []),
    }


@app.get("/api/demo/profiles")
async def get_demo_profiles():
    return {
        "profiles": [
            {
                "phone": "555-0100",
                "zip": "94102",
                "name": "Sarah Johnson",
                "vehicle": "2022 Silver Toyota Camry",
                "scenario": "Good Customer",
                "description": "Clean history, Gold member, quick approval. Low risk score.",
                "expected_outcome": "Fast approval, standard process",
            },
            {
                "phone": "555-0200",
                "zip": "90210",
                "name": "Mike Thompson",
                "vehicle": "2019 Black Ford F-150",
                "scenario": "Frequent Claims",
                "description": "4 previous claims in 2 years, higher risk score, fraud flags.",
                "expected_outcome": "Extended review, fraud check warning",
            },
            {
                "phone": "555-0300",
                "zip": "10001",
                "name": "Emma Rodriguez",
                "vehicle": "2024 Midnight Blue BMW X5",
                "scenario": "VIP Customer",
                "description": "Platinum member since 2015, premium coverage, concierge perks.",
                "expected_outcome": "Priority processing, premium repair shop options",
            },
            {
                "phone": "555-0400",
                "zip": "33101",
                "name": "James Wilson",
                "vehicle": "2020 White Honda Civic",
                "scenario": "Payment Issues",
                "description": "Policy payment 30 days overdue, requires attention.",
                "expected_outcome": "Account warning, payment required notice",
            },
        ],
        "usage": "Say the phone number during the call when Alex asks for it.",
    }


@app.get("/api/debug/workflow-test")
async def debug_workflow_test():
    """Direct workflow connectivity test — bypasses voice/agent flow entirely."""
    results = {}
    task_names = ["verify_policy", "generate_greeting", "conversation"]
    for name in task_names:
        tid = _task_id(name)
        try:
            logger.info(f"[DEBUG] Triggering task {tid}")
            client = RenderAsync()
            if name == "verify_policy":
                run = await client.workflows.run_task(tid, ["POL-2024-7749"])
            elif name == "generate_greeting":
                run = await client.workflows.run_task(tid, ["Sarah"])
            else:
                run = await client.workflows.run_task(
                    tid, ["system prompt", [{"role": "user", "content": "hello"}]]
                )
            results[name] = {"status": "ok", "run_id": str(run.id) if run else "no-id"}
            logger.info(f"[DEBUG] Task {tid} succeeded: {run}")
        except Exception as exc:
            logger.error(f"[DEBUG] Task {tid} failed: {exc}")
            results[name] = {"status": "failed", "error": str(exc)}
    return {"collected": {"task_id_prefix": _task_id("X").rsplit("/", 1)[0]}, "tasks": results}


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
