import base64
import tempfile
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Groq
    groq_api_key: str

    # Google Drive
    google_drive_folder_id: str

    # Service account — file path (local) OR base64 string (cloud)
    service_account_path: str = "credentials/service_account.json"
    service_account_b64: str = ""

    # App
    app_env: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_service_account_path(self) -> str:
        """
        Returns a valid path to the service-account JSON.
        On cloud (Railway/Render), set SERVICE_ACCOUNT_B64 to the
        base64-encoded content of your JSON key file.
        """
        if self.service_account_b64:
            decoded = base64.b64decode(self.service_account_b64).decode("utf-8")
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            tmp.write(decoded)
            tmp.flush()
            return tmp.name

        path = Path(self.service_account_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Service account not found at '{path}'. "
                "Set SERVICE_ACCOUNT_B64 env var for cloud deployment."
            )
        return str(path)


settings = Settings()