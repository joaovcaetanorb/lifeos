"""Configuração via variáveis de ambiente (.env local, nunca commitado).

Espelha os nomes usados em st.secrets no Streamlit (ver
modules/musica/spotify_client.py, groq_client.py, database.py) — só troca a
origem (arquivo .env em vez do secrets.toml do Streamlit Cloud), pra poder
copiar os mesmos valores de um lado pro outro sem inventar nomes novos.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


class Settings:
    turso_musica_url: str | None = os.environ.get("TURSO_MUSICA_URL") or None
    turso_musica_token: str | None = os.environ.get("TURSO_MUSICA_TOKEN") or None
    turso_livros_url: str | None = os.environ.get("TURSO_LIVROS_URL") or None
    turso_livros_token: str | None = os.environ.get("TURSO_LIVROS_TOKEN") or None
    turso_habitos_url: str | None = os.environ.get("TURSO_HABITOS_URL") or None
    turso_habitos_token: str | None = os.environ.get("TURSO_HABITOS_TOKEN") or None
    turso_humor_url: str | None = os.environ.get("TURSO_HUMOR_URL") or None
    turso_humor_token: str | None = os.environ.get("TURSO_HUMOR_TOKEN") or None
    turso_projetos_url: str | None = os.environ.get("TURSO_PROJETOS_URL") or None
    turso_projetos_token: str | None = os.environ.get("TURSO_PROJETOS_TOKEN") or None
    turso_financeiro_url: str | None = os.environ.get("TURSO_FINANCEIRO_URL") or None
    turso_financeiro_token: str | None = os.environ.get("TURSO_FINANCEIRO_TOKEN") or None
    turso_momentos_url: str | None = os.environ.get("TURSO_MOMENTOS_URL") or None
    turso_momentos_token: str | None = os.environ.get("TURSO_MOMENTOS_TOKEN") or None
    turso_beatforge_url: str | None = os.environ.get("TURSO_BEATFORGE_URL") or None
    turso_beatforge_token: str | None = os.environ.get("TURSO_BEATFORGE_TOKEN") or None
    spotify_client_id: str | None = os.environ.get("SPOTIFY_CLIENT_ID") or None
    spotify_client_secret: str | None = os.environ.get("SPOTIFY_CLIENT_SECRET") or None
    spotify_redirect_uri: str | None = os.environ.get("SPOTIFY_REDIRECT_URI") or None
    groq_api_key: str | None = os.environ.get("GROQ_API_KEY") or None
    google_books_api_key: str | None = os.environ.get("GOOGLE_BOOKS_API_KEY") or None


settings = Settings()
