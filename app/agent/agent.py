from __future__ import annotations

import re
from typing import Dict, Any, Tuple, Optional

from cachetools import TTLCache

from app.security.guardrails import looks_like_injection
from app.agent.state import AgentVars
from app.services import klingo
from app.services.asaas import create_payment_link
from app.utils.validators import (
    sanitize_digits,
    is_valid_phone,
    is_valid_cpf,
    to_iso_date,
)
from app.utils.filters import filter_slots

__all__ = ["agent_controller"]

# -----------------------------------------------------------------------------
# Cache (reduz custo de API): agenda reduzida por 60s
# -----------------------------------------------------------------------------
_agenda_cache: TTLCache = TTLCache(maxsize=1, ttl=60)

# -----------------------------------------------------------------------------
# Helpers de parsing e formatação
# -----------------------------------------------------------------------------
YES_WORDS = {"sim", "claro", "ok", "pode", "confirmo", "isso", "quero", "vamos"}
NO_WORDS = {"nao", "não", "no", "negativo", "prefiro não", "depois"}


def normalize(t: str) -> str:
    return (t or "").strip().lower()


def is_yes(t: str) -> bool:
    n = normalize(t)
    return any(w in n for w in YES_WORDS)


def is_no(t: str) -> bool:
    n = normalize(t)
    return any(w in n for w in NO_WORDS)


def iso_to_br(date_iso: str) -> str:
    """yyyy-mm-dd -> dd/mm/yyyy"""
    if not date_iso or len(date_iso) != 10:
        return date_iso
    y, m, d = date_iso.split("-")
    return f"{d}/{m}/{y}"


def extract_doctor(text: str, doctors: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """
    Seleciona médico por id (se usuário digitar) ou por substring do nome.
    Nunca exibimos/solicitamos ids, mas aceitamos se o usuário enviar.
    """
    txt = normalize(text)

    # Aceita id se o usuário enviar espontaneamente (não mostramos)
    for mid in re.findall(r"\b(\d{1,6})\b", txt):
        if mid in doctors:
            return mid, doctors[mid]["doctor_name"]

    # Por nome (substring), tolerando "dr"/"dra"
    for did, d in doctors.items():
        name = normalize(d["doctor_name"])
        name_clean = (
            name.replace("dr ", "")
            .replace("dra ", "")
            .replace("dr.", "")
            .replace("dra.", "")
        )
        if name in txt or name_clean in txt:
            return did, d["doctor_name"]
        if any(part and part in name for part in txt.split()):
            return did, d["doctor_name"]

    return None


DATE_RE_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
DATE_RE_BR = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2})\b")


def extract_date(text: str) -> Optional[str]:
    m = DATE_RE_ISO.search(text) or DATE_RE_BR.search(text)
    if not m:
        return None
    return to_iso_date(m.group(1))


def extract_time(text: str) -> Optional[str]:
    mt = TIME_RE.search(text)
    if not mt:
        return None
    h, mm = mt.group(1).split(":")
    return f"{int(h):02d}:{mm}"


def parse_sex(text: str) -> Optional[str]:
    t = normalize(text)
    if any(x in t for x in ["feminino", "mulher", "femea", "fêmea"]) or t == "f":
        return "F"
    if any(x in t for x in ["masculino", "homem", "macho"]) or t == "m":
        return "M"
    return None


def bullets(title: str, items: list[str]) -> str:
    if not items:
        return title + "\n- (sem opções disponíveis)"
    lines = "\n".join([f"- {it}" for it in items])
    return f"{title}\n{lines}"


# -----------------------------------------------------------------------------
# Agenda & slots (com filtro de regras de negócio)
# -----------------------------------------------------------------------------
async def get_reduced_agenda_cached() -> Dict[str, Any]:
    """Busca agenda na Klingo e aplica filtro de regras. Usa cache TTL."""
    if "reduced" in _agenda_cache:
        return _agenda_cache["reduced"]
    payload = await klingo.get_agenda()
    reduced = filter_slots(payload)  # já filtra hoje, domingos e feriados; top 3 datas / 5 horários
    _agenda_cache["reduced"] = reduced
    return reduced


