from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, Dict, Any

class AgentVars(BaseModel):
    # FSM
    # START -> ASK_DOCTOR_PREFERENCE -> ASK_DOCTOR -> ASK_DATE -> ASK_TIME -> ASK_IDENTIFY -> ASK_REGISTER -> ASK_CONFIRM_APPOINTMENT -> ASK_PREPAY -> END
    current_step: str = "START"
    last_bot_message: Optional[str] = None

    # usuário
    user_id: Optional[str] = None
    user_fullname: Optional[str] = None
    user_phone: Optional[str] = None
    user_email: Optional[str] = None
    user_document: Optional[str] = None
    user_birthday_date: Optional[str] = None  # yyyy-mm-dd
    user_token: Optional[str] = None
    user_payment_link: Optional[str] = None
    user_sex: Optional[str] = None  # "M" ou "F"

    # médico & agenda
    doctor_id: Optional[str] = None     # usado só internamente
    doctor_name: Optional[str] = None
    appoitment_id: Optional[str] = None # slot_id da Klingo (interno)
    appoitment_date: Optional[str] = None  # yyyy-mm-dd
    appoitment_hour: Optional[str] = None  # hh:mm

    # caches
    doctors_cache: Dict[str, Any] = {}     # {doctor_id: {...}}
    agenda_reduced: Dict[str, Any] = {}    # {"doctors": ...}
