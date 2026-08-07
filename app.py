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
import time
from pathlib import Path

import streamlit as st

MODULES_DIR = Path(__file__).resolve().parent / "modules"
_STATIC_DIR = Path(__file__).resolve().parent / "static"

# Nomes de arquivo reaproveitados por mais de um módulo — têm que ser
# removidos do cache antes de cada página rodar, senão uma página herda o
# "database" (ou "calculations", "models"...) que outro módulo carregou antes.
# A ORDEM importa: é a ordem de dependência real entre esses arquivos
# (conferida nos imports de cada um) — utils/database não dependem de
# nada daqui, models depende de database, calculations depende de
# models+utils(+database em alguns módulos), relatorio depende de tudo
# isso. _preload_nomes_compartilhados() carrega nessa ordem.
_NOMES_COMPARTILHADOS = [
    "utils", "database", "models", "calculations", "ui",
    "colagem", "relatorio", "spotify_client", "groq_client",
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
st.set_page_config(page_title="~/life", page_icon=str(_STATIC_DIR / "icon-192.png"), layout="wide")


def _injetar_tags_pwa() -> None:
    """page_icon do set_page_config só troca o favicon — pro ícone de
    "adicionar à tela inicial" no celular funcionar de verdade (não virar
    print da tela), o navegador precisa de um <link rel="manifest"> e um
    <link rel="apple-touch-icon"> no <head> real da página. Streamlit não
    tem API pra isso, então injeta via JS: o componente roda num iframe,
    mas same-origin — window.parent.document é o documento de verdade.
    Um por sessão (session_state) evita repetir isso a cada rerun; a
    checagem de id no próprio JS evita duplicar as tags mesmo assim."""
    if st.session_state.get("_lifeos_pwa_injetado"):
        return
    st.session_state["_lifeos_pwa_injetado"] = True
    st.iframe(
        """
        <script>
        (function() {
            const head = window.parent.document.querySelector('head');
            if (!head || head.querySelector('#lifeos-pwa-manifest')) return;

            const manifest = document.createElement('link');
            manifest.id = 'lifeos-pwa-manifest';
            manifest.rel = 'manifest';
            manifest.href = '/app/static/manifest.json';
            head.appendChild(manifest);

            const appleIcon = document.createElement('link');
            appleIcon.rel = 'apple-touch-icon';
            appleIcon.href = '/app/static/apple-touch-icon.png';
            head.appendChild(appleIcon);

            const meta = (name, content) => {
                const tag = document.createElement('meta');
                tag.name = name;
                tag.content = content;
                head.appendChild(tag);
            };
            meta('theme-color', '#0D0F0C');
            meta('apple-mobile-web-app-capable', 'yes');
            meta('apple-mobile-web-app-status-bar-style', 'black-translucent');
            meta('apple-mobile-web-app-title', '~/life');
        })();
        </script>
        """,
        height=1,
    )


_injetar_tags_pwa()


def _preload_nomes_compartilhados(modulo_dir: Path) -> dict:
    """Carrega database.py/models.py/calculations.py/etc. manualmente, na
    ordem de dependência certa, e injeta direto em sys.modules — em vez de
    deixar o `import database` (etc.) de dentro do script da página
    disparar o mecanismo de import normal do CPython.

    Motivo: o mecanismo normal de import usa locks internos por NOME de
    módulo (não por arquivo), que persistem entre chamadas. Como vários
    módulos têm arquivos de mesmo nome, uma sessão carregando "database" de
    um módulo pode colidir com outra sessão carregando "database" de um
    módulo diferente ao mesmo tempo — visto em produção como `KeyError`
    (dentro de `importlib._bootstrap`) e também como `ModuleNotFoundError`
    (`import utils` falhando mesmo com o diretório certo no sys.path).
    Pré-carregar manualmente e colocar em sys.modules ANTES do script da
    página rodar faz o `import database`/`import utils` dele virar um
    simples lookup em sys.modules (dict, atômico) — nunca mais aciona o
    loader nem o lock por nome do CPython pra esses arquivos.

    Retorna {nome: módulo} carregados, pra quem chamou poder guardar esses
    objetos (ver _obter_modulos_cacheados) e reaproveitá-los depois sem
    reexecutar o arquivo."""
    modulos = {}
    for nome in _NOMES_COMPARTILHADOS:
        caminho = modulo_dir / f"{nome}.py"
        if not caminho.exists():
            continue
        spec = importlib.util.spec_from_file_location(nome, caminho)
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nome] = modulo
        spec.loader.exec_module(modulo)
        modulos[nome] = modulo
    return modulos


def _obter_modulos_cacheados(modulo_dir: Path, caminho_str: str) -> dict | None:
    """Módulos que ESTA sessão já carregou pra esse modulo_dir, reaproveitáveis
    se nenhum arquivo mudou desde então (cobre runOnSave). None se nunca
    carregou ou se algo mudou — força recarregar do zero nesse caso.

    Guardado em st.session_state (não em atributo de `st`/thread-local): tem
    que ser por sessão mesmo, sem depender de nenhuma outra sessão estar ou
    não com o mesmo módulo carregado nesse instante — uma tentativa anterior
    usava uma flag global pra decidir se podia pular o reload, e isso deu
    contaminação cruzada real em produção com sessões concorrentes em
    módulos diferentes. Aqui não tem esse compartilhamento: cada sessão só
    confia nos PRÓPRIOS objetos de módulo, nunca nos de outra."""
    cache = st.session_state.get("_lifeos_modulos_cache", {})
    entrada = cache.get(caminho_str)
    if entrada is None:
        return None
    modulos = {}
    for nome, (modulo, mtime_registrado) in entrada.items():
        caminho = modulo_dir / f"{nome}.py"
        try:
            mtime_atual = caminho.stat().st_mtime if caminho.exists() else None
        except OSError:
            return None
        if mtime_atual != mtime_registrado:
            return None
        modulos[nome] = modulo
    return modulos


def _guardar_modulos_cache(modulo_dir: Path, caminho_str: str, modulos: dict) -> None:
    entrada = {}
    for nome, modulo in modulos.items():
        caminho = modulo_dir / f"{nome}.py"
        try:
            mtime = caminho.stat().st_mtime
        except OSError:
            mtime = None
        entrada[nome] = (modulo, mtime)
    cache = st.session_state.get("_lifeos_modulos_cache", {})
    cache[caminho_str] = entrada
    st.session_state["_lifeos_modulos_cache"] = cache


def _executar_pagina(modulo_dir: Path, script: Path) -> None:
    """Executa o script de uma página isolado do sys.path/sys.modules de
    qualquer outro módulo já carregado nesta mesma sessão (ver
    _preload_nomes_compartilhados). Reexecuta algumas vezes em caso de
    falha transitória (ex.: Streamlit interrompe um rerun no meio de um
    `conn.sync()` lento do embedded replica) antes de desistir.

    Streamlit reroda esse script inteiro a cada interação (digitar,
    clicar), não só ao trocar de página — reexecutar database.py/models.py/
    etc. do zero em TODO rerun é caro à toa quando o módulo nem mudou.
    A otimização aqui é só pular a parte cara (parse + exec dos arquivos):
    o sys.modules em si é SEMPRE reatribuído explicitamente a cada render,
    nunca fica "confiando" que já está certo de uma vez anterior — os
    objetos vêm do cache desta sessão (`_obter_modulos_cacheados`) quando
    disponíveis, ou de um preload novo quando não. Isso evita a classe de
    bug da tentativa anterior (contaminação cruzada por causa de uma flag
    global compartilhada entre sessões)."""
    ultimo_erro = None
    caminho_str = str(modulo_dir)
    for tentativa in range(3):
        with _LOCK_IMPORTACAO:
            for nome in _NOMES_COMPARTILHADOS:
                sys.modules.pop(nome, None)

            ja_no_path = caminho_str in sys.path
            if not ja_no_path:
                sys.path.insert(0, caminho_str)
            try:
                _contexto_pagina.suprimir = True
                modulos = _obter_modulos_cacheados(modulo_dir, caminho_str)
                if modulos is None:
                    modulos = _preload_nomes_compartilhados(modulo_dir)
                    _guardar_modulos_cache(modulo_dir, caminho_str, modulos)
                else:
                    sys.modules.update(modulos)
                nome_unico = f"_pagina_{script.as_posix().replace('/', '_').replace(':', '')}"
                spec = importlib.util.spec_from_file_location(nome_unico, script)
                modulo = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(modulo)
                return
            except (KeyError, ModuleNotFoundError, ImportError) as e:
                ultimo_erro = e
                # o cache desta sessão pra esse módulo pode estar
                # implicado na falha — descarta, força preload do zero
                # nas tentativas seguintes.
                st.session_state.get("_lifeos_modulos_cache", {}).pop(caminho_str, None)
            finally:
                _contexto_pagina.suprimir = False
                if not ja_no_path and caminho_str in sys.path:
                    sys.path.remove(caminho_str)
        time.sleep(0.05 * (tentativa + 1))
    raise ultimo_erro


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