def render_doctor_options(doctors: Dict[str, Any]) -> str:
    names = [d["doctor_name"] for _, d in doctors.items()]
    # remove duplicados preservando ordem
    names = list(dict.fromkeys(names))
    return bullets("Médicos:", names[:10])


def list_dates_for_doc(doc: Dict[str, Any]) -> list[str]:
    return [iso_to_br(e["date"]) for e in doc.get("dates", [])][:3]


def list_times_for_doc_date(doc: Dict[str, Any], date_iso: str) -> list[str]:
    for e in doc.get("dates", []):
        if e["date"] == date_iso:
            return [t["time"] for t in e.get("times", [])][:5]
    return []


def find_slot_id(doc: Dict[str, Any], date_iso: str, time_: str) -> Optional[str]:
    for e in doc.get("dates", []):
        if e["date"] == date_iso:
            for t in e.get("times", []):
                if t["time"] == time_:
                    return t["slot_id"]
    return None


# -----------------------------------------------------------------------------
# Mensagens padrão
# -----------------------------------------------------------------------------
GREETING = (
    "Olá, eu sou o Otinho, assistente de agendamento da OtorrinoMed.\n"
    "Você tem preferência por algum médico?"
)

# -----------------------------------------------------------------------------
# Steps da FSM
# -----------------------------------------------------------------------------
async def step_start(state: AgentVars) -> str:
    state.current_step = "ASK_DOCTOR_PREFERENCE"
    return GREETING


async def step_ask_doctor_preference(state: AgentVars, user_text: str) -> str:
    txt = normalize(user_text)

    reduced = await get_reduced_agenda_cached()
    doctors = reduced.get("doctors", {})
    state.agenda_reduced = reduced
    state.doctors_cache = doctors

    # Não tem preferência
    if is_no(user_text) or "primeira vez" in txt or "sem preferência" in txt or "sem preferencia" in txt:
        state.current_step = "ASK_DOCTOR"
        return f"{render_doctor_options(doctors)}\n\nQual médico você prefere?"

    # Informou um nome (ou id por conta própria)
    choice = extract_doctor(user_text, doctors)
    if choice:
        did, dname = choice
        state.doctor_id, state.doctor_name = did, dname
        doc = doctors[did]
        dates = list_dates_for_doc(doc)
        state.current_step = "ASK_DATE"
        title = f"Datas para {dname}:"
        return f"{bullets(title, dates)}\n\nQual data você prefere?"

    # Peça o médico explicitamente
    state.current_step = "ASK_DOCTOR"
    return f"{render_doctor_options(doctors)}\n\nQual médico você prefere?"


async def step_ask_doctor(state: AgentVars, user_text: str) -> str:
    doctors = state.doctors_cache or state.agenda_reduced.get("doctors", {})
    choice = extract_doctor(user_text, doctors)
    if not choice:
        return f"Não identifiquei o médico.\n{render_doctor_options(doctors)}\n\nQual médico você prefere?"

    did, dname = choice
    state.doctor_id, state.doctor_name = did, dname
    doc = doctors[did]
    dates = list_dates_for_doc(doc)
    state.current_step = "ASK_DATE"
    title = f"Datas para {dname}:"
    return f"{bullets(title, dates)}\n\nQual data você prefere?"


async def step_ask_date(state: AgentVars, user_text: str) -> str:
    date_iso = extract_date(user_text)
    if not date_iso:
        doctors = state.doctors_cache or state.agenda_reduced.get("doctors", {})
        doc = doctors.get(state.doctor_id or "")
        dates = list_dates_for_doc(doc or {})
        title = f"Datas para {state.doctor_name}:"
        return "Por favor, informe a data escolhida.\n" + bullets(title, dates)

    state.appoitment_date = date_iso

    # Mostra horários da data escolhida
    doctors = state.doctors_cache or state.agenda_reduced.get("doctors", {})
    doc = doctors.get(state.doctor_id or "")
    times = list_times_for_doc_date(doc or {}, date_iso)
    state.current_step = "ASK_TIME"
    title = f"Horários em {iso_to_br(date_iso)}:"
    return f"{bullets(title, times)}\n\nQual horário você prefere?"


