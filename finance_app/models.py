"""Camada de acesso a dados (CRUD). Sem regra de negócio financeira.

Funções de listagem retornam pandas.DataFrame (facilita uso direto em
gráficos e nas páginas). Funções de escrita retornam None ou o id criado.
"""

import pandas as pd
from database import get_connection

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def get_config() -> dict:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM config WHERE id = 1").fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def atualizar_config(salario: float, vale_alimentacao: float, dia_util_pagamento: int,
                      reserva_meta: float, reserva_aporte_padrao: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE config SET salario = ?, vale_alimentacao = ?, dia_util_pagamento = ?,
               reserva_meta = ?, reserva_aporte_padrao = ? WHERE id = 1""",
            (salario, vale_alimentacao, dia_util_pagamento, reserva_meta, reserva_aporte_padrao),
        )
        conn.commit()
    finally:
        conn.close()


def definir_inicio_controle(data_iso: str) -> None:
    """Data a partir de quando o Dia do Pagamento passa a valer de verdade
    (usado quando o usuário começa a usar o app no meio de um ciclo sem ter
    o dinheiro do pagamento anterior em mãos)."""
    conn = get_connection()
    try:
        conn.execute("UPDATE config SET inicio_controle = ? WHERE id = 1", (data_iso,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Contas fixas
# ---------------------------------------------------------------------------

def listar_contas_fixas(somente_ativas: bool = True) -> pd.DataFrame:
    conn = get_connection()
    try:
        query = "SELECT * FROM contas_fixas"
        if somente_ativas:
            query += " WHERE ativo = 1"
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def inserir_conta_fixa(descricao: str, valor: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO contas_fixas (descricao, valor, ativo) VALUES (?, ?, 1)",
            (descricao, valor),
        )
        conn.commit()
    finally:
        conn.close()


def atualizar_conta_fixa(conta_id: int, descricao: str, valor: float, ativo: bool) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE contas_fixas SET descricao = ?, valor = ?, ativo = ? WHERE id = ?",
            (descricao, valor, int(ativo), conta_id),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_conta_fixa(conta_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM contas_fixas WHERE id = ?", (conta_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def inserir_gasto(data: str, descricao: str, valor: float, categoria: str, forma_pagamento: str,
                   hora: str = "") -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO gastos (data, descricao, valor, categoria, forma_pagamento, hora)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data, descricao, valor, categoria, forma_pagamento, hora),
        )
        conn.commit()
    finally:
        conn.close()


def listar_gastos(data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    try:
        query = "SELECT * FROM gastos WHERE 1=1"
        params = []
        if data_inicio:
            query += " AND data >= ?"
            params.append(data_inicio)
        if data_fim:
            query += " AND data <= ?"
            params.append(data_fim)
        query += " ORDER BY data DESC, id DESC"
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


def excluir_gasto(gasto_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM gastos WHERE id = ?", (gasto_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Cartão de crédito
# ---------------------------------------------------------------------------

def inserir_compra_cartao(descricao: str, data_compra: str, valor_total: float,
                           parcelas: int, categoria: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO cartao_compras (descricao, data_compra, valor_total, parcelas, categoria)
               VALUES (?, ?, ?, ?, ?)""",
            (descricao, data_compra, valor_total, parcelas, categoria),
        )
        conn.commit()
    finally:
        conn.close()


def listar_compras_cartao() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query("SELECT * FROM cartao_compras ORDER BY data_compra DESC", conn)
    finally:
        conn.close()


def excluir_compra_cartao(compra_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM cartao_compras WHERE id = ?", (compra_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Planejamento mensal
# ---------------------------------------------------------------------------

def upsert_planejamento(mes_referencia: str, categoria: str, valor_planejado: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO planejamento (mes_referencia, categoria, valor_planejado)
               VALUES (?, ?, ?)
               ON CONFLICT(mes_referencia, categoria)
               DO UPDATE SET valor_planejado = excluded.valor_planejado""",
            (mes_referencia, categoria, valor_planejado),
        )
        conn.commit()
    finally:
        conn.close()


def listar_planejamento(mes_referencia: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT * FROM planejamento WHERE mes_referencia = ?", conn, params=[mes_referencia]
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Reserva financeira
# ---------------------------------------------------------------------------

def inserir_movimento_reserva(data: str, valor: float, tipo: str, observacao: str = "") -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO reserva_movimentos (data, valor, tipo, observacao)
               VALUES (?, ?, ?, ?)""",
            (data, valor, tipo, observacao),
        )
        conn.commit()
    finally:
        conn.close()


def listar_movimentos_reserva() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT * FROM reserva_movimentos ORDER BY data ASC, id ASC", conn
        )
    finally:
        conn.close()


def excluir_movimento_reserva(movimento_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM reserva_movimentos WHERE id = ?", (movimento_id,))
        conn.commit()
    finally:
        conn.close()
