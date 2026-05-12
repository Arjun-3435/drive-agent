from langchain_groq import ChatGroq
from langchain_core.messages import trim_messages, SystemMessage, AIMessage, ToolMessage
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

trimmer = trim_messages(
    max_tokens=10,
    strategy="last",
    token_counter=len,
    include_system=True,
    allow_partial=False,
    start_on="human",
)

def state_modifier(state):
    messages = trimmer.invoke(state["messages"])

    # Remove orphaned ToolMessages at the start
    # (tool result with no preceding AI tool_call → Groq rejects this)
    while messages and isinstance(messages[0], ToolMessage):
        messages = messages[1:]

    # Remove trailing AIMessage that has tool_calls but no following ToolMessage
    # (AI called a tool but result was trimmed away → also breaks Groq)
    while messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        messages = messages[:-1]

    return [SystemMessage(content=SYSTEM_PROMPT)] + messages

agent = create_react_agent(
    model=llm,
    tools=tools,
    checkpointer=memory,
    state_modifier=state_modifier,
)

def get_agent_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}