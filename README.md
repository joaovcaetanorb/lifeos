# LifeOS

Sistema pessoal de acompanhamento de vida — não é um app de finanças, hábitos ou produtividade isolado, e sim um painel único para entender melhor a própria vida e tomar melhores decisões ao longo dos anos.

Toda funcionalidade precisa passar no teste: **isso me ajuda a entender melhor minha vida e tomar melhores decisões?** Se não, não entra.

## Princípios

- Simplicidade e clareza acima de dashboards complexos — a tela inicial deve ser compreendida em menos de 30 segundos.
- Construção incremental: um módulo por vez, nunca em paralelo.
- Mobile-first, sem excesso de métricas ou gráficos.

## Stack

Python, Streamlit, SQLite, SQLAlchemy, Pandas (Plotly só quando necessário).

## Estrutura

```
modules/
  financeiro/      # controle financeiro pessoal (pronto)
  projetos/        # metas e projetos com orçamento e checklist (pronto)
  habitos/         # check-in diário de hábitos, streak e % cumprido (pronto)
  livros/          # estante e diário de leitura (pronto)
  musica/          # catálogo e diário de escutas (pronto)
  dashboard_geral/ # visão consolidada das áreas acima (pronto)
```

Cada módulo vive em `modules/<nome>/` como uma aplicação independente (roda
sozinho com `streamlit run app.py` de dentro da própria pasta).

## Como rodar

```
streamlit run app.py
```

Isso sobe o LifeOS inteiro num processo só: `app.py`, na raiz, junta todos os
módulos numa sidebar única (Geral, Financeiro, Projetos, Hábitos, Livros,
Música) via `st.navigation`. Nenhum módulo precisa ser alterado pra isso — cada um
continua funcionando sozinho (`streamlit run app.py` dentro de
`modules/<nome>/`) se precisar depurar um em isolamento.

## Roadmap

1. Fundação/arquitetura
2. **Financeiro** — pronto
3. **Projetos** — pronto
4. **Dashboard Geral** — pronto
5. **Hábitos** — pronto
6. Humor
7. **Livros** — pronto
8. **Música** — pronto
9. Analytics
10. IA e Insights
