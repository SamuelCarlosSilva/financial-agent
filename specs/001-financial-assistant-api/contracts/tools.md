# Contrato das Ferramentas do Agente

Cada ferramenta tem responsabilidade única (Princípio III). A docstring abaixo é o **contrato
exposto ao LLM** e deve ser implementada literalmente, ou com uma melhoria equivalente revisada.
Todas usam `response_format="content_and_artifact"`: o `content` (texto) vai para o LLM e o
`artifact` (`SourceCitation`) vai para a API.

Erros esperados **não** levantam exceção. Eles voltam como `content` descritivo com artefato
`None`, para que o LLM informe o usuário sem inventar valores (FR-012).

---

## `search_financial_documents(query: str) -> str`

```text
Busca trechos relevantes na base de documentos financeiros do projeto
(regulamentos, lâminas de fundos, glossários, políticas).

Use para perguntas conceituais ou sobre produtos/regras financeiras.
NÃO use para cotações de moedas nem para cálculos.

Args:
    query: pergunta ou termos de busca em português, autocontida
        (resolva referências do histórico antes de chamar).

Returns:
    Até 4 trechos numerados com título e origem, ou a mensagem
    "NENHUM_RESULTADO_RELEVANTE" se nada superar o limiar de relevância.
```

- Artefato: `list[DocumentSource]`.
- Regras: `query` com 1–500 caracteres, k=4, `score >= RAG_MIN_SCORE`.
- Citações: cada busca do turno numera seus trechos em uma faixa própria ([1–4], [5–8], ...)
  e o agente cita os números que usou (`[1]`, `[1, 3]`). Só os trechos citados na resposta
  final entram em `sources`; os trechos parecidos que não respondem à pergunta ficam de fora,
  e uma resposta "não encontrei" sai com `sources == []`. O limiar sozinho não separa esses
  casos: na calibração com `grounding.jsonl`, o trecho certo da pergunta respondível mais
  difícil teve 0.41 e o melhor trecho de uma pergunta sem resposta chegou a 0.63.
- Trava de fundamentação (nó `enforce_grounding`): se o turno buscou documentos, não citou
  nenhum trecho e não tem outra fonte, a resposta é trocada por `NOT_FOUND_MESSAGE` e o evento
  `ungrounded_answer_replaced` vai para o log. O prompt sozinho não basta: no eval, o modelo
  às vezes ignorava os trechos e respondia de cabeça.

## `get_currency_quote(base: str, quote: str = "BRL") -> str`

```text
Obtém a cotação atual (em tempo real) de um par de moedas.

Use sempre que o usuário pedir valor de moeda ou conversão cambial;
para converter um montante, chame esta ferramenta e depois `calculate`.
Para conversões, use o valor de compra (bid) e informe isso ao usuário.

Args:
    base: código ISO 4217 da moeda de origem (ex.: "USD", "EUR").
    quote: código ISO 4217 da moeda de destino. Padrão "BRL".

Returns:
    Par, valor de compra (bid), venda (ask) e data/hora da cotação;
    ou mensagem de erro se o par não for suportado ou o provedor
    estiver indisponível.
```

- Artefato: `FxQuoteSource`.
- Erros: `PAR_NAO_SUPORTADO` (404 do provedor, com exemplos de moedas: USD, EUR, GBP, JPY,
  ARS, BTC) e `PROVEDOR_INDISPONIVEL` (timeout de 5 s ou 5xx).

## `calculate(expression: str) -> str`

```text
Avalia uma expressão aritmética com precisão decimal exata.

Use para QUALQUER número que precise ser calculado (conversões,
juros, percentuais, parcelas). Nunca calcule de cabeça.

Operadores suportados: + - * / ** % e parênteses. Use ponto como
separador decimal e escreva percentuais como fração (15% → 0.15).
Exemplo juros compostos: 10000 * (1 + 0.01) ** 12

Args:
    expression: expressão aritmética (máx. 200 caracteres).

Returns:
    "expressão = resultado" com o resultado arredondado para 2 casas
    decimais, ou mensagem de erro (divisão por zero, expressão inválida).
```

- Artefato: `CalculationSource`.
- Erros: `DIVISAO_POR_ZERO`, `EXPRESSAO_INVALIDA` e `VALOR_MUITO_GRANDE`.

---

## Nó `guardrail` (não é ferramenta do LLM)

- Entrada: a última `HumanMessage` e até 2 trocas anteriores (só texto).
- Saída: `ScopeDecision` via structured output.
- Mensagem padrão de recusa (constante `OUT_OF_SCOPE_MESSAGE`):
  > "Sou um assistente especializado em finanças e só posso ajudar com temas como
  > investimentos, câmbio, produtos e conceitos financeiros e cálculos financeiros.
  > Como posso ajudar nesse assunto?"
