"""Constantes e funções auxiliares — vocabulário fixo de tags, cores e
formatação. Sem acesso a banco nem regra de negócio (isso fica em
calculations.py). Port ~verbatim de modules/humor/utils.py, sem os helpers
específicos de Streamlit (badge_cor_tag)."""

from datetime import date, datetime

# Vocabulário fixo de tags — de propósito, não é texto livre. O objetivo é
# permitir cruzamento automático (ex.: tags cruzando hábitos x humor x
# música) mais pra frente, e isso só funciona com um vocabulário fechado.
TAGS_HUMOR = [
    "Animado", "Grato", "Motivado", "Calmo", "Realizado", "Confiante", "Focado",
    "Ansioso", "Cansado", "Irritado", "Triste", "Sobrecarregado", "Frustrado", "Entediado",
]

# As 7 primeiras tags acima são o lado positivo do vocabulário; o resto é
# negativo. Usado só pra colorir — não afeta a nota numérica.
TAGS_POSITIVAS = set(TAGS_HUMOR[:7])

# Par validado (CVD ΔE 19.2, normal-vision ΔE 29.0) via
# scripts/validate_palette.js da skill de dataviz — verde/vermelho falha
# separação pra daltonismo deutan, por isso azul/vermelho.
COR_TAG_POSITIVO = "#3987e5"
COR_TAG_NEGATIVO = "#e66767"

# Ponto médio neutro pra escala divergente do calendário de humor.
COR_NEUTRO = "#383835"

NOMES_MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def hex_para_rgb(hex_cor: str) -> tuple[int, int, int]:
    hex_cor = hex_cor.lstrip("#")
    return tuple(int(hex_cor[i:i + 2], 16) for i in (0, 2, 4))


def cor_nota(nota: float, nota_min: float = 1, nota_max: float = 10) -> str:
    """Interpola a escala divergente (vermelho -> cinza -> azul)."""
    proporcao = min(max((nota - nota_min) / (nota_max - nota_min), 0), 1)
    if proporcao <= 0.5:
        cor_a, cor_b, t = COR_TAG_NEGATIVO, COR_NEUTRO, proporcao / 0.5
    else:
        cor_a, cor_b, t = COR_NEUTRO, COR_TAG_POSITIVO, (proporcao - 0.5) / 0.5
    r1, g1, b1 = hex_para_rgb(cor_a)
    r2, g2, b2 = hex_para_rgb(cor_b)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def formatar_data_br(data_iso: str) -> str:
    if not data_iso:
        return ""
    ano, mes, dia = data_iso.split("-")
    return f"{dia}/{mes}"


def hoje_iso() -> str:
    return date.today().isoformat()


def agora_hora() -> str:
    return datetime.now().strftime("%H:%M")


def tags_para_texto(tags: list[str]) -> str:
    return ",".join(tags)


def texto_para_tags(texto: str) -> list[str]:
    return [t for t in texto.split(",") if t]


def cor_tag(tag: str) -> str:
    return COR_TAG_POSITIVO if tag in TAGS_POSITIVAS else COR_TAG_NEGATIVO
