from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import trim_messages

from backend.config import settings
from backend.prompts import SYSTEM_PROMPT
from backend.tools import search_drive_files, list_all_files, get_file_details

# ── LLM ──────────────────────────────────────────────────────────────────────
# llama-3.3-70b-versatile has the best tool-calling support on Groq
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.groq_api_key,
    temperature=0.1,          # low temp → consistent, accurate tool calls
    max_tokens=1024,
)

# ── Tools ─────────────────────────────────────────────────────────────────────
tools = [search_drive_files, list_all_files, get_file_details]

# ── Memory (per-session conversation history) ─────────────────────────────────
memory = MemorySaver()

# ── Agent ─────────────────────────────────────────────────────────────────────
agent = create_react_agent(
    model=llm,
    tools=tools,
    checkpointer=memory,
    state_modifier=SYSTEM_PROMPT,
    # Trim messages before each LLM call
    messages_modifier=trim_messages(
        max_tokens=3000,
        strategy="last",
        token_counter=len,       # rough count by message count
        include_system=True,
        allow_partial=False,
        start_on="human",
    ),
)


def get_agent_config(session_id: str) -> dict:
    """Return LangGraph config for a specific session (thread)."""
    return {"configurable": {"thread_id": session_id}}