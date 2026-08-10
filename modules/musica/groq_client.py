"""Integração com a API do Groq — insights curtos sobre as estatísticas de
música (Diário ou histórico real do Spotify), no mesmo espírito do
groq_client.py de Analytics.

Qualquer falha aqui (sem credencial configurada, erro de rede, timeout)
degrada pra "recurso indisponível" em vez de quebrar a página — a IA é um
complemento opcional, os gráficos e números continuam funcionando sem ela.
"""

import streamlit as st
from groq import Groq

# groq/compound (não llama-3.3-70b-versatile puro) — tem busca na web
# embutida e aciona sozinho quando precisa de informação que não está no
# treino do modelo, o que é exatamente o caso aqui: subgênero, idioma,
# temática das letras etc. de artistas menos famosos internacionalmente
# (samba, rap nacional) o modelo pode não saber de cabeça.
#
# MODELO_FALLBACK entra se o compound falhar — na prática ele orquestra
# VÁRIOS modelos por trás (ex.: llama-4-scout pra buscar/resumir a web), e
# testar isso algumas vezes seguidas já foi suficiente pra estourar o rate
# limit de um desses modelos internos (plano gratuito da Groq). O fallback
# não pesquisa a web, mas ainda usa o próprio conhecimento do modelo sobre
# os artistas — melhor que "não consegui gerar" na maioria das vezes.
MODELO = "groq/compound"
MODELO_FALLBACK = "llama-3.3-70b-versatile"

_SISTEMA = (
    "Você é um assistente pessoal dentro do LifeOS, comentando os hábitos "
    "musicais do usuário. Responda em português do Brasil, em tom direto, "
    "curto e informal — nada de linguagem corporativa.\n\n"
    "Os NÚMEROS (contagens, rankings, horários, sequências) vêm SEMPRE do "
    "contexto abaixo — nunca invente ou altere um número que não esteja lá. "
    "Mas pra além dos números, você pode e deve pesquisar/usar seu "
    "conhecimento sobre os artistas e gêneros citados: em que língua "
    "cantam, subgênero mais específico, época/movimento musical, temática "
    "recorrente das letras — isso enriquece a observação em vez de só "
    "repetir a contagem. Se pesquisar algo, cite naturalmente no texto (ex: "
    "'X é um dos nomes do samba de raiz carioca dos anos 90'), sem soar "
    "como enciclopédia. Se o contexto não tiver dado suficiente pra uma "
    "observação minimamente confiável, diga isso em vez de forçar uma "
    "conclusão fraca."
)


@st.cache_resource(show_spinner=False)
def _get_client() -> Groq | None:
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except (KeyError, FileNotFoundError):
        return None
    return Groq(api_key=api_key)


def disponivel() -> bool:
    return _get_client() is not None


def gerar_insights(contexto: str) -> str | None:
    """2-4 observações curtas sobre o `contexto` (números já calculados em
    Python — ver calculations.contexto_ia_diario/contexto_ia_real). None
    se a API não estiver disponível ou a chamada falhar."""
    cliente = _get_client()
    if cliente is None:
        return None
    prompt = (
        f"Dados reais do período selecionado:\n\n{contexto}\n\n"
        "Aponte de 2 a 4 observações curtas sobre o gosto ou hábito musical "
        "do usuário nesse período. Vá além da contagem: pesquise os "
        "artistas/gêneros citados acima e traga algo sobre o que eles "
        "cantam (temática), em que língua, subgênero específico ou época — "
        "não só 'padrão de horário' ou 'artista em alta' repetindo o "
        "número. Formate como lista curta, uma observação por linha."
    )
    mensagens = [
        {"role": "system", "content": _SISTEMA},
        {"role": "user", "content": prompt},
    ]
    for modelo in (MODELO, MODELO_FALLBACK):
        try:
            resposta = cliente.chat.completions.create(
                model=modelo, messages=mensagens, temperature=0.5, max_tokens=400,
            )
            texto = (resposta.choices[0].message.content or "").strip()
            if texto:
                return texto
        except Exception:
            continue
    return None
