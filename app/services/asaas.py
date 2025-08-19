from __future__ import annotations
import httpx
from typing import Dict, Any
from app.config import settings

class AsaasError(RuntimeError):
    pass

async def create_payment_link(
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    value: float,
    description: str,
) -> Dict[str, Any]:
    """
    Cria pagamento simples no Asaas e retorna o link de checkout.
    Ajuste conforme sua conta (customer creation, etc.).
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "access_token": "ASAAS_API_KEY",
    }
    payload = {
        "billingType": "UNDEFINED",
        "chargeType": "DETACHED",
        "value": 5,
        "description": "Consulta Médica escription",
        "dueDateLimitDays": 10,
    }
    async with httpx.AsyncClient(
        base_url=settings.asaas_base_url,
        timeout=settings.request_timeout_seconds,
        headers=headers,
    ) as client:
        r = await client.post("/payments", json=payload)
        if r.status_code not in (200, 201):
            raise AsaasError(f"{r.status_code}: {r.text}")
        data = r.json()
        return {
            "paymentId": data.get("id"),
            "invoiceUrl": data.get("invoiceUrl") or data.get("bankSlipUrl") or data.get("invoiceUrl"),
        }
