from langchain_groq import ChatGroq
from langchain_core.messages import trim_messages, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from backend.config import settings
from backend.prompts import SYSTEM_PROMPT
from backend.tools import search_drive_files, list_all_files, get_file_details

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.groq_api_key,
    temperature=0.1,
    max_tokens=1024,
)

tools = [search_drive_files, list_all_files, get_file_details]
memory = MemorySaver()

# Trimmer — keeps last 10 messages (5 turns) to cap context size
trimmer = trim_messages(
    max_tokens=10,          # 10 messages max (token_counter=len counts messages, not tokens)
    strategy="last",
    token_counter=len,
    include_system=True,
    allow_partial=False,
    start_on="human",
)

def state_modifier(state):
    """Prepend system prompt + trim history — combined into one modifier."""
    messages = trimmer.invoke(state["messages"])
    return [SystemMessage(content=SYSTEM_PROMPT)] + messages

agent = create_react_agent(
    model=llm,
    tools=tools,
    checkpointer=memory,
    state_modifier=state_modifier,   # single param only
)

def get_agent_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}