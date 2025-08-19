from __future__ import annotations
import httpx
from typing import Any, Dict
from app.config import settings

HEADERS = {
    "accept": "application/json",
    "X-APP-TOKEN": settings.klingo_app_token,
}

class KlingoError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"Klingo API error {status}: {detail}")
        self.status = status
        self.detail = detail

async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.klingo_base_url,
        timeout=settings.request_timeout_seconds,
        headers=HEADERS,
    )

async def get_agenda(especialidade: str = "225275", exame: str = "1376", plano: str = "1") -> Dict[str, Any]:
    url = f"/agenda/horarios?especialidade={especialidade}&exame={exame}&plano={plano}"
    async with await _client() as client:
        r = await client.get(url)
        if r.status_code != 200:
            raise KlingoError(r.status_code, r.text)
        return r.json()

async def identify_user(phone: str, birthday_iso: str, cpf: str | None = "") -> Dict[str, Any]:
    payload = {"telefone": phone, "dt_nascimento": birthday_iso, "cpf": cpf or ""}
    async with await _client() as client:
        r = await client.post("/paciente/identificar", json=payload)
        if r.status_code != 200:
            raise KlingoError(r.status_code, r.text)
        return r.json()

async def register_user(
    fullname: str,
    email: str,
    cpf: str,
    dt_nasc_iso: str,
    phone: str,
    sexo: str = "M",  # <-- novo parâmetro (default M)
) -> Dict[str, Any]:
    # garante valores aceitos pela Klingo: "M" ou "F"
    sexo = "M" if str(sexo).upper() not in ("M", "F") else str(sexo).upper()

    payload = {
        "paciente": {
            "id_origem": 1234,
            "nome": fullname,
            "sexo": sexo,  # <-- valor válido
            "dt_nasc": dt_nasc_iso,
            "mae": "NA",
            "docs": {"cpf": cpf, "rg": ""},
            "contatos": {"celular": phone, "telefone": "", "email": email},
            "endereco": {
                "cep": "00000000",
                "endereco": "",
                "numero": "",
                "complemento": "",
                "bairro": "",
                "cidade": "",
                "uf": "BA",
            },
            "convenio": {
                "id": "01",
                "reg_ans": "",
                "matricula": "",
                "validade": "2030-12-31",
                "id_plano": "01",
            },
        }
    }
    # alguns ambientes usam outro token para register/login; se houver, usa-o
    headers = {
        "accept": "application/json",
        "X-APP-TOKEN": getattr(settings, "klingo_register_token", None) or settings.klingo_app_token,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(
        base_url=settings.klingo_base_url,
        timeout=settings.request_timeout_seconds,
        headers=headers,
    ) as client:
        r = await client.post("/externo/register", json=payload)
        if r.status_code != 200:
            raise KlingoError(r.status_code, r.text)
        return r.json()


async def login_user(user_id: int) -> Dict[str, Any]:
    headers = {
        "accept": "application/json",
        "X-APP-TOKEN": getattr(settings, "klingo_register_token", None) or settings.klingo_app_token,
        "Content-Type": "application/json",
    }
    async with await _client() as client:
        # sobrescreve headers na chamada
        r = await client.post("/externo/login", json={"id": user_id}, headers=headers)
        if r.status_code != 200:
            raise KlingoError(r.status_code, r.text)
        return r.json()


async def create_appointment(token: str, slot_id: str) -> Dict[str, Any]:
    headers = dict(HEADERS)
    headers["Authorization"] = f"Bearer {token}"
    payload = {
        "procedimento": "1000",
        "id": slot_id,  # formato completo vindo de horarios.keys()
        "plano": 1,
        "email": True,
        "teleatendimento": False,
        "revisao": False,
        "ordem_chegada": False,
        "lista": [123],
        "solicitante": {
            "conselho": "CRM",
            "uf": "BA",
            "numero": 17137,
            "nome": "Dr. Carlos Borba",
            "cbos": "225265",
        },
        "confirmado": "",
        "id_externo": "",
        "obs": "Agendado pelo Agente de IA",
        "duracao": 10,
        "id_ampliar": 0,
    }
    async with httpx.AsyncClient(
        base_url=settings.klingo_base_url,
        timeout=settings.request_timeout_seconds,
        headers=headers,
    ) as client:
        r = await client.post("/agenda/horario", json=payload)
        if r.status_code != 200:
            raise KlingoError(r.status_code, r.text)
        return r.json()
