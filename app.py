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
    "spotify_client", "colagem",
]

# sys.path/sys.modules são globais do processo, mas o Streamlit roda cada
# sessão (e cada rerun, inclusive os automáticos do runOnSave) numa thread
# própria — sem essa trava, duas páginas de módulos diferentes carregando
# "ao mesmo tempo" podem pisar uma no sys.modules da outra (foi exatamente
# o que causou o "database sem inicializar_banco" visto em produção).
_LOCK_IMPORTACAO = threading.Lock()

# st.set_page_config só pode ser chamado uma vez por sessão — mas cada
# página, pensada pra rodar sozinha, chama isso no próprio topo. Aqui a
# config já foi feita (layout wide vale pra todas as páginas mesmo assim),
# então viramos as chamadas seguintes em no-op em vez de editar 17 arquivos
# pra tirar essa linha.
st.set_page_config(page_title="LifeOS", page_icon="🧭", layout="wide")
st.set_page_config = lambda *args, **kwargs: None


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
            nome_unico = f"_pagina_{script.as_posix().replace('/', '_').replace(':', '')}"
            spec = importlib.util.spec_from_file_location(nome_unico, script)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
        finally:
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
