import json
import asyncio
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from backend.schemas import ChatRequest, ChatResponse
from backend.agent import agent, get_agent_config

app = FastAPI(
    title="Drive Agent API",
    description="Conversational AI agent for Google Drive file discovery",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "drive-agent-backend"}


# ── Streaming chat ─────────────────────────────────────────────────────────────

async def event_stream(session_id: str, message: str) -> AsyncIterator[str]:
    """
    Yield Server-Sent Events as the LangGraph agent streams its response.

    Event types:
      {"type": "tool_start",  "tool": "<name>", "input": {...}}
      {"type": "tool_end",    "tool": "<name>", "output": "..."}
      {"type": "token",       "content": "..."}
      {"type": "done"}
      {"type": "error",       "content": "..."}
    """
    config = get_agent_config(session_id)
    inputs = {"messages": [HumanMessage(content=message)]}

    try:
        async for event in agent.astream_events(inputs, config=config, version="v2"):
            kind = event["event"]

            # ── LLM token ────────────────────────────────────────────────────
            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                content = getattr(chunk, "content", "") if chunk else ""
                if content:
                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                    await asyncio.sleep(0)   # flush to client

            # ── Tool invoked ──────────────────────────────────────────────────
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event["data"].get("input", {})
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name, 'input': tool_input})}\n\n"
                await asyncio.sleep(0)

            # ── Tool finished ─────────────────────────────────────────────────
            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                raw_output = event["data"].get("output", "")
                # Try to parse as JSON for structured pass-through
                try:
                    output = json.loads(str(raw_output))
                except Exception:
                    output = str(raw_output)
                yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name, 'output': output})}\n\n"
                await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming endpoint — returns SSE events."""
    return StreamingResponse(
        event_stream(req.session_id, req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Non-streaming fallback ─────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Simple non-streaming endpoint — returns full response at once."""
    config = get_agent_config(req.session_id)
    inputs = {"messages": [HumanMessage(content=req.message)]}

    try:
        result = await agent.ainvoke(inputs, config=config)
        messages = result.get("messages", [])
        # Last message from the AI
        ai_msgs = [m for m in messages if isinstance(m, AIMessage)]
        response_text = ai_msgs[-1].content if ai_msgs else "No response generated."
        return ChatResponse(session_id=req.session_id, response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Conversation history ───────────────────────────────────────────────────────

@app.get("/history/{session_id}")
async def get_history(session_id: str):
    """Return the conversation history for a session."""
    from langgraph.checkpoint.memory import MemorySaver
    config = get_agent_config(session_id)
    try:
        state = agent.get_state(config)
        messages = state.values.get("messages", [])
        history = []
        for m in messages:
            if isinstance(m, HumanMessage):
                history.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage) and m.content:
                history.append({"role": "assistant", "content": m.content})
        return {"session_id": session_id, "history": history}
    except Exception:
        return {"session_id": session_id, "history": []}


@app.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Clear conversation for a session (new session ID achieves same result)."""
    return {"message": "Start a new session to clear history.", "session_id": session_id}