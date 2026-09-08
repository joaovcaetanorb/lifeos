"""Camada de acesso a dados (CRUD) do módulo voltar. Um registro por dia
(upsert por `data`, mesmo padrão de webapp/revisao/repo.py::upsert_revisao —
uma semana lá, um dia aqui)."""

from datetime import date, datetime

import pandas as pd

from .db import get_connection, linha_para_dict

CATEGORIAS_COISA_BOA = {
    "album": "🎵 Ouvir um álbum inteiro",
    "basquete": "🏀 Jogar basquete",
    "jogo": "🎮 Jogar sem culpa",
    "leitura": "📖 Ler algumas páginas",
    "caminhada": "🚶 Dar uma caminhada",
    "amor": "❤️ Fazer algo legal com quem você gosta",
    "quarto": "🧹 Arrumar seu quarto",
    "beat": "🎹 Fazer um beat",
    "cafe": "☕ Sair para tomar um café",
    "unhas": "🧼 Cuidar das unhas",
    "dormir": "😴 Dormir mais cedo",
    "filme": "🎬 Assistir um filme",
    "descansar": "🛋️ Simplesmente descansar",
    "cozinhar": "🍳 Cozinhar algo gostoso",
    "amigo": "📱 Mandar mensagem pra um amigo",
    "familia": "👨‍👩‍👧 Passar um tempo com a família",
    "outro": "📝 Outra coisa",
}


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
    coisa_boa_categoria: str | None,
    dinheiro: str | None,
    maconha: str | None,
) -> dict:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO registros_diarios
            (data, hora_dormir, agua, academia, leitura, cigarros, responsabilidades,
             coisa_boa_texto, coisa_boa_categoria, dinheiro, maconha, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(data) DO UPDATE SET
            hora_dormir = excluded.hora_dormir,
            agua = excluded.agua,
            academia = excluded.academia,
            leitura = excluded.leitura,
            cigarros = excluded.cigarros,
            responsabilidades = excluded.responsabilidades,
            coisa_boa_texto = excluded.coisa_boa_texto,
            coisa_boa_categoria = excluded.coisa_boa_categoria,
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
            coisa_boa_categoria,
            dinheiro,
            maconha,
        ),
    )
    conn.commit()
    return obter_registro(data_iso)