async def step_ask_time(state: AgentVars, user_text: str) -> str:
    time_ = extract_time(user_text)
    if not time_:
        doctors = state.doctors_cache or state.agenda_reduced.get("doctors", {})
        doc = doctors.get(state.doctor_id or "")
        times = list_times_for_doc_date(doc or {}, state.appoitment_date or "")
        title = f"Horários em {iso_to_br(state.appoitment_date or '')}:"
        return "Por favor, escolha um horário válido.\n" + bullets(title, times)

    doctors = state.doctors_cache or state.agenda_reduced.get("doctors", {})
    doc = doctors.get(state.doctor_id or "")
    if not doc:
        state.current_step = "ASK_DOCTOR"
        return "Perdi a referência do médico selecionado. Qual médico você prefere?"

    slot_id = find_slot_id(doc, state.appoitment_date or "", time_)
    if not slot_id:
        times = list_times_for_doc_date(doc, state.appoitment_date or "")
        title = f"Horários em {iso_to_br(state.appoitment_date or '')}:"
        return "Esse horário não está disponível.\n" + bullets(title, times) + "\n\nQual horário você prefere?"

    state.appoitment_hour = time_
    state.appoitment_id = slot_id  # interno (não exibido)
    state.current_step = "ASK_IDENTIFY"
    return (
        "Perfeito! Agora, para verificar seu cadastro, me informe:\n"
        "- Data de nascimento (yyyy-mm-dd)\n"
        "- Telefone (somente números)"
    )


async def step_ask_identify(state: AgentVars, user_text: str) -> str:
    date_iso = extract_date(user_text)
    phone = sanitize_digits(user_text)

    if date_iso:
        state.user_birthday_date = date_iso
    if is_valid_phone(phone):
        state.user_phone = phone

    if not state.user_birthday_date:
        return "Qual é sua data de nascimento? (yyyy-mm-dd ou dd/mm/aaaa)"
    if not state.user_phone:
        return "Qual é seu telefone com DDD? (somente números, ex.: 11987654321)"

    # Tenta identificar
    try:
        ident = await klingo.identify_user(state.user_phone, state.user_birthday_date)
        token = ident.get("access_token")
        if token:
            state.user_token = token
            state.current_step = "ASK_CONFIRM_APPOINTMENT"
            return (
                "Cadastro encontrado! Posso confirmar o agendamento?\n"
                f"- Médico: {state.doctor_name}\n"
                f"- Data: {iso_to_br(state.appoitment_date or '')}\n"
                f"- Horário: {state.appoitment_hour}\n"
                "- Confirma? (sim/não)"
            )
    except Exception:
        # segue cadastro
        pass

    state.current_step = "ASK_REGISTER"
    return (
        "Não localizei seu cadastro. Por favor, envie:\n"
        "- Nome completo\n"
        "- E-mail\n"
        "- CPF (somente números)"
    )


async def step_ask_register(state: AgentVars, user_text: str) -> str:
    # Extrai dados possíveis
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w{2,}", user_text)
    cpf_digits = re.findall(r"\d{11}", user_text)
    sex_guess = parse_sex(user_text)
    name_guess = None

    cleaned = re.sub(r"[\w\.-]+@[\w\.-]+\.\w{2,}", "", user_text)
    cleaned = re.sub(r"\d", "", cleaned).strip()
    if len(cleaned.split()) >= 2:
        name_guess = cleaned

    if email_match:
        state.user_email = email_match.group(0)
    if cpf_digits:
        doc = cpf_digits[0]
        if is_valid_cpf(doc):
            state.user_document = doc
    if name_guess:
        state.user_fullname = name_guess
    if sex_guess:
        state.user_sex = sex_guess

    # Campos obrigatórios
    if not state.user_fullname:
        return "Qual é o seu nome completo?"
    if not state.user_email or "@" not in state.user_email:
        return "Qual é o seu e-mail?"
    if not state.user_document or not is_valid_cpf(state.user_document):
        return "Qual é o seu CPF? (somente números)"
    if state.user_sex not in ("M", "F"):
        return "Para finalizar, qual é o seu sexo? (responda 'M' para Masculino ou 'F' para Feminino)"

    # Cadastro + login
    reg = await klingo.register_user(
        fullname=state.user_fullname,
        email=state.user_email,
        cpf=state.user_document,
        dt_nasc_iso=state.user_birthday_date or "",
        phone=state.user_phone or "",
        sexo=state.user_sex,
    )
    uid = reg.get("id")
    if not uid:
        return "Não consegui concluir o cadastro agora. Podemos tentar novamente em instantes?"

    login = await klingo.login_user(int(uid))
    token = login.get("access_token")
    if not token:
        return "Cadastro criado, mas o login falhou. Tente novamente mais tarde, por favor."

    state.user_token = token
    state.current_step = "ASK_CONFIRM_APPOINTMENT"
    return (
        "Cadastro criado! Posso confirmar o agendamento?\n"
        f"- Médico: {state.doctor_name}\n"
        f"- Data: {iso_to_br(state.appoitment_date or '')}\n"
        f"- Horário: {state.appoitment_hour}\n"
        "- Confirma? (sim/não)"
    )


