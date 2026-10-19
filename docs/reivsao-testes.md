RAG-05 - Resultado não foi o esperado
 RAG-05 | `chat "LCI paga imposto de renda para pessoa física?"` | Isenta para pessoa física, com fonte `document` | US1 |

RAG-06 - Resultado esperado mas pode melhorar a mensagem
 | RAG-06 | `chat "Quais são as regras do saque-aniversário do FGTS?"` (tema financeiro que não está na base) | `scope: "in_scope"`, resposta `Não encontrei essa informação nas fontes disponíveis.` (ou equivalente), `sources: []`. Não pode responder com conhecimento próprio. | US1 cen. 2, FR-005 |


ESC-09 - Resultado não foi o esperado, esperava resposta ambígua
 | ESC-09 | `chat "Como funciona o leão?"` | `ambiguous` com esclarecimento, ou `in_scope` falando de IR. Nunca `out_of_scope`. | Edge case "ambígua" |

Resultado não foi o esperado: "Não encontrei essa informação nas fontes disponíveis.",
 | FX-03 | `chat "Quanto está a moeda XYZ?"` | Mensagem amigável de moeda não suportada, com exemplos (USD, EUR, GBP, JPY, ARS, BTC). Sem valor inventado, `sources: []`. | Edge case "moeda não suportada" |


Não foi o esperado
  CALC-04 | `chat "Quanto é 10 dividido por 0?"` | Explica que a divisão por zero não tem resultado. Não inventa número. | US4 cen. 2 |