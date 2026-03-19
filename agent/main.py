import logging
import os
import httpx

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    AgentSession,
    Agent,
    function_tool,
)
from livekit.plugins import openai, silero

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("insurance-agent")


# Build API URL from host or use default for local dev
def get_api_url():
    api_host = os.getenv("API_HOST")
    logger.info(f"API_HOST env var: {api_host}")
    if api_host:
        # Handle both cases: just service name or full hostname
        if ".onrender.com" in api_host:
            url = f"https://{api_host}"
        else:
            url = f"https://{api_host}.onrender.com"
        logger.info(f"Constructed API URL: {url}")
        return url
    logger.info("No API_HOST set, using local default")
    return "http://api:8000"  # Local Docker default


API_URL = get_api_url()
logger.info(f"Agent will use API_URL: {API_URL}")

# Insurance agent system prompt
SYSTEM_PROMPT = """You are Alex, a friendly and empathetic customer support agent at SafeDrive Insurance. 
You help customers file auto insurance claims after accidents.

Your personality:
- Warm and reassuring - accidents are stressful
- Professional but not robotic
- Patient - ask for ONE piece of information at a time

CRITICAL RULES:
1. Ask for ONE piece of information at a time
2. After EACH response, call the corresponding save function to record it
3. Wait for the customer to respond before asking the next question
4. USE customer info returned by functions to personalize your responses

Follow this EXACT flow:

1. Confirm safety: "Are you and everyone involved safe?"
   → When they confirm, call save_safety_status(confirmed=true)

2. Ask for phone: "Can I get the phone number on your account?"
   → When they give it, call save_phone_number(phone="...")
   → The function returns customer info (name, vehicle, status)
   → GREET THEM BY NAME: "Hi [name]! I see you have a [vehicle] on file. Is that the vehicle involved?"
   → If they have account issues, mention it politely

3. Ask for location: "Where did the accident happen?"
   → When they answer, call save_accident_location(location="...")

4. Ask about damage: "Can you describe the damage to your [vehicle make/model]?"
   → Reference their vehicle if known
   → When they describe it, call save_damage_description(damage="...")
   → Say "I'm analyzing that now"

5. Ask for ZIP: "What's your ZIP code? I'll find repair shops near you."
   → When they give it, call save_zip_code(zip="...")
   → Say "Looking for shops in your area"

6. Ask about other vehicles: "Were any other vehicles involved?"
   → Call save_other_party_info(involved=true/false, info="...")

7. After ALL info collected, call submit_claim with everything.

Guidelines:
- NEVER ask multiple questions at once
- Keep responses SHORT - this is a phone call
- NEVER use markdown (no asterisks, bold, etc.) - this is spoken audio
- Speak numbers naturally
- USE the customer's first name after looking them up
- If customer is Platinum/Gold tier, acknowledge their loyalty
"""


