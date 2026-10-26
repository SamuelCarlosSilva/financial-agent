// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import './ToolStatus.css';

export interface ToolStep {
  tool:
    | 'guardrail'
    | 'search_financial_documents'
    | 'get_currency_quote'
    | 'calculate'
    | 'verify_grounding';
  /** Substitui o rótulo padrão da ferramenta. */
  label?: string;
  state: 'running' | 'done' | 'error';
  /** Título do documento, par de moedas ou expressão. */
  detail?: string;
}

export interface ToolStatusProps {
  steps: ToolStep[];
  id?: string;
  hidden?: boolean;
}

const TOOL_LABEL: Record<ToolStep['tool'], string> = {
  guardrail: 'Verificando o escopo',
  search_financial_documents: 'Buscando nos documentos',
  get_currency_quote: 'Consultando cotação',
  calculate: 'Calculando',
  verify_grounding: 'Conferindo a fundamentação',
};

/** Texto para leitor de tela: o estado não fica só na cor e na animação do ponto. */
const STATE_TEXT: Record<ToolStep['state'], string> = {
  running: ' em andamento',
  done: ' concluído',
  error: ' falhou',
};

/** Passos do agente no turno. Mudanças são anunciadas com `aria-live="polite"`. */
export function ToolStatus({ steps, id, hidden }: ToolStatusProps) {
  return (
    <ol className="fa-tools" aria-live="polite" id={id} hidden={hidden}>
      {steps.map((step, i) => (
        <li key={i} className={`fa-tool is-${step.state}`}>
          <span className="fa-tool-dot" aria-hidden="true" />
          <span className="fa-tool-label">{step.label ?? TOOL_LABEL[step.tool]}</span>
          {step.detail ? <code className="fa-tool-detail">{step.detail}</code> : null}
          <span className="fa-sr">{STATE_TEXT[step.state]}</span>
        </li>
      ))}
    </ol>
  );
}
