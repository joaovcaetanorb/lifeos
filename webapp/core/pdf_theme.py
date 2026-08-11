"""Tema visual compartilhado pros relatórios em PDF (reportlab) — mesma
paleta/tipografia do console novo (webapp/frontend/shared/tokens.css) e o
mesmo vocabulário visual do relatório Stories de música (LED, prompt "$",
caixas com hairline, KPI com linha de destaque no topo — ver
webapp/musica/relatorio_stories.py).

Qualquer `<modulo>/relatorio.py` novo deve importar daqui em vez de
redesenhar cores/fontes/caixas do zero — é o pedido explícito de manter
todos os relatórios com a mesma cara.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

_FONTS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "shared" / "fonts"

# ---------------------------------------------------------------------------
# paleta — mesmos valores de tokens.css
# ---------------------------------------------------------------------------

BG = "#0B0D09"
PANEL = "#14170F"
HAIR = "#262920"
HAIR_BRIGHT = "#3a4030"
INK = "#E9E7DC"
INK_MUTED = "#8B8A82"
INK_DIM = "#57564f"
ACCENT = "#2E9E63"
ACCENT_BRIGHT = "#4ADE94"

COR_BG = colors.HexColor(BG)
COR_PANEL = colors.HexColor(PANEL)
COR_HAIR = colors.HexColor(HAIR)
COR_HAIR_BRIGHT = colors.HexColor(HAIR_BRIGHT)
COR_INK = colors.HexColor(INK)
COR_MUTED = colors.HexColor(INK_MUTED)
COR_DIM = colors.HexColor(INK_DIM)
COR_ACCENT = colors.HexColor(ACCENT)
COR_ACCENT_BRIGHT = colors.HexColor(ACCENT_BRIGHT)


# ---------------------------------------------------------------------------
# fontes reais (JetBrains Mono + Courier Prime, mesmos arquivos do frontend)
# ---------------------------------------------------------------------------

_registrado = False


def registrar_fontes() -> None:
    global _registrado
    if _registrado:
        return
    pdfmetrics.registerFont(TTFont("JBM", str(_FONTS_DIR / "jbm-400.ttf")))
    pdfmetrics.registerFont(TTFont("JBM-Medium", str(_FONTS_DIR / "jbm-500.ttf")))
    pdfmetrics.registerFont(TTFont("JBM-Bold", str(_FONTS_DIR / "jbm-700.ttf")))
    pdfmetrics.registerFont(TTFont("CP", str(_FONTS_DIR / "cp-400.ttf")))
    pdfmetrics.registerFont(TTFont("CP-Bold", str(_FONTS_DIR / "cp-700.ttf")))
    _registrado = True


def estilos() -> dict:
    """Paragraph styles prontos — chamar registrar_fontes() já embutido."""
    registrar_fontes()
    return {
        "topbar": ParagraphStyle("topbar", fontName="CP", fontSize=8.5, leading=11, textColor=COR_DIM),
        "eyebrow": ParagraphStyle("eyebrow", fontName="CP-Bold", fontSize=8, leading=10, textColor=COR_MUTED, spaceAfter=3),
        "titulo": ParagraphStyle("titulo", fontName="JBM-Bold", fontSize=24, leading=30, textColor=COR_INK, spaceAfter=2),
        "subtitulo": ParagraphStyle("subtitulo", fontName="JBM-Bold", fontSize=12, leading=16, textColor=COR_INK, spaceBefore=10, spaceAfter=6),
        "corpo": ParagraphStyle("corpo", fontName="JBM", fontSize=9.5, textColor=COR_INK, leading=14),
        "muted": ParagraphStyle("muted", fontName="JBM", fontSize=8.5, textColor=COR_MUTED, leading=12),
        "dim": ParagraphStyle("dim", fontName="JBM", fontSize=8, textColor=COR_DIM, leading=11),
        "kpi_label": ParagraphStyle("kpi_label", fontName="CP-Bold", fontSize=7.5, leading=10, textColor=COR_MUTED, alignment=1),
        "kpi_valor": ParagraphStyle("kpi_valor", fontName="JBM-Bold", fontSize=26, leading=30, textColor=COR_ACCENT_BRIGHT, alignment=1),
        "nota": ParagraphStyle("nota", fontName="JBM-Bold", fontSize=40, leading=52, textColor=COR_ACCENT_BRIGHT, alignment=1),
        "veredito": ParagraphStyle("veredito", fontName="JBM-Bold", fontSize=12, leading=16, textColor=COR_INK, alignment=1, spaceBefore=4, spaceAfter=8),
        "tabela_cab": ParagraphStyle("tabela_cab", fontName="CP-Bold", fontSize=7.5, textColor=COR_MUTED, leading=10),
        "tabela_cel": ParagraphStyle("tabela_cel", fontName="JBM", fontSize=9, textColor=COR_INK, leading=12),
    }


class _LEDDot(Flowable):
    """Círculo preenchido desenhado direto no canvas — não depende de a
    fonte ter o glifo "●" (Courier Prime não tem; virava uma caixa vazia)."""

    def __init__(self, diametro: float = 0.2 * cm, cor=None):
        super().__init__()
        self.diametro = diametro
        self.cor = cor or COR_ACCENT
        self.width = diametro
        self.height = diametro

    def draw(self) -> None:
        r = self.diametro / 2
        self.canv.setFillColor(self.cor)
        self.canv.circle(r, r, r, fill=1, stroke=0)


def led_com_texto(texto: str, estilo: ParagraphStyle, cor_led=None) -> Table:
    """LED (círculo vetor) + texto na mesma linha — usado no topbar do
    cabeçalho de todo relatório."""
    t = Table([[_LEDDot(cor=cor_led), Paragraph(texto, estilo)]], colWidths=[0.35 * cm, None])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def fundo_pagina(canvas_obj, doc) -> None:
    canvas_obj.saveState()
    canvas_obj.setFillColor(COR_BG)
    canvas_obj.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    canvas_obj.restoreState()


# ---------------------------------------------------------------------------
# blocos compostos — cabeçalho, caixas com hairline, KPIs, chips
# ---------------------------------------------------------------------------

def cabecalho(modulo_label: str, titulo: str, data_label: str) -> list:
    """Topbar (● LIFEOS · MÓDULO X) + título "$ ..." + data + hairline —
    mesmo bloco em todo relatório, pra reconhecer de cara qual módulo é."""
    s = estilos()
    return [
        led_com_texto(f"LIFEOS · MÓDULO {modulo_label.upper()}", s["topbar"]),
        Spacer(1, 0.35 * cm),
        Paragraph(f'<font color="{ACCENT}">$</font> {titulo}', s["titulo"]),
        Spacer(1, 0.15 * cm),
        Paragraph(data_label, s["muted"]),
        Spacer(1, 0.4 * cm),
        hairline(),
        Spacer(1, 0.4 * cm),
    ]


def hairline(cor=None):
    from reportlab.platypus import HRFlowable
    return HRFlowable(width="100%", color=cor or COR_HAIR, thickness=1)


def eyebrow(texto: str):
    return Paragraph(texto.upper(), estilos()["eyebrow"])


def caixa(flowables: list, largura: float, cor_borda=None, accent_topo: bool = False, padding: float = 0.35) -> Table:
    """Painel com hairline ao redor (mesma leitura visual do `.module` do
    frontend) — opcionalmente com uma linha de destaque verde no topo
    (como o `.kpi::before`). `flowables` é o conteúdo da caixa."""
    cor_borda = cor_borda or COR_HAIR
    t = Table([[flowables]], colWidths=[largura * cm])
    estilo = [
        ("BOX", (0, 0), (-1, -1), 1, cor_borda),
        ("LEFTPADDING", (0, 0), (-1, -1), padding * cm),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding * cm),
        ("TOPPADDING", (0, 0), (-1, -1), padding * cm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding * cm),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if accent_topo:
        estilo.append(("LINEABOVE", (0, 0), (-1, 0), 2.4, COR_ACCENT))
    t.setStyle(TableStyle(estilo))
    return t


def linha_kpis(pares: list[tuple[str, str]], largura_total: float, gap: float = 0.4) -> Table:
    """pares: [(rótulo, valor), ...] — vira N caixas iguais lado a lado,
    cada uma com a linha de destaque no topo (mesmo padrão do `.kpi-grid`
    do frontend)."""
    s = estilos()
    n = len(pares)
    largura_caixa = (largura_total - gap * (n - 1)) / n
    celulas = []
    for rotulo, valor in pares:
        conteudo = [
            Spacer(1, 0.15 * cm),
            Paragraph(str(valor), s["kpi_valor"]),
            Spacer(1, 0.08 * cm),
            Paragraph(rotulo.upper(), s["kpi_label"]),
            Spacer(1, 0.15 * cm),
        ]
        celulas.append(caixa(conteudo, largura_caixa, accent_topo=True))

    linha = Table([celulas], colWidths=[largura_caixa * cm + gap * cm] * n)
    linha.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), gap * cm),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return linha


def linha_chips(textos: list[str]):
    """Detalhes curtos separados por "·", em muted — versão simplificada
    das pills do frontend (chip-por-caixa não vale a complexidade num
    documento que flui/quebra página; o espaçador visual já comunica
    "tags soltas" o bastante)."""
    if not textos:
        return Spacer(1, 0)
    texto = "&nbsp;&nbsp;·&nbsp;&nbsp;".join(t.upper() for t in textos)
    return Paragraph(texto, estilos()["dim"])


def tabela_dados(cabecalhos: list[str], linhas: list[list[str]], larguras_cm: list[float]) -> Table:
    """Tabela com o mesmo tratamento do `.data-table` do frontend: cabeçalho
    em Courier Prime muted, células em JetBrains Mono, hairline entre
    linhas."""
    s = estilos()
    dados = [[Paragraph(c.upper(), s["tabela_cab"]) for c in cabecalhos]]
    for linha in linhas:
        dados.append([Paragraph(str(v), s["tabela_cel"]) for v in linha])

    t = Table(dados, colWidths=[w * cm for w in larguras_cm])
    t.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.6, COR_HAIR),
        ("LINEBELOW", (0, 0), (-1, 0), 1, COR_HAIR_BRIGHT),
    ]))
    return t