class InsuranceAgent(Agent):
    """Insurance claim agent with tools defined as methods."""

    def __init__(self, room_name: str):
        super().__init__(instructions=SYSTEM_PROMPT)
        self.room_name = room_name
        self.agent_session = None

    def set_session(self, session):
        self.agent_session = session

    async def _update_session(self, field: str, value: str):
        """Send session update to API."""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                await client.post(
                    f"{API_URL}/api/session/update",
                    json={"room_name": self.room_name, "field": field, "value": value},
                    timeout=10.0,
                )
                logger.info(f"Session updated: {field} = {value}")
        except Exception as e:
            logger.error(f"Failed to update session: {e}")
            # If we have the session, speak the error
            if self.agent_session:
                # We can't await session.say() here easily if we want to return quickly?
                # Actually tools are async, so we can.
                pass
                # Don't interrupt flow with error message, just log it.
                # But for debugging, let's log it to console.

    @function_tool()
    async def save_safety_status(self, confirmed: bool) -> str:
        """Save that safety has been confirmed. Call this after asking if everyone is safe."""
        logger.info(f"[TOOL CALLED] save_safety_status(confirmed={confirmed})")
        await self._update_session("safety_confirmed", "yes" if confirmed else "no")
        return "Safety status recorded."

    @function_tool()
    async def save_phone_number(self, phone: str) -> str:
        """Save the customer's phone number. This triggers policy verification and returns customer info."""
        logger.info(f"[TOOL CALLED] save_phone_number(phone={phone})")
        await self._update_session("phone", phone)

        # Look up customer to get their name and vehicle info
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{API_URL}/api/customer/lookup/{phone}",
                    timeout=10.0,
                )
                if response.status_code == 200:
                    customer = response.json()
                    name = customer.get("first_name", "there")
                    vehicle = customer.get("vehicle")
                    tier = customer.get("loyalty_tier", "Standard")
                    has_issues = customer.get("has_issues", False)
                    notes = customer.get("account_notes", [])

                    # Build response for the agent to use
                    info_parts = [f"Customer found: {name}"]

                    if vehicle:
                        info_parts.append(f"Their vehicle on file is a {vehicle}")

                    if tier == "Platinum":
                        info_parts.append(
                            "They are a Platinum VIP member - give them premium service"
                        )
                    elif tier == "Gold":
                        info_parts.append("They are a Gold member")

                    if has_issues:
                        if "payment_30_days_overdue" in notes:
                            info_parts.append(
                                "WARNING: Their account has an overdue payment - mention this politely"
                            )

                    info_parts.append(
                        "Greet them by name and confirm the vehicle if known"
                    )

                    return ". ".join(info_parts)
        except Exception as e:
            logger.error(f"Customer lookup failed: {e}")

        return f"Phone number {phone} recorded. Policy verification started."

    @function_tool()
    async def save_accident_location(self, location: str) -> str:
        """Save the accident location."""
        logger.info(f"[TOOL CALLED] save_accident_location(location={location})")
        await self._update_session("location", location)
        return f"Location recorded: {location}"

    @function_tool()
    async def save_damage_description(self, damage: str) -> str:
        """Save the damage description. This triggers AI damage analysis in the background."""
        logger.info(f"[TOOL CALLED] save_damage_description(damage={damage})")
        await self._update_session("damage", damage)
        return f"Damage description recorded. Analysis started."

    @function_tool()
    async def save_zip_code(self, zip_code: str) -> str:
        """Save the ZIP code. This triggers repair shop search in the background."""
        logger.info(f"[TOOL CALLED] save_zip_code(zip_code={zip_code})")
        await self._update_session("zip", zip_code)
        return f"ZIP code {zip_code} recorded. Finding nearby repair shops."

    @function_tool()
    async def save_other_party_info(self, involved: bool, info: str = "") -> str:
        """Save information about other vehicles/parties involved."""
        logger.info(
            f"[TOOL CALLED] save_other_party_info(involved={involved}, info={info})"
        )
        await self._update_session("other_party", info if involved else "none")
        return "Other party information recorded."

    @function_tool()
    async def submit_claim(
        self,
        phone: str,
        location: str,
        damage_description: str,
        zip_code: str,
        other_vehicles_involved: bool = False,
        other_party_info: str = "",
    ) -> str:
        """Submit the final insurance claim. Call this ONLY after all information is collected."""
        logger.info(
            f"[TOOL CALLED] submit_claim(phone={phone}, location={location}, damage={damage_description}, zip={zip_code})"
        )

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(
                    f"{API_URL}/api/claims",
                    json={
                        "claim_data": {
                            "phone": phone,
                            "location": location,
                            "damage": damage_description,
                            "zip": zip_code,
                            "other_party": other_party_info
                            if other_vehicles_involved
                            else None,
                        }
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                result = response.json()
                claim_id = result.get("claim_id", "CLM-PENDING")
                logger.info(f"Claim submitted successfully: {claim_id}")
                return f"Claim submitted successfully. The claim number is {claim_id}."
        except Exception as e:
            logger.error(f"Failed to submit claim: {e}")
            return "I've recorded your claim information. You'll receive your claim number shortly via text message."


async def entrypoint(ctx: JobContext):
    """Main entry point for the voice agent."""
    logger.info(f"Agent connecting to room: {ctx.room.name}")

    # Connect to the room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Check keys
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY is missing! Agent will fail.")

    logger.info("Using OpenAI TTS")
    tts_provider = openai.TTS(
        model="gpt-4o-mini-tts",
        voice="marin",
    )

    # Create the agent session
    logger.info("Initializing AgentSession with OpenAI LLM...")
    session = AgentSession(
        stt=openai.STT(),
        llm=openai.LLM(
            model="gpt-4o",
        ),
        tts=tts_provider,
        vad=silero.VAD.load(),
    )

    # Create agent instance with room name for session updates
    agent = InsuranceAgent(room_name=ctx.room.name)

    # Start the session
    await session.start(room=ctx.room, agent=agent)
    agent.set_session(session)  # Pass session to agent for speaking errors
    logger.info("Session started successfully")

    # Agent speaks first with welcome message
    await session.say(
        "Hi, this is Alex from SafeDrive Insurance. I understand you need to file a claim. "
        "First things first, are you and everyone involved safe?",
        allow_interruptions=True,
    )
    logger.info("Welcome message sent")


async def request_fnc(ctx):
    """Accept all job requests."""
    logger.info(f"Received job request for room: {ctx.room.name}")
    await ctx.accept()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            request_fnc=request_fnc,
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
            ws_url=os.getenv("LIVEKIT_URL"),
        )
    )
