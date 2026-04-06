"""
Twilio personalization webhook for ElevenLabs.

Called automatically when an inbound Twilio call arrives. ElevenLabs
sends caller_id, agent_id, called_number, call_sid. We look up the
caller in our DB and return dynamic_variables + conversation overrides.

Hybrid silent auth:
  - Known number → partial auth (only TC Kimlik last 4 needed)
  - Unknown number → full KBA (3 fields)

Reference:
  https://elevenlabs.io/docs/eleven-agents/customization/personalization/twilio-personalization
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent.logging_config import get_logger
from api.models import Application, Citizen, get_db

logger = get_logger(__name__)

router = APIRouter(tags=["twilio"])


class TwilioInboundRequest(BaseModel):
    """Request from ElevenLabs when a Twilio inbound call arrives."""
    caller_id: str
    agent_id: str
    called_number: str
    call_sid: str


@router.post("/twilio/inbound")
def twilio_personalization(
    request: TwilioInboundRequest,
    db: Session = Depends(get_db),
):
    """Personalize conversation based on caller phone number.

    Returns ElevenLabs conversation_initiation_client_data format.
    If caller is recognized, returns their name and partial auth flag.
    If not recognized, returns default greeting.
    """
    caller = request.caller_id
    logger.info(f"Twilio inbound | caller={caller} | call_sid={request.call_sid}")

    # Look up citizen by phone number
    citizen = db.query(Citizen).filter(Citizen.phone_number == caller).first()

    if citizen:
        # Known caller — get their latest application for context
        latest_app = (
            db.query(Application)
            .filter(Application.citizen_id == citizen.id)
            .order_by(Application.id.desc())
            .first()
        )

        logger.info(f"Twilio inbound | recognized caller | citizen={citizen.first_name}")

        return {
            "type": "conversation_initiation_client_data",
            "dynamic_variables": {
                "caller_name": citizen.first_name,
                "caller_known": "true",
                "citizen_id": str(citizen.id),
                "language_preference": citizen.language_preference,
            },
            "conversation_config_override": {
                "agent": {
                    "first_message": (
                        f"Merhaba {citizen.first_name}, Vatandas Hizmetleri'ne hos geldiniz. "
                        f"Kimliginizi dogrulamak icin TC Kimlik numaranizin son dort hanesini soyler misiniz?"
                    ),
                    "language": citizen.language_preference,
                },
            },
        }

    else:
        # Unknown caller — standard greeting, full KBA required
        logger.info(f"Twilio inbound | unknown caller | caller={caller}")

        return {
            "type": "conversation_initiation_client_data",
            "dynamic_variables": {
                "caller_known": "false",
            },
        }
