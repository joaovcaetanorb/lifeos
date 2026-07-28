"""Constantes e funções auxiliares usadas em todo o app.

Não acessa banco de dados nem contém regra de negócio — isso fica em
calculations.py. Aqui só formatação e constantes de domínio.
"""

NOTA_MINIMA = 0.5
NOTA_MAXIMA = 5.0
NOTA_PASSO = 0.5
OPCOES_NOTA = [round(NOTA_MINIMA + i * NOTA_PASSO, 1) for i in range(int((NOTA_MAXIMA - NOTA_MINIMA) / NOTA_PASSO) + 1)]

# Tema visual "ledger/terminal": mesmo esquema de cores dos outros módulos
# do LifeOS, pra manter identidade visual consistente.
COR_FUNDO = "#0D0F0C"
COR_FUNDO_ALT = "#16190F"
COR_TEXTO = "#E8E6DC"
COR_TEXTO_MUTED = "#898781"
COR_HAIRLINE = "#2A2D23"
COR_ACENTO = "#3FA66B"


def nota_ausente(nota: float | None) -> bool:
    """True pra None ou NaN — pandas lê NULL do SQLite como NaN (float),
    não None, e "nota != nota" só é True quando o valor é NaN."""
    return nota is None or nota != nota


def formatar_nota(nota: float | None) -> str:
    """4.5 -> '★ 4.5'. None/NaN -> 'sem nota'."""
    if nota_ausente(nota):
        return "sem nota"
    return f"★ {nota:g}"


def formatar_data_br(data_iso: str) -> str:
    """'2026-08-05' -> '05/08/2026'. String vazia retorna vazio."""
    if not data_iso:
        return ""
    ano, mes, dia = data_iso.split("-")
    return f"{dia}/{mes}/{ano}"
