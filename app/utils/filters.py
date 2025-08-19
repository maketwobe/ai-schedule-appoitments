from __future__ import annotations
from typing import Any, Dict, List, Tuple
from collections import defaultdict
from app.utils.validators import is_br_holiday, is_sunday, is_today

# Entrada: payload da Klingo /agenda/horarios
# Saída: estrutura reduzida e filtrada

def filter_slots(payload: Dict[str, Any]) -> Dict[str, Any]:
    horarios: List[Dict[str, Any]] = payload.get("horarios", [])
    result: Dict[str, Dict[str, List[Tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))

    # agrega por medico -> data -> [horas]
    for item in horarios:
        date_iso = item.get("data")
        prof = item.get("profissional", {})
        doctor_name = prof.get("nome")
        doctor_id = str(prof.get("id"))
        times: Dict[str, str] = item.get("horarios", {})

        # filtros de data proibida
        if not date_iso or is_today(date_iso) or is_sunday(date_iso) or is_br_holiday(date_iso):
            continue

        # coleta 5 primeiros horários disponíveis da data
        top_times = list(times.items())[:5]  # [(id_completo, "HH:MM"), ...]
        if not top_times:
            continue

        result[(doctor_id, doctor_name)][date_iso].extend(top_times)

    # reduz para top 3 datas por médico, top 5 horários por data (já limitado)
    reduced: Dict[str, Any] = {}
    for (doctor_id, doctor_name), dates_map in result.items():
        dates_sorted = sorted(dates_map.keys())[:3]
        reduced[doctor_id] = {
            "doctor_name": doctor_name,
            "dates": [
                {
                    "date": d,
                    "times": [{"slot_id": sid, "time": t} for sid, t in dates_map[d][:5]],
                }
                for d in dates_sorted
            ],
        }
    return {"doctors": reduced}
