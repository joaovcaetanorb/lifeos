"""Ponto de entrada único do LifeOS.

Reúne todos os módulos (cada um uma aplicação Streamlit independente, veja
modules/<nome>/) numa única sessão via st.navigation — sidebar com todas as
telas, sem precisar abrir uma porta por módulo. Nenhum módulo precisou ser
alterado: cada um continua rodável sozinho com `streamlit run app.py` dentro
da própria pasta.

O truque é que vários módulos têm arquivos com o mesmo nome (database.py,
models.py, calculations.py, utils.py, ui.py...) — cada um pensado pra ser
importado como `import database` de dentro da própria pasta. Pra rodar todos
no mesmo processo Python sem um "database" de um módulo vazar pro outro,
cada troca de página limpa esses nomes do cache de módulos e importa o
script da página com o diretório do módulo correto na frente do sys.path.
"""

import importlib.util
import sys
import threading
from pathlib import Path

import streamlit as st

MODULES_DIR = Path(__file__).resolve().parent / "modules"

# Nomes de arquivo reaproveitados por mais de um módulo — têm que ser
# removidos do cache antes de cada página rodar, senão uma página herda o
# "database" (ou "calculations", "models"...) que outro módulo carregou antes.
_NOMES_COMPARTILHADOS = [
    "database", "models", "calculations", "utils", "ui", "relatorio",
    "spotify_client", "colagem", "groq_client",
]

# sys.path/sys.modules são globais do processo, mas o Streamlit roda cada
# sessão (e cada rerun, inclusive os automáticos do runOnSave) numa thread
# própria — sem essa trava, duas páginas de módulos diferentes carregando
# "ao mesmo tempo" podem pisar uma no sys.modules da outra (foi exatamente
# o que causou o "database sem inicializar_banco" visto em produção).
_LOCK_IMPORTACAO = threading.Lock()

# st.set_page_config só pode ser chamado uma vez por execução de script —
# mas cada página, pensada pra rodar sozinha, chama isso no próprio topo.
# A config já foi feita aqui em cima (layout wide vale pra todas as páginas
# mesmo assim), então a chamada da própria página precisa virar no-op — só
# que `st.set_page_config` é atributo do módulo `streamlit`, COMPARTILHADO
# por todas as sessões/abas do processo (Streamlit roda cada sessão numa
# thread própria, mas é o mesmo processo Python). Um monkeypatch comum
# (`st.set_page_config = lambda: None`, mesmo desfeito depois via
# try/finally com lock) ainda abre uma janela onde a chamada "de verdade"
# de QUALQUER outra sessão em andamento nesse exato instante acaba caindo
# nesse no-op — foi exatamente o bug visto em produção: a 1ª aba pegava
# wide, e se uma 2ª sessão chamasse st.set_page_config() (na raiz do
# app.py, fora de qualquer lock) enquanto a 1ª ainda estivesse dentro da
# janela de supressão, a 2ª ficava com layout "centered" pra sempre, e o
# título/ícone customizados também sumiam. threading.local() resolve isso
# de verdade: cada sessão (thread) só suprime a própria chamada, nunca a
# de outra rodando ao mesmo tempo — sem precisar de lock aqui.
if not hasattr(st, "_lifeos_set_page_config_original"):
    st._lifeos_set_page_config_original = st.set_page_config
    st._lifeos_contexto_pagina = threading.local()

    def _set_page_config_seguro(*args, **kwargs):
        if getattr(st._lifeos_contexto_pagina, "suprimir", False):
            return None
        return st._lifeos_set_page_config_original(*args, **kwargs)

    st.set_page_config = _set_page_config_seguro

_contexto_pagina = st._lifeos_contexto_pagina
st.set_page_config(page_title="LifeOS", page_icon="🧭", layout="wide")


def _executar_pagina(modulo_dir: Path, script: Path) -> None:
    """Executa o script de uma página isolado do sys.path/sys.modules de
    qualquer outro módulo já carregado nesta mesma sessão."""
    with _LOCK_IMPORTACAO:
        for nome in _NOMES_COMPARTILHADOS:
            sys.modules.pop(nome, None)

        caminho_str = str(modulo_dir)
        ja_no_path = caminho_str in sys.path
        if not ja_no_path:
            sys.path.insert(0, caminho_str)
        try:
            _contexto_pagina.suprimir = True
            nome_unico = f"_pagina_{script.as_posix().replace('/', '_').replace(':', '')}"
            spec = importlib.util.spec_from_file_location(nome_unico, script)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
        finally:
            _contexto_pagina.suprimir = False
            if not ja_no_path:
                sys.path.remove(caminho_str)


