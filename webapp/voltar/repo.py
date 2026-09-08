"""Camada de acesso a dados (CRUD) do módulo voltar. Um registro por dia
(upsert por `data`, mesmo padrão de webapp/revisao/repo.py::upsert_revisao —
uma semana lá, um dia aqui)."""

import re
import unicodedata
from datetime import date, datetime

import pandas as pd

from .db import get_connection, linha_para_dict


def _slugificar(texto: str) -> str:
    """'❤️ Fazer algo legal' -> 'fazer_algo_legal' — tira emoji/acento,
    vira snake_case. Usado só pra gerar a chave de uma tag nova."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")
    return slug or "tag"


def listar_tags_coisa_boa() -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query("SELECT * FROM tags_coisa_boa ORDER BY ordem ASC, rotulo ASC", conn)


def criar_tag_coisa_boa(rotulo: str) -> dict:
    conn = get_connection()
    base = _slugificar(rotulo)
    chave = base
    n = 1
    while conn.execute("SELECT 1 FROM tags_coisa_boa WHERE chave = ?", (chave,)).fetchone():
        n += 1
        chave = f"{base}_{n}"
    maior_ordem = conn.execute("SELECT COALESCE(MAX(ordem), -1) FROM tags_coisa_boa").fetchone()[0]
    conn.execute(
        "INSERT INTO tags_coisa_boa (chave, rotulo, ordem) VALUES (?, ?, ?)",
        (chave, rotulo, maior_ordem + 1),
    )
    conn.commit()
    return {"chave": chave, "rotulo": rotulo, "ordem": maior_ordem + 1}


def excluir_tag_coisa_boa(chave: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM tags_coisa_boa WHERE chave = ?", (chave,))
    conn.commit()


def obter_meta() -> dict:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM app_meta WHERE id = 1")
    meta = linha_para_dict(cursor, cursor.fetchone())
    return meta or {"seeded": 0, "data_inicio": date.today().isoformat()}


def obter_registro(data_iso: str) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM registros_diarios WHERE data = ?", (data_iso,))
    return linha_para_dict(cursor, cursor.fetchone())


def listar_registros(data_inicio: str | None = None, data_fim: str | None = None, limite: int = 0) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM registros_diarios"
    condicoes, params = [], []
    if data_inicio:
        condicoes.append("data >= ?")
        params.append(data_inicio)
    if data_fim:
        condicoes.append("data <= ?")
        params.append(data_fim)
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY data DESC"
    if limite:
        query += f" LIMIT {int(limite)}"
    return pd.read_sql_query(query, conn, params=params)


def upsert_registro(
    data_iso: str,
    hora_dormir: str | None,
    agua: bool | None,
    academia: str | None,
    leitura: bool | None,
    cigarros: int | None,
    responsabilidades: bool | None,
    coisa_boa_texto: str,
    coisa_boa_chaves: list[str],
    dinheiro: str | None,
    maconha: str | None,
) -> dict:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO registros_diarios
            (data, hora_dormir, agua, academia, leitura, cigarros, responsabilidades,
             coisa_boa_texto, coisa_boa_chaves, dinheiro, maconha, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(data) DO UPDATE SET
            hora_dormir = excluded.hora_dormir,
            agua = excluded.agua,
            academia = excluded.academia,
            leitura = excluded.leitura,
            cigarros = excluded.cigarros,
            responsabilidades = excluded.responsabilidades,
            coisa_boa_texto = excluded.coisa_boa_texto,
            coisa_boa_chaves = excluded.coisa_boa_chaves,
            dinheiro = excluded.dinheiro,
            maconha = excluded.maconha,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            data_iso,
            hora_dormir or None,
            None if agua is None else int(agua),
            academia,
            None if leitura is None else int(leitura),
            cigarros,
            None if responsabilidades is None else int(responsabilidades),
            coisa_boa_texto,
            ",".join(coisa_boa_chaves) if coisa_boa_chaves else None,
            dinheiro,
            maconha,
        ),
    )
    conn.commit()
    return obter_registro(data_iso)
