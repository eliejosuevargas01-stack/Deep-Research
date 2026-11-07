/**
 * Tradução de falhas técnicas para texto que a pessoa consegue usar.
 *
 * Regra: toda mensagem diz o que falhou, o que aconteceu com o trabalho dela e
 * o próximo passo. Código HTTP, nome de provedor e stack só aparecem em
 * "Detalhes técnicos", nunca no corpo do aviso.
 */

export type TomFalha = 'erro' | 'aviso';

export interface FalhaApresentada {
  titulo: string;
  mensagem: string;
  detalhe?: string;
  tom: TomFalha;
}

export interface ContextoFalha {
  /** Ação que falhou, no infinitivo: "abrir a sessão", "salvar a credencial". */
  acao: string;
  tom?: TomFalha;
}

const LIMITE_DETALHE = 600;

function textoBruto(erro: unknown): string {
  if (erro instanceof Error) return erro.message || erro.name;
  if (typeof erro === 'string') return erro;
  if (erro && typeof erro === 'object') {
    try {
      return JSON.stringify(erro);
    } catch {
      return String(erro);
    }
  }
  return String(erro ?? '');
}

/** Status HTTP embutido no erro (classe ApiError ou mensagem legada). */
export function statusDeErro(erro: unknown): number | null {
  const status = (erro as { status?: unknown })?.status;
  if (typeof status === 'number' && status >= 400 && status <= 599) return status;
  const bruto = textoBruto(erro);
  const porHttp = bruto.match(/HTTP\s*(\d{3})/i);
  if (porHttp) return Number(porHttp[1]);
  const porStatus = bruto.match(/status\D{0,8}(\d{3})/i);
  if (porStatus) return Number(porStatus[1]);
  if (/failed to fetch|networkerror|load failed|network request failed|econnrefused/i.test(bruto)) return 0;
  return null;
}

function detalheDe(erro: unknown): string | undefined {
  const bruto = textoBruto(erro).trim();
  if (!bruto) return undefined;
  const status = statusDeErro(erro);
  const comStatus = status && status > 0 && !/HTTP\s*\d{3}/i.test(bruto) ? `HTTP ${status} · ${bruto}` : bruto;
  return comStatus.length > LIMITE_DETALHE ? `${comStatus.slice(0, LIMITE_DETALHE)}…` : comStatus;
}

interface TextoStatus {
  titulo: string;
  mensagem: string;
}

const POR_STATUS: Record<number, TextoStatus> = {
  0: {
    titulo: 'Sem conexão com o servidor',
    mensagem: 'Confira sua internet e tente de novo.',
  },
  400: {
    titulo: 'Não foi possível usar esses dados',
    mensagem: 'Revise o que foi enviado e tente de novo.',
  },
  401: {
    titulo: 'Sua sessão expirou',
    mensagem: 'Recarregue a página para entrar de novo. Suas pesquisas continuam salvas neste navegador.',
  },
  403: {
    titulo: 'Você não tem acesso a essa área',
    mensagem: 'Peça acesso a quem administra a conta.',
  },
  404: {
    titulo: 'Não encontramos essa pesquisa',
    mensagem: 'Ela pode ter sido apagada. Abra o Histórico e escolha outra.',
  },
  409: {
    titulo: 'Essa ação já está em andamento',
    mensagem: 'Espere ela terminar e tente de novo.',
  },
  422: {
    titulo: 'Faltou informação para continuar',
    mensagem: 'Confira os campos indicados e envie de novo.',
  },
  429: {
    titulo: 'Muitas tentativas em pouco tempo',
    mensagem: 'Espere um minuto e tente de novo.',
  },
  500: {
    titulo: 'O servidor travou no meio do caminho',
    mensagem: 'Nada foi perdido. Tente de novo. Se repetir, copie os detalhes técnicos e avise o suporte.',
  },
  502: {
    titulo: 'O serviço está fora do ar',
    mensagem: 'Costuma voltar em minutos. Tente de novo daqui a pouco.',
  },
  503: {
    titulo: 'O serviço está fora do ar',
    mensagem: 'Costuma voltar em minutos. Tente de novo daqui a pouco.',
  },
  504: {
    titulo: 'A resposta demorou demais',
    mensagem: 'Tente de novo. Se repetir, reduza o número de pontos da pesquisa.',
  },
};

const PROVEDOR = /LLM_PROVIDER_ERROR|EXTERNAL_PROVIDER_ERROR|PROVIDER_ERROR|upstream/i;
const TEMPO_ESGOTADO = /timeout|timed out|timed-out|ETIMEDOUT|504|deadline exceeded/i;

/**
 * Converte qualquer erro em título, mensagem e detalhe técnico.
 * Nunca devolve texto vazio: o fallback usa a ação informada pelo chamador.
 */
export function apresentarErro(erro: unknown, contexto: ContextoFalha): FalhaApresentada {
  const bruto = textoBruto(erro).trim();
  const tom = contexto.tom ?? 'erro';
  const detalhe = detalheDe(erro);
  const status = statusDeErro(erro);

  if (status === 0) return { ...POR_STATUS[0], detalhe, tom };

  if (status && POR_STATUS[status]) {
    return { ...POR_STATUS[status], detalhe, tom };
  }

  if (TEMPO_ESGOTADO.test(bruto)) {
    return { ...POR_STATUS[504], detalhe, tom };
  }

  if (PROVEDOR.test(bruto)) {
    return {
      titulo: 'O provedor de IA não respondeu',
      mensagem: 'O que já foi coletado continua salvo. Tente de novo em instantes.',
      detalhe,
      tom,
    };
  }

  if (status && status >= 500) {
    return { ...POR_STATUS[500], detalhe, tom };
  }

  return {
    titulo: `Não foi possível ${contexto.acao}`,
    mensagem: 'Tente de novo. Se continuar, veja os detalhes técnicos.',
    detalhe,
    tom,
  };
}

/** Atalho para mensagem curta de linha única, sem bloco de título. */
export function resumirErro(erro: unknown, contexto: ContextoFalha): string {
  const falha = apresentarErro(erro, contexto);
  return `${falha.titulo}. ${falha.mensagem}`;
}
