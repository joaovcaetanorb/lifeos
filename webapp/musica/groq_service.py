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
    "Mas o valor real está no que você traz ALÉM do número: pesquise e use "
    "seu conhecimento sobre os artistas, músicas e produtores citados — uma "
    "curiosidade específica e pouco óbvia. Exemplos do tipo de coisa que "
    "vale citar: de onde veio o sample da faixa, quem produziu e o que mais "
    "essa pessoa produziu, uma história por trás da gravação ou do nome do "
    "álbum, uma parceria ou rixa entre os artistas, um detalhe da letra que "
    "não é óbvio de primeira, o contexto/cena em que o artista surgiu. Fuja "
    "de generalidade tipo 'letras introspectivas' ou 'sons inovadores' — "
    "isso não diz nada. Prefira um fato concreto e verificável a uma "
    "caracterização vaga, mesmo que isso signifique falar de só um "
    "artista/faixa em vez de tentar cobrir todos. Cite a curiosidade "
    "naturalmente, sem soar como enciclopédia. Se o contexto não tiver dado "
    "suficiente pra uma observação minimamente confiável, diga isso em vez "
    "de forçar uma conclusão fraca.\n\n"
    "Varie a estrutura das frases entre as observações — não comece todas "
    "com 'O usuário...' ou repita o mesmo esqueleto sujeito-verbo-explicação "
    "toda vez. Escreva como quem está contando algo interessante pra um "
    "amigo, não gerando um relatório."
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
        "do usuário nesse período. Pelo menos uma delas TEM que ser uma "
        "curiosidade concreta sobre um artista, faixa ou produtor específico "
        "dos dados acima (sample, produção, história da gravação, parceria, "
        "origem — não característica genérica de gênero). Formate como "
        "lista curta, uma observação por linha."
    )
    mensagens = [
        {"role": "system", "content": _SISTEMA},
        {"role": "user", "content": prompt},
    ]
    for modelo in (MODELO, MODELO_FALLBACK):
        try:
            resposta = cliente.chat.completions.create(
                model=modelo, messages=mensagens, temperature=0.85, max_tokens=450,
            )
            texto = (resposta.choices[0].message.content or "").strip()
            if texto:
                return texto
        except Exception:
            continue
    return None
