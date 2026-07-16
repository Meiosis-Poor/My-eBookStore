from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "My-eBookStore API")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
        if origin.strip()
    )

    sqlserver_driver: str = os.getenv("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server")
    sqlserver_server: str = os.getenv("SQLSERVER_SERVER", r"localhost\MYDB")
    sqlserver_database: str = os.getenv("SQLSERVER_DATABASE", "My_eBookStore")
    sqlserver_username: str = os.getenv("SQLSERVER_USERNAME", "")
    sqlserver_password: str = os.getenv("SQLSERVER_PASSWORD") or os.getenv("MSSQL_SA_PASSWORD", "")
    sqlserver_trusted_connection: str = os.getenv("SQLSERVER_TRUSTED_CONNECTION", "yes")
    sqlserver_encrypt: str = os.getenv("SQLSERVER_ENCRYPT", "yes")
    sqlserver_trust_server_certificate: str = os.getenv("SQLSERVER_TRUST_SERVER_CERTIFICATE", "yes")

    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    def connection_string(self, database: str | None = None) -> str:
        parts = [
            f"DRIVER={{{self.sqlserver_driver}}}",
            f"SERVER={self.sqlserver_server}",
            f"DATABASE={database or self.sqlserver_database}",
        ]
        if self.sqlserver_username:
            parts.extend(
                [
                    f"UID={self.sqlserver_username}",
                    f"PWD={self.sqlserver_password}",
                    f"Encrypt={self.sqlserver_encrypt}",
                ]
            )
        else:
            parts.append(f"Trusted_Connection={self.sqlserver_trusted_connection}")
        parts.append(f"TrustServerCertificate={self.sqlserver_trust_server_certificate}")
        return ";".join(parts) + ";"


settings = Settings()