async def step_ask_confirm_appointment(state: AgentVars, user_text: str) -> str:
    if is_no(user_text):
        state.current_step = "END"
        return "Tudo bem! Se preferir, posso buscar outros horários. É só me dizer. 😊"
    if not is_yes(user_text):
        return "Por favor, responda com 'sim' ou 'não'."

    if not (state.user_token and state.appoitment_id):
        state.current_step = "ASK_IDENTIFY"
        return "Estou quase lá! Preciso validar seus dados para prosseguir."

    _ = await klingo.create_appointment(state.user_token, state.appoitment_id)
    state.current_step = "ASK_PREPAY"
    return (
        "Agendamento confirmado! ✅\n"
        f"- Médico: {state.doctor_name}\n"
        f"- Data: {iso_to_br(state.appoitment_date or '')}\n"
        f"- Horário: {state.appoitment_hour}\n\n"
        "Deseja antecipar o pagamento da consulta? (sim/não)"
    )


async def step_ask_prepay(state: AgentVars, user_text: str) -> str:
    if is_no(user_text):
        state.current_step = "END"
        return "Perfeito! Seu horário está confirmado. Até breve e boa recuperação!"
    if not is_yes(user_text):
        return "Por favor, responda com 'sim' ou 'não'."

    pay = await create_payment_link(
        customer_name=state.user_fullname or "Paciente",
        customer_email=state.user_email or "paciente@example.com",
        customer_phone=state.user_phone or "",
        value=200.0,
        description="Consulta particular OtorrinoMed",
    )
    state.user_payment_link = pay.get("invoiceUrl")
    state.current_step = "END"
    return (
        "Aqui está seu link de pagamento antecipado:\n"
        f"- {state.user_payment_link}\n\n"
        "Assim que o pagamento for confirmado, eu aviso você. Foi um prazer ajudar! 🙌"
    )


# -----------------------------------------------------------------------------
# Controlador principal (FSM)
# -----------------------------------------------------------------------------
async def agent_controller(state: AgentVars, user_text: str) -> str:
    # Proteção simples contra injection
    if looks_like_injection(user_text):
        user_text = ""

    step = state.current_step

    if step == "START":
        return await step_start(state)
    if step == "ASK_DOCTOR_PREFERENCE":
        return await step_ask_doctor_preference(state, user_text)
    if step == "ASK_DOCTOR":
        return await step_ask_doctor(state, user_text)
    if step == "ASK_DATE":
        return await step_ask_date(state, user_text)
    if step == "ASK_TIME":
        return await step_ask_time(state, user_text)
    if step == "ASK_IDENTIFY":
        return await step_ask_identify(state, user_text)
    if step == "ASK_REGISTER":
        return await step_ask_register(state, user_text)
    if step == "ASK_CONFIRM_APPOINTMENT":
        return await step_ask_confirm_appointment(state, user_text)
    if step == "ASK_PREPAY":
        return await step_ask_prepay(state, user_text)

    # END ou estado desconhecido: reinicia educadamente
    state.current_step = "ASK_DOCTOR_PREFERENCE"
    return GREETING
