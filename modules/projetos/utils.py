"""Constantes e funções auxiliares usadas em todo o app.

Não acessa banco de dados nem contém regra de negócio — isso fica em
calculations.py. Aqui só formatação e constantes de domínio.
"""

STATUS_PROJETO = ["Ativo", "Pausado", "Concluído"]

# Tema visual "ledger/terminal": mesmo esquema de cores do módulo financeiro,
# para manter identidade visual consistente entre módulos do LifeOS.
COR_FUNDO = "#0D0F0C"
COR_FUNDO_ALT = "#16190F"
COR_TEXTO = "#E8E6DC"
COR_TEXTO_MUTED = "#898781"
COR_HAIRLINE = "#2A2D23"
COR_ACENTO = "#3FA66B"


def formatar_moeda(valor: float) -> str:
    """Formata um número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    if valor is None:
        valor = 0.0
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"
