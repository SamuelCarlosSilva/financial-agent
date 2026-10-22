// Mensagens fixas do backend, copiadas de src/financial_agent/graph/prompts.py.
// O front as reconhece por igualdade de texto: mudar o backend exige mudar este arquivo
// (contrato em specs/002-web-chat-frontend/contracts/client-api.md).

export const OUT_OF_SCOPE_MESSAGE =
  'Sou um assistente especializado em finanças e só posso ajudar com temas como ' +
  'investimentos, câmbio, produtos e conceitos financeiros e cálculos financeiros. ' +
  'Como posso ajudar nesse assunto?';

export const CLARIFY_MESSAGE =
  'Não ficou claro para mim se sua pergunta é sobre finanças. Pode dar mais detalhes? ' +
  'Posso ajudar com investimentos, câmbio, produtos e conceitos financeiros e cálculos ' +
  'financeiros.';

export const NOT_FOUND_MESSAGE = 'Não encontrei essa informação nas fontes disponíveis.';

export const ADVICE_DISCLAIMER =
  'Esta resposta é informativa e não constitui recomendação de investimento.';

/** Núcleo do aviso, procurado com `includes` sem diferenciar maiúsculas. */
export const ADVICE_DISCLAIMER_CORE = 'não constitui recomendação de investimento';
