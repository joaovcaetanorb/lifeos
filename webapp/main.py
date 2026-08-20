"""Ponto de entrada do backend novo (fora do Streamlit) — cobre música,
livros e hábitos por enquanto (ver plano em .claude/plans/; cada módulo
migrado como uma fatia própria, um de cada vez).

Rodar de DENTRO da pasta webapp/ (mesma convenção que o resto do repo já
usa em modules/<nome>/ — arquivos importados como módulo solto, `import
database`/`import models`, funcionam porque o processo roda com aquela
pasta como raiz):

    cd webapp
    uvicorn main:app --reload --port 8000

O Streamlit (`streamlit run app.py`, porta 8501) continua funcionando em
paralelo sem nenhuma alteração — os dois processos leem/escrevem no mesmo
banco Turso, cada um com sua própria réplica local (ver <modulo>/db.py)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from analytics.router import router as analytics_router
from beatforge.db import inicializar_banco as inicializar_banco_beatforge
from beatforge.router import router as beatforge_router
from financeiro.db import inicializar_banco as inicializar_banco_financeiro
from financeiro.router import router as financeiro_router
from habitos.db import inicializar_banco as inicializar_banco_habitos
from habitos.router import router as habitos_router
from humor.db import inicializar_banco as inicializar_banco_humor
from humor.router import router as humor_router
from livros.db import inicializar_banco as inicializar_banco_livros
from livros.router import router as livros_router
from momentos.db import inicializar_banco as inicializar_banco_momentos
from momentos.router import router as momentos_router
from musica.db import inicializar_banco as inicializar_banco_musica
from musica.export_router import router as musica_export_router
from musica.router import router as musica_router
from musica.spotify_router import router as musica_spotify_router
from projetos.db import inicializar_banco as inicializar_banco_projetos
from projetos.router import router as projetos_router
from timeline.router import router as timeline_router

_WEBAPP_DIR = Path(__file__).resolve().parent
_FRONTEND_DIR = _WEBAPP_DIR / "frontend"

(_FRONTEND_DIR / "shared").mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIR / "analytics").mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIR / "musica").mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIR / "livros").mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIR / "habitos").mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIR / "humor").mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIR / "projetos").mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIR / "financeiro").mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIR / "timeline").mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIR / "beatforge").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="LifeOS — fora do Streamlit")


@app.on_event("startup")
def _startup() -> None:
    """Não deixa a ausência de .env derrubar o processo inteiro — sem
    banco configurado, o frontend estático (HTML/CSS/JS) continua
    acessível pra visualizar/ajustar; só as chamadas de API é que vão
    devolver erro (500 com mensagem clara) até o .env ser preenchido."""
    modulos = (
        ("música", inicializar_banco_musica),
        ("livros", inicializar_banco_livros),
        ("hábitos", inicializar_banco_habitos),
        ("humor", inicializar_banco_humor),
        ("projetos", inicializar_banco_projetos),
        ("financeiro", inicializar_banco_financeiro),
        ("momentos", inicializar_banco_momentos),
        ("beatforge", inicializar_banco_beatforge),
    )
    for nome, fn in modulos:
        try:
            fn()
        except RuntimeError as e:
            print(f"[aviso · {nome}] {e}")


app.include_router(musica_router)
app.include_router(musica_spotify_router)
app.include_router(musica_export_router)
app.include_router(livros_router)
app.include_router(habitos_router)
app.include_router(humor_router)
app.include_router(projetos_router)
app.include_router(financeiro_router)
app.include_router(momentos_router)
app.include_router(timeline_router)
app.include_router(analytics_router)
app.include_router(beatforge_router)

app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR / "shared")), name="shared-static")
app.mount("/musica", StaticFiles(directory=str(_FRONTEND_DIR / "musica"), html=True), name="musica-frontend")
app.mount("/livros", StaticFiles(directory=str(_FRONTEND_DIR / "livros"), html=True), name="livros-frontend")
app.mount("/habitos", StaticFiles(directory=str(_FRONTEND_DIR / "habitos"), html=True), name="habitos-frontend")
app.mount("/humor", StaticFiles(directory=str(_FRONTEND_DIR / "humor"), html=True), name="humor-frontend")
app.mount("/projetos", StaticFiles(directory=str(_FRONTEND_DIR / "projetos"), html=True), name="projetos-frontend")
app.mount("/financeiro", StaticFiles(directory=str(_FRONTEND_DIR / "financeiro"), html=True), name="financeiro-frontend")
app.mount("/timeline", StaticFiles(directory=str(_FRONTEND_DIR / "timeline"), html=True), name="timeline-frontend")
app.mount("/analytics", StaticFiles(directory=str(_FRONTEND_DIR / "analytics"), html=True), name="analytics-frontend")
app.mount("/beatforge", StaticFiles(directory=str(_FRONTEND_DIR / "beatforge"), html=True), name="beatforge-frontend")


@app.get("/", response_class=HTMLResponse)
def raiz():
    return (_FRONTEND_DIR / "home.html").read_text(encoding="utf-8")
