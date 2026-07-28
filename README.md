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
  financeiro/   # controle financeiro pessoal (pronto)
```

Cada módulo vive em `modules/<nome>/` como uma aplicação independente.

## Roadmap

1. Fundação/arquitetura
2. **Financeiro** — pronto
3. Projetos
4. Dashboard Geral
5. Hábitos
6. Humor
7. Livros
8. Música
9. Analytics
10. IA e Insights
