from __future__ import annotations
import re
from datetime import datetime

CPF_REGEX = re.compile(r"^\d{11}$")
PHONE_REGEX = re.compile(r"^\d{11,}$")
DATE_ISO_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")

BR_HOLIDAYS_2025 = {
    "2025-01-01",  # Confraternização Universal
    "2025-04-18",  # Sexta-feira Santa
    "2025-04-21",  # Tiradentes
    "2025-05-01",  # Dia do Trabalhador
    "2025-09-07",  # Independência
    "2025-10-12",  # Nossa Senhora Aparecida
    "2025-11-02",  # Finados
    "2025-11-15",  # Proclamação da República
    "2025-12-25",  # Natal
}

def sanitize_digits(value: str) -> str:
    return re.sub(r"\D+", "", value or "")

def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_REGEX.match(sanitize_digits(phone)))

def is_valid_cpf(cpf: str) -> bool:
    cpf = sanitize_digits(cpf)
    if not CPF_REGEX.match(cpf):
        return False
    # validação de dígitos (simples)
    def calc_dv(cpf_slice: str) -> int:
        s = sum(int(d) * w for d, w in zip(cpf_slice, range(len(cpf_slice) + 1, 1, -1)))
        r = (s * 10) % 11
        return 0 if r == 10 else r
    return calc_dv(cpf[:9]) == int(cpf[9]) and calc_dv(cpf[:10]) == int(cpf[10])

def to_iso_date(date_str: str) -> str:
    # aceita dd/mm/aaaa ou yyyy-mm-dd
    if DATE_ISO_REGEX.match(date_str):
        return date_str
    try:
        d = datetime.strptime(date_str, "%d/%m/%Y").date()
        return d.isoformat()
    except Exception:
        raise ValueError("Data inválida; use dd/mm/aaaa ou yyyy-mm-dd")

def is_sunday(date_iso: str) -> bool:
    return datetime.fromisoformat(date_iso).weekday() == 6  # 0=mon .. 6=sun

def is_today(date_iso: str) -> bool:
    return datetime.fromisoformat(date_iso).date() == datetime.utcnow().date()

def is_br_holiday(date_iso: str) -> bool:
    return date_iso in BR_HOLIDAYS_2025
