from __future__ import annotations
import sys
import asyncio
import streamlit as st
from app.db.session import engine
from app.db import models
from app.agent.state import AgentVars
from app.agent.agent import agent_controller

# ---- FIX para Windows (evita conflitos de event loop) ----
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
    except Exception:
        pass

st.set_page_config(page_title="Otinho – OtorrinoMed", page_icon="👂", layout="centered")

# --------- INIT DB (apenas 1x por processo) ----------
async def _init_db_async():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

@st.cache_resource
def init_db_once() -> bool:
    asyncio.run(_init_db_async())
    return True

init_db_once()
# ------------------------------------------------------

st.title("💬 Otinho – Assistente de Agendamento")
st.caption("Agende sua consulta com o Otinho.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "vars" not in st.session_state:
    st.session_state.vars = AgentVars()

# Render histórico
for msg in st.session_state.messages:
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        st.markdown(msg["content"])

prompt = st.chat_input("Digite sua mensagem...")

async def handle_user_input(user_text: str):
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("assistant"):
        reply = await agent_controller(st.session_state.vars, user_text)  # <-- vars (com 's') + parênteses ok
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.markdown(reply)

if prompt:
    asyncio.run(handle_user_input(prompt))
