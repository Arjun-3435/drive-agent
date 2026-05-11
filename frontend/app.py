import json
import uuid
import requests
import streamlit as st
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DriveBot — AI File Discovery",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Config ────────────────────────────────────────────────────────────────────
import os
API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Chat container */
.stChatMessage { border-radius: 12px; margin-bottom: 8px; }

/* File card */
.file-card {
    background: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 10px;
    padding: 12px 16px;
    margin: 6px 0;
    transition: border-color 0.2s;
}
.file-card:hover { border-color: #89b4fa; }
.file-card a {
    color: #89b4fa;
    text-decoration: none;
    font-weight: 600;
    font-size: 15px;
}
.file-card a:hover { text-decoration: underline; }
.file-meta {
    color: #a6adc8;
    font-size: 12px;
    margin-top: 4px;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}
.file-type-badge {
    display: inline-block;
    background: #313244;
    color: #cdd6f4;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 20px;
    margin-right: 6px;
}
.tool-indicator {
    background: #1e1e2e;
    border-left: 3px solid #a6e3a1;
    padding: 6px 12px;
    border-radius: 0 6px 6px 0;
    color: #a6e3a1;
    font-size: 13px;
    margin: 4px 0;
    font-family: monospace;
}
.result-count {
    color: #a6e3a1;
    font-weight: 600;
    margin: 8px 0 4px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []   # {role, content, files?, tool_events?}
if "is_loading" not in st.session_state:
    st.session_state.is_loading = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def render_file_card(f: dict):
    emoji = f.get("emoji", "📎")
    name = f.get("name", "Untitled")
    link = f.get("link", "#")
    ftype = f.get("type", "File")
    modified = f.get("modified", "—")
    size = f.get("size", "—")
    owners = ", ".join(f.get("owners", [])) or "—"

    st.markdown(f"""
    <div class="file-card">
        <div>
            <span class="file-type-badge">{emoji} {ftype}</span>
            <a href="{link}" target="_blank">{name}</a>
        </div>
        <div class="file-meta">
            <span>🕐 {modified}</span>
            <span>💾 {size}</span>
            <span>👤 {owners}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def parse_tool_output(output) -> list[dict]:
    """Extract file list from tool output (dict or JSON string)."""
    if isinstance(output, dict):
        return output.get("files", [])
    if isinstance(output, str):
        try:
            data = json.loads(output)
            return data.get("files", [])
        except Exception:
            pass
    return []


def stream_chat(session_id: str, message: str):
    """
    Generator that yields parsed SSE events from the backend.
    Yields dicts: {type, content?, tool?, input?, output?}
    """
    url = f"{API_URL}/chat/stream"
    payload = {"session_id": session_id, "message": message}

    try:
        with requests.post(url, json=payload, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if line.startswith("data: "):
                    try:
                        yield json.loads(line[6:])
                    except json.JSONDecodeError:
                        pass
    except requests.exceptions.ConnectionError:
        yield {"type": "error", "content": f"Cannot reach backend at {API_URL}. Is it running?"}
    except requests.exceptions.Timeout:
        yield {"type": "error", "content": "Request timed out. The Drive query may have taken too long."}
    except Exception as e:
        yield {"type": "error", "content": str(e)}


TOOL_LABELS = {
    "search_drive_files": "🔍 Searching Drive files...",
    "list_all_files":     "📂 Listing all files...",
    "get_file_details":   "📋 Fetching file details...",
}


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗂️ DriveBot")
    st.markdown("**Conversational AI for Google Drive**")
    st.divider()

    st.markdown("#### 💡 Try asking:")
    examples = [
        "Show me everything in the drive",
        "Find all PDFs",
        "Search for files about finance",
        "Any images in the drive?",
        "Find documents modified last month",
        "Look for spreadsheets with 'budget' in the name",
        "Find files containing the word 'report'",
        "Show me the most recently modified files",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True, key=f"ex_{ex[:20]}"):
            st.session_state["prefill"] = ex

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 New Chat", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()
    with col2:
        st.markdown(
            f"<small style='color:#a6adc8'>Session:<br><code>{st.session_state.session_id[:8]}…</code></small>",
            unsafe_allow_html=True
        )

    st.divider()
    st.markdown(
        "<small style='color:#585b70'>Powered by Groq · LangGraph · Google Drive API</small>",
        unsafe_allow_html=True
    )


# ── Main header ───────────────────────────────────────────────────────────────
st.markdown("## 🗂️ DriveBot — AI File Discovery")
st.markdown("Chat naturally to search, filter, and explore your Google Drive files.")
st.divider()

# ── Render existing messages ──────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # Render tool events if any
        for evt in msg.get("tool_events", []):
            if evt["type"] == "tool_start":
                label = TOOL_LABELS.get(evt["tool"], f"🔧 {evt['tool']}...")
                st.markdown(f'<div class="tool-indicator">{label}</div>', unsafe_allow_html=True)

        # Render text content
        if msg.get("content"):
            st.markdown(msg["content"])

        # Render file results
        files = msg.get("files", [])
        if files:
            st.markdown(f'<div class="result-count">Found {len(files)} file(s):</div>', unsafe_allow_html=True)
            for f in files:
                render_file_card(f)

        if msg.get("error"):
            st.error(msg["error"])


# ── Handle prefill from sidebar buttons ──────────────────────────────────────
prefill = st.session_state.pop("prefill", None)

# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask me to find files… e.g. 'Find all PDFs modified this week'")
if prefill:
    user_input = prefill

if user_input and not st.session_state.is_loading:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.is_loading = True

    with st.chat_message("user"):
        st.markdown(user_input)

    # Stream response
    with st.chat_message("assistant"):
        token_placeholder = st.empty()
        tool_container = st.container()

        accumulated_text = ""
        all_files = []
        tool_events = []
        error_msg = None
        current_tool = None

        for event in stream_chat(st.session_state.session_id, user_input):
            etype = event.get("type")

            if etype == "token":
                accumulated_text += event.get("content", "")
                token_placeholder.markdown(accumulated_text + "▌")

            elif etype == "tool_start":
                current_tool = event.get("tool", "")
                label = TOOL_LABELS.get(current_tool, f"🔧 {current_tool}...")
                tool_events.append(event)
                with tool_container:
                    st.markdown(f'<div class="tool-indicator">{label}</div>', unsafe_allow_html=True)

            elif etype == "tool_end":
                output = event.get("output", {})
                files = parse_tool_output(output)
                if files:
                    all_files.extend(files)
                tool_events.append(event)

            elif etype == "error":
                error_msg = event.get("content", "Unknown error")

            elif etype == "done":
                break

        # Final render
        token_placeholder.markdown(accumulated_text if accumulated_text else "")

        if all_files:
            st.markdown(f'<div class="result-count">Found {len(all_files)} file(s):</div>', unsafe_allow_html=True)
            for f in all_files:
                render_file_card(f)

        if error_msg:
            st.error(f"⚠️ {error_msg}")

    # Save to history
    st.session_state.messages.append({
        "role": "assistant",
        "content": accumulated_text,
        "files": all_files,
        "tool_events": [e for e in tool_events if e["type"] == "tool_start"],
        "error": error_msg,
    })

    st.session_state.is_loading = False
    st.rerun()