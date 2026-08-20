"""Camada de acesso a dados (CRUD) do módulo Beat Forge. Sem regra de
negócio — ver calculations.py. Mesmo padrão de webapp/projetos/repo.py."""

import pandas as pd

from .db import get_connection, linha_para_dict

# ---------------------------------------------------------------------------
# Beats
# ---------------------------------------------------------------------------

_COLUNAS_BEAT = (
    "id, nome, data, bpm, tonalidade, duracao_alvo, origem_tipo, origem_referencia, "
    "origem_metodo, status, tecnicas, link_externo, observacoes, capa_mime, created_at"
)


def listar_beats(status: str | None = None) -> pd.DataFrame:
    """Não traz `capa_dados` (BLOB) — ver obter_capa_beat() pra servir a
    imagem sob demanda."""
    conn = get_connection()
    query = f"SELECT {_COLUNAS_BEAT} FROM beats"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC, id DESC"
    return pd.read_sql_query(query, conn, params=params)


def obter_beat(beat_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute(f"SELECT {_COLUNAS_BEAT} FROM beats WHERE id = ?", (beat_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def obter_capa_beat(beat_id: int) -> tuple[bytes, str] | None:
    conn = get_connection()
    cursor = conn.execute("SELECT capa_dados, capa_mime FROM beats WHERE id = ?", (beat_id,))
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1] or "image/jpeg"


def inserir_beat(
    nome: str, data: str, bpm: int | None, tonalidade: str, duracao_alvo: str,
    origem_tipo: str, origem_referencia: str, origem_metodo: str,
    status: str, tecnicas: str, link_externo: str, observacoes: str,
    capa_dados: bytes | None = None, capa_mime: str | None = None,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO beats (nome, data, bpm, tonalidade, duracao_alvo, origem_tipo,
           origem_referencia, origem_metodo, status, tecnicas, link_externo, observacoes,
           capa_dados, capa_mime)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nome, data, bpm, tonalidade, duracao_alvo, origem_tipo, origem_referencia,
         origem_metodo, status, tecnicas, link_externo, observacoes, capa_dados, capa_mime),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_beat(
    beat_id: int, nome: str, data: str, bpm: int | None, tonalidade: str, duracao_alvo: str,
    origem_tipo: str, origem_referencia: str, origem_metodo: str,
    status: str, tecnicas: str, link_externo: str, observacoes: str,
    capa_dados: bytes | None = None, capa_mime: str | None = None,
) -> None:
    """capa_dados=None mantém a capa atual (não a apaga) — mesmo sentinela
    de webapp/projetos/repo.py::atualizar_projeto."""
    conn = get_connection()
    if capa_dados is None:
        conn.execute(
            """UPDATE beats SET nome = ?, data = ?, bpm = ?, tonalidade = ?, duracao_alvo = ?,
               origem_tipo = ?, origem_referencia = ?, origem_metodo = ?, status = ?,
               tecnicas = ?, link_externo = ?, observacoes = ? WHERE id = ?""",
            (nome, data, bpm, tonalidade, duracao_alvo, origem_tipo, origem_referencia,
             origem_metodo, status, tecnicas, link_externo, observacoes, beat_id),
        )
    else:
        conn.execute(
            """UPDATE beats SET nome = ?, data = ?, bpm = ?, tonalidade = ?, duracao_alvo = ?,
               origem_tipo = ?, origem_referencia = ?, origem_metodo = ?, status = ?,
               tecnicas = ?, link_externo = ?, observacoes = ?, capa_dados = ?, capa_mime = ?
               WHERE id = ?""",
            (nome, data, bpm, tonalidade, duracao_alvo, origem_tipo, origem_referencia,
             origem_metodo, status, tecnicas, link_externo, observacoes,
             capa_dados, capa_mime, beat_id),
        )
    conn.commit()


def excluir_beat(beat_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM beats WHERE id = ?", (beat_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Sessões
# ---------------------------------------------------------------------------

_COLUNAS_SESSAO = (
    "id, beat_id, data, duracao_minutos, proximo_passo_brutal, estado_emocional_snapshot, "
    "referencia_audicao_snapshot, observacao, audio_mime, created_at"
)


def listar_sessoes(beat_id: int) -> pd.DataFrame:
    """Não traz `audio_dados` (BLOB) — ver obter_audio_sessao() pra servir o
    áudio sob demanda."""
    conn = get_connection()
    return pd.read_sql_query(
        f"SELECT {_COLUNAS_SESSAO} FROM beat_sessoes WHERE beat_id = ? ORDER BY data DESC, id DESC",
        conn, params=[beat_id],
    )


def obter_audio_sessao(sessao_id: int) -> tuple[bytes, str] | None:
    conn = get_connection()
    cursor = conn.execute("SELECT audio_dados, audio_mime FROM beat_sessoes WHERE id = ?", (sessao_id,))
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1] or "audio/webm"


def inserir_sessao(
    beat_id: int, data: str, duracao_minutos: int, proximo_passo_brutal: str,
    estado_emocional_snapshot: str = "", referencia_audicao_snapshot: str = "",
    observacao: str = "", audio_dados: bytes | None = None, audio_mime: str | None = None,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO beat_sessoes (beat_id, data, duracao_minutos, proximo_passo_brutal,
           estado_emocional_snapshot, referencia_audicao_snapshot, observacao, audio_dados, audio_mime)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (beat_id, data, duracao_minutos, proximo_passo_brutal,
         estado_emocional_snapshot, referencia_audicao_snapshot, observacao, audio_dados, audio_mime),
    )
    conn.commit()
    return cur.lastrowid


def excluir_sessao(sessao_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM beat_sessoes WHERE id = ?", (sessao_id,))
    conn.commit()


def listar_sessoes_todas(data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    """Sessões de todos os beats juntas, com o nome do beat via join — usado
    pro streak/tempo-total em calculations.py e, no futuro, pela Timeline."""
    conn = get_connection()
    colunas = ", ".join(f"beat_sessoes.{c}" for c in _COLUNAS_SESSAO.split(", "))
    query = f"""SELECT {colunas}, beats.nome AS beat_nome
               FROM beat_sessoes
               JOIN beats ON beats.id = beat_sessoes.beat_id"""
    condicoes, params = [], []
    if data_inicio:
        condicoes.append("beat_sessoes.data >= ?")
        params.append(data_inicio)
    if data_fim:
        condicoes.append("beat_sessoes.data <= ?")
        params.append(data_fim)
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY beat_sessoes.data DESC, beat_sessoes.id DESC"
    return pd.read_sql_query(query, conn, params=params)


# ---------------------------------------------------------------------------
# Dicas
# ---------------------------------------------------------------------------

def listar_dicas() -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query("SELECT * FROM beat_dicas ORDER BY id ASC", conn)


def inserir_dica(texto: str) -> int:
    conn = get_connection()
    cur = conn.execute("INSERT INTO beat_dicas (texto) VALUES (?)", (texto,))
    conn.commit()
    return cur.lastrowid


def excluir_dica(dica_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM beat_dicas WHERE id = ?", (dica_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Crate de samples
# ---------------------------------------------------------------------------

def listar_crate(status: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM sample_crate"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC, id DESC"
    return pd.read_sql_query(query, conn, params=params)


def obter_item_crate(item_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM sample_crate WHERE id = ?", (item_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_item_crate(
    link: str, nome: str = "", fonte: str = "", tags: str = "", observacao: str = "", capa_url: str = "",
) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO sample_crate (link, nome, fonte, tags, observacao, capa_url) VALUES (?, ?, ?, ?, ?, ?)",
        (link, nome, fonte, tags, observacao, capa_url),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_status_crate(item_id: int, status: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE sample_crate SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()


def excluir_item_crate(item_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM sample_crate WHERE id = ?", (item_id,))
    conn.commit()


def sortear_item_crate() -> dict | None:
    """Sorteio de verdade via SQL (ORDER BY RANDOM()), não em Python — evita
    ter que trazer a fila inteira só pra escolher um. Só considera status
    'novo': itens já usados/descartados saem do sorteio."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM sample_crate WHERE status = 'novo' ORDER BY RANDOM() LIMIT 1"
    )
    return linha_para_dict(cursor, cursor.fetchone())