def _pagina(modulo: str, script_relativo: str):
    """Cria a função que uma st.Page chama a cada renderização."""
    modulo_dir = MODULES_DIR / modulo
    script = modulo_dir / script_relativo

    def render() -> None:
        _executar_pagina(modulo_dir, script)

    render.__name__ = f"pagina_{modulo}_{script.stem}"
    return render


paginas = {
    "Geral": [
        st.Page(_pagina("dashboard_geral", "app.py"),
                title="Dashboard Geral", icon="🧭", url_path="geral", default=True),
    ],
    "Analytics": [
        st.Page(_pagina("analytics", "app.py"),
                title="Como funciona", icon="📈", url_path="analytics"),
        st.Page(_pagina("analytics", "pages/analytics.py"),
                title="Analytics", icon="🔍", url_path="analytics-tendencias"),
    ],
    "Financeiro": [
        st.Page(_pagina("financeiro", "app.py"),
                title="Como funciona", icon="💰", url_path="financeiro"),
        st.Page(_pagina("financeiro", "pages/dashboard.py"),
                title="Dashboard", icon="📊", url_path="financeiro-dashboard"),
        st.Page(_pagina("financeiro", "pages/gastos.py"),
                title="Gastos", icon="🧾", url_path="financeiro-gastos"),
        st.Page(_pagina("financeiro", "pages/cartao.py"),
                title="Cartão", icon="💳", url_path="financeiro-cartao"),
        st.Page(_pagina("financeiro", "pages/planejamento.py"),
                title="Planejamento", icon="🗂️", url_path="financeiro-planejamento"),
        st.Page(_pagina("financeiro", "pages/reserva.py"),
                title="Reserva", icon="🏦", url_path="financeiro-reserva"),
    ],
    "Projetos": [
        st.Page(_pagina("projetos", "app.py"),
                title="Como funciona", icon="🎯", url_path="projetos"),
        st.Page(_pagina("projetos", "pages/projetos.py"),
                title="Projetos", icon="📋", url_path="projetos-lista"),
    ],
    "Humor": [
        st.Page(_pagina("humor", "app.py"),
                title="Como funciona", icon="🙂", url_path="humor"),
        st.Page(_pagina("humor", "pages/humor.py"),
                title="Humor", icon="📅", url_path="humor-registro"),
    ],
    "Hábitos": [
        st.Page(_pagina("habitos", "app.py"),
                title="Como funciona", icon="✅", url_path="habitos"),
        st.Page(_pagina("habitos", "pages/habitos.py"),
                title="Hábitos", icon="🗓️", url_path="habitos-lista"),
    ],
    "Livros": [
        st.Page(_pagina("livros", "app.py"),
                title="Como funciona", icon="📚", url_path="livros"),
        st.Page(_pagina("livros", "pages/estante.py"),
                title="Estante", icon="📖", url_path="livros-estante"),
        st.Page(_pagina("livros", "pages/diario.py"),
                title="Diário", icon="📝", url_path="livros-diario"),
        st.Page(_pagina("livros", "pages/estatisticas.py"),
                title="Estatísticas", icon="📈", url_path="livros-estatisticas"),
    ],
    "Música": [
        st.Page(_pagina("musica", "app.py"),
                title="Como funciona", icon="🎵", url_path="musica"),
        st.Page(_pagina("musica", "pages/albuns.py"),
                title="Álbuns", icon="💿", url_path="musica-albuns"),
        st.Page(_pagina("musica", "pages/diario.py"),
                title="Diário", icon="📝", url_path="musica-diario"),
        st.Page(_pagina("musica", "pages/colagem.py"),
                title="Colagem", icon="🖼️", url_path="musica-colagem"),
        st.Page(_pagina("musica", "pages/estatisticas.py"),
                title="Estatísticas", icon="📈", url_path="musica-estatisticas"),
    ],
}

pagina_atual = st.navigation(paginas)
pagina_atual.run()
