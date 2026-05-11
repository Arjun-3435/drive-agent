import traceback
import json
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from backend.config import settings

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

MIME_LABELS = {
    "application/pdf": "PDF",
    "application/vnd.google-apps.document": "Google Doc",
    "application/vnd.google-apps.spreadsheet": "Google Sheet",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/vnd.google-apps.folder": "Folder",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word Doc",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint",
    "image/jpeg": "JPEG Image",
    "image/png": "PNG Image",
    "image/gif": "GIF Image",
    "image/webp": "WebP Image",
    "text/plain": "Text File",
    "text/csv": "CSV File",
    "application/json": "JSON File",
    "application/zip": "ZIP Archive",
    "video/mp4": "MP4 Video",
    "audio/mpeg": "MP3 Audio",
}

MIME_EMOJIS = {
    "application/pdf": "📄",
    "application/vnd.google-apps.document": "📝",
    "application/vnd.google-apps.spreadsheet": "📊",
    "application/vnd.google-apps.presentation": "📑",
    "application/vnd.google-apps.folder": "📁",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "📝",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "📊",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "📑",
    "text/plain": "📃",
    "text/csv": "📊",
    "image/jpeg": "🖼️",
    "image/png": "🖼️",
    "image/gif": "🖼️",
    "image/webp": "🖼️",
}

# Common kwargs to pass on every Drive API files().list() call
_DRIVE_LIST_KWARGS = {
    "supportsAllDrives": True,
    "includeItemsFromAllDrives": True,
}

_DRIVE_GET_KWARGS = {
    "supportsAllDrives": True,
}


def _get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        settings.get_service_account_path(), scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def _format_size(size_str: Optional[str]) -> str:
    if not size_str:
        return "—"
    size = int(size_str)
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 ** 3:
        return f"{size / 1024 ** 2:.1f} MB"
    return f"{size / 1024 ** 3:.1f} GB"


def _format_date(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return iso_str


def _format_file(f: dict) -> dict:
    mime = f.get("mimeType", "")
    return {
        "id": f.get("id", ""),
        "name": f.get("name", "Untitled"),
        "type": MIME_LABELS.get(mime, mime.split("/")[-1].upper()),
        "emoji": MIME_EMOJIS.get(mime, "📎"),
        "mimeType": mime,
        "modified": _format_date(f.get("modifiedTime")),
        "created": _format_date(f.get("createdTime")),
        "size": _format_size(f.get("size")),
        "link": f.get("webViewLink", ""),
        "owners": [o.get("displayName", "") for o in f.get("owners", [])],
    }


@tool
def search_drive_files(query: str, max_results: int = 20) -> str:
    """
    Search for files in the Google Drive folder using a Drive API query string.
    Searches recursively through all subfolders.

    Build the `query` argument using Drive API q-parameter syntax:
    - name = 'exact'                        → exact name match
    - name contains 'keyword'               → partial name match
    - mimeType = 'application/pdf'          → PDFs
    - mimeType = 'application/vnd.google-apps.document'      → Google Docs
    - mimeType = 'application/vnd.google-apps.spreadsheet'   → Google Sheets
    - mimeType = 'application/vnd.google-apps.presentation'  → Google Slides
    - mimeType contains 'image/'            → any image
    - fullText contains 'keyword'           → search inside file content
    - modifiedTime > '2024-01-01T00:00:00'  → date filter
    - Combine with: and, or, not

    Do NOT include folder ID or trashed filters — added automatically.

    Args:
        query: Drive API q-parameter string
        max_results: Max files to return (1-50, default 20)

    Returns:
        JSON string with count and list of file metadata dicts.
    """
    service = _get_drive_service()

    # KEY FIX: 'in ancestors' searches recursively through all subfolders
    base = "trashed = false"
    full_query = f"({query}) and {base}" if query.strip() else base

    try:
        result = service.files().list(
            q=full_query,
            pageSize=min(max(1, max_results), 50),
            fields=(
                "files(id, name, mimeType, modifiedTime, createdTime, "
                "size, webViewLink, owners)"
            ),
            orderBy="modifiedTime desc",
            **_DRIVE_LIST_KWARGS,
        ).execute()

        files = result.get("files", [])

        if not files:
            return json.dumps({
                "count": 0,
                "files": [],
                "query_used": full_query,
                "message": (
                    "No files found for this query. "
                    "Try broader terms or use list_all_files to see what's available."
                ),
            })

        return json.dumps({
            "count": len(files),
            "files": [_format_file(f) for f in files],
            "query_used": full_query,
        })

    except HttpError as e:
            traceback.print_exc()   # ← ADD THIS LINE
            return json.dumps({"error": f"Drive API error: {e}", "count": 0, "files": []})
    except Exception as e:
            traceback.print_exc()   # ← ADD THIS LINE
            return json.dumps({"error": str(e), "count": 0, "files": []})


@tool
def list_all_files(max_results: int = 50) -> str:
    """
    List ALL files in the Google Drive folder, including files in subfolders.
    Use when the user wants a full overview or asks 'what files do you have?'

    Args:
        max_results: Max files to return (default 50)

    Returns:
        JSON string with all file metadata grouped by type summary.
    """
    service = _get_drive_service()
    folder_id = settings.google_drive_folder_id

    try:
        result = service.files().list(
            # KEY FIX: 'in ancestors' not 'in parents'
            q="trashed = false",
            pageSize=min(max_results, 50),
            fields=(
                "files(id, name, mimeType, modifiedTime, createdTime, "
                "size, webViewLink, owners)"
            ),
            orderBy="modifiedTime desc",
            **_DRIVE_LIST_KWARGS,
        ).execute()

        files = result.get("files", [])

        # Build a type summary so the LLM can give a useful overview
        type_counts: dict = {}
        for f in files:
            label = MIME_LABELS.get(f.get("mimeType", ""), "Other")
            type_counts[label] = type_counts.get(label, 0) + 1

        return json.dumps({
            "count": len(files),
            "type_summary": type_counts,
            "files": [_format_file(f) for f in files],
        })

    except HttpError as e:
        return json.dumps({"error": f"Drive API error: {e}", "count": 0, "files": []})
    except Exception as e:
        return json.dumps({"error": str(e), "count": 0, "files": []})


@tool
def get_file_details(file_id: str) -> str:
    """
    Retrieve full metadata for a specific file by its Drive file ID.
    Use when the user wants more info about a specific file from a previous search.

    Args:
        file_id: The Google Drive file ID string

    Returns:
        JSON string with detailed file metadata.
    """
    service = _get_drive_service()

    try:
        f = service.files().get(
            fileId=file_id,
            fields=(
                "id, name, mimeType, modifiedTime, createdTime, size, "
                "webViewLink, description, owners, parents, "
                "lastModifyingUser, capabilities"
            ),
            **_DRIVE_GET_KWARGS,
        ).execute()

        details = _format_file(f)
        details["description"] = f.get("description", "")
        details["last_modifier"] = (
            f.get("lastModifyingUser", {}).get("displayName", "Unknown")
        )
        details["can_download"] = (
            f.get("capabilities", {}).get("canDownload", False)
        )

        return json.dumps(details)

    except HttpError as e:
        return json.dumps({"error": f"Drive API error: {e}"})
    except Exception as e:
        return json.dumps({"error": str(e)})