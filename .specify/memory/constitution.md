<!--
Sync Impact Report
- Version change: template (unversioned) → 1.0.0
- Modified principles: n/a (initial ratification)
- Added principles:
  - I. Respostas Fundamentadas em Contexto Verificável (NÃO NEGOCIÁVEL)
  - II. Guardrail de Escopo Financeiro (NÃO NEGOCIÁVEL)
  - III. Ferramentas com Responsabilidade Única
  - IV. API Stateless com Estado no thread_id
- Added sections:
  - Restrições de Arquitetura e Segurança
  - Fluxo de Desenvolvimento e Quality Gates
  - Governança (preenchida)
- Removed sections: template slot PRINCIPLE_5 (project defines 4 principles)
- Templates: not modified (read constitution at runtime)
- Follow-up TODOs: none
-->

# Financial Agent Constitution

## Core Principles

### I. Respostas Fundamentadas em Contexto Verificável (NÃO NEGOCIÁVEL)

- Toda afirmação factual (cotações, taxas, índices, dados de produtos, regras e normas) DEVE
  derivar de contexto recuperado na própria requisição, via RAG ou chamada de API.
- Sem contexto suficiente, o assistente DEVE declarar que não sabe ou pedir esclarecimento.
  É proibido completar a resposta com conhecimento não verificado.
- Respostas DEVEM citar a fonte (documento ou endpoint) sempre que possível.
- Valores numéricos DEVEM vir de ferramentas. O LLM NÃO DEVE calcular ou estimar números de cabeça.

**Rationale**: em finanças, uma alucinação vira decisão errada, dano financeiro e risco
regulatório. Só confiamos no assistente se tudo o que ele diz puder ser verificado.

### II. Guardrail de Escopo Financeiro (NÃO NEGOCIÁVEL)

- Perguntas fora do domínio de finanças DEVEM ser recusadas com uma mensagem padronizada,
  antes de qualquer chamada a ferramentas ou recuperação de contexto.
- O guardrail DEVE ser um componente explícito e testável. Uma instrução solta no prompt não basta.
- Tentativas de prompt injection ou de contornar o escopo DEVEM ser tratadas como fora de escopo.
- A suíte de testes DEVE conter casos dentro e fora do escopo, incluindo casos-limite.

**Rationale**: um escopo restrito reduz a superfície de risco, o custo e a responsabilidade
legal, e mantém o produto focado.

### III. Ferramentas com Responsabilidade Única

- Cada ferramenta DEVE fazer exatamente uma coisa. Ferramentas "faz-tudo" são proibidas.
- Cada ferramenta DEVE ter uma docstring clara com propósito, parâmetros tipados, retorno e
  erros possíveis. É essa docstring que o LLM usa para escolher a ferramenta.
- Ferramentas DEVEM ser determinísticas para a mesma entrada externa e testáveis isoladamente,
  com dependências externas mockadas.

**Rationale**: ferramentas pequenas e bem descritas melhoram a seleção feita pelo LLM, facilitam
os testes e deixam as falhas rastreáveis.

### IV. API Stateless com Estado no thread_id

- Os processos da API NÃO DEVEM manter estado de conversa em memória entre requisições.
- O histórico da conversa DEVE ser persistido e recuperado exclusivamente pelo `thread_id`,
  por meio de um checkpointer ou armazenamento externo.
- Qualquer instância da API DEVE conseguir atender qualquer requisição de qualquer thread.
- Um `thread_id` ausente ou inválido DEVE ser tratado de forma explícita, com erro ou criação de
  nova thread, conforme o contrato da API.

**Rationale**: sem estado no processo, a API escala horizontalmente, é resiliente a reinícios e
tem um comportamento reproduzível.

## Restrições de Arquitetura e Segurança

- Segredos (chaves de API e credenciais) DEVEM vir de variáveis de ambiente e nunca podem ser
  versionados no código.
- Cada resposta DEVE gerar um log estruturado com as ferramentas chamadas e as fontes usadas,
  para permitir a auditoria do Princípio I.
- Dados pessoais ou financeiros do usuário NÃO DEVEM ser enviados a serviços externos além do
  estritamente necessário para responder.

## Fluxo de Desenvolvimento e Quality Gates

- Todo plano de implementação (`/speckit-plan`) DEVE passar pelo Constitution Check dos
  Princípios I–IV antes da fase de design.
- Todo PR que adicione ou altere uma ferramenta DEVE incluir a docstring completa e testes
  unitários.
- Mudanças no guardrail, no pipeline de RAG ou nos prompts DEVEM vir com os casos de avaliação
  atualizados (dentro/fora de escopo, fundamentação).

## Governance

- Esta constituição prevalece sobre quaisquer outras práticas ou convenções do projeto.
- Emendas são feitas por PR e DEVEM incluir um Sync Impact Report e o bump de versão semântico:
  MAJOR para remoção ou redefinição incompatível de princípios, MINOR para novo princípio ou
  seção, PATCH para clarificações.
- Toda revisão de código DEVE verificar a conformidade com os princípios. Qualquer violação
  justificada DEVE ser registrada na seção de Complexity Tracking do plano.

**Version**: 1.0.0 | **Ratified**: 2026-09-27 | **Last Amended**: 2026-09-27
