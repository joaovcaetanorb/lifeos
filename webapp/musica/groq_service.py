"""Integração com a API do Groq — port de modules/musica/groq_client.py.
Sem @st.cache_resource: o cliente é criado uma vez e guardado num
singleton de módulo simples (mesmo raciocínio de webapp/musica/db.py)."""

from groq import Groq

from core.config import settings

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

_client_singleton: Groq | None = None
_client_tentado = False


def _get_client() -> Groq | None:
    global _client_singleton, _client_tentado
    if _client_tentado:
        return _client_singleton
    _client_tentado = True
    if settings.groq_api_key:
        _client_singleton = Groq(api_key=settings.groq_api_key)
    return _client_singleton


def disponivel() -> bool:
    return _get_client() is not None


def gerar_insights(contexto: str) -> str | None:
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
