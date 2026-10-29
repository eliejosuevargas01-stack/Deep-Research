import React, { useEffect, useState } from 'react';
import { ReasoningFeed } from '../components/ReasoningFeed';
import { ReasoningFeedItem } from '../types/stream';

/**
 * Harness de desenvolvimento do feed de raciocínio (rota #harness).
 * Existe só para inspecionar densidade/navegação sem rodar uma pesquisa real.
 * Não é montado em produção (checado por import.meta.env.DEV no App).
 */

const BASE = Date.now() - 6 * 60 * 1000;

function item(
  n: number,
  agentType: ReasoningFeedItem['agentType'],
  agentName: string,
  title: string,
  reasoning: string,
  extra: Partial<ReasoningFeedItem> = {}
): ReasoningFeedItem {
  return {
    id: `mock-${n}`,
    timestamp: new Date(BASE + n * 25_000).toISOString(),
    agentType,
    agentName,
    title,
    reasoning,
    status: 'concluido',
    streaming: false,
    details: { stage: agentType === 'planejador' ? 'plan' : agentType === 'auditor' ? 'audit' : agentType === 'redator' ? 'write' : 'search', duration_ms: 40_000 + n * 1000 },
    ...extra,
  };
}

const ITENS: ReasoningFeedItem[] = [
  item(1, 'planejador', 'Planejador', 'Plano — 4 eixos', 'Pedido normalizado: mapear impacto da IA generativa no atendimento bancário. Eixos: (1) custo por atendimento, (2) satisfação do cliente, (3) regulação do Banco Central, (4) empregabilidade nos call centers.'),
  item(2, 'busca', 'Historiador', 'Varredura Web — Historiador', 'Buscando a evolução histórica do atendimento bancário desde 2010, com foco na automação de primeiro nível e nos marcos regulatórios.'),
  item(3, 'busca', 'Visionário', 'Varredura Web — Visionário', 'Explorando cenários 2026-2030: agentes conversacionais com memória de longo prazo, integração com Open Finance e personalização em escala.'),
  item(4, 'busca', 'Cético', 'Varredura Web — Cético', 'Verificando se os ganhos de custo reportados resistem a auditoria: procurando estudos com grupo de controle e métricas de reabertura de chamados.'),
  item(5, 'busca', 'Futurista', 'Varredura Web — Futurista', 'Analisando sinais fracos: regulação de explicabilidade, auditoria algorítmica pelo Bacen e o custo reputacional de respostas erradas.'),
  item(6, 'busca', 'Cético', 'Varredura Web — Cético', 'Coleta falhou: 429 do provedor após 3 tentativas. Nenhuma evidência adicional incorporada.', { status: 'falha' }),
  item(7, 'auditor', 'Auditor', 'Auditoria — Ponto 1', 'Critérios 1-12 avaliados. Aprovados: clareza temática, corroboração canônica, atualidade, ausência de contradições, embasamento factual, aderência ao escopo. Reprovados: densidade de evidências e solidez lógica — duas alegações de custo sem fonte primária.'),
  item(8, 'auditor', 'Auditor', 'Auditoria — Ponto 2', 'Parecer: 11/12. A única lacuna é a ausência de série temporal completa para o custo por atendimento em 2025.'),
  item(9, 'redator', 'Redator Final', 'Redação do dossiê', 'Consolidando 42 fontes em 6 seções, com tabela comparativa de custo por canal e ressalvas metodológicas explícitas.'),
  item(10, 'busca', 'Historiador', 'Varredura Web — Historiador (retry)', 'Reprocessando as duas URLs que falharam na primeira rodada; agora com leitura integral de 18 trechos.'),
  item(11, 'busca', 'Futurista', 'Varredura Web — Futurista', 'Lendo documento do Banco Central sobre explicabilidade de modelos; trecho relevante identificado na seção 4.2.', { streaming: true, status: 'em_andamento', details: { stage: 'search', started_at: Date.now() - 42_000 } }),
  item(12, 'auditor', 'Auditor', 'Auditoria — Ponto 3', 'Aguardando consolidação das personas para iniciar a leitura em passes.'),
];

export const ReasoningHarness: React.FC = () => {
  const [itens, setItens] = useState(ITENS);

  // simula um delta ao vivo no cartão em streaming
  useEffect(() => {
    const t = setInterval(() => {
      setItens((prev) =>
        prev.map((i) =>
          i.streaming
            ? { ...i, reasoning: `${i.reasoning} Novos trechos lidos: ${Math.floor(Math.random() * 9) + 1}.` }
            : i
        )
      );
    }, 1200);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', marginBottom: 12 }}>Harness — feed de raciocínio</h1>
      <ReasoningFeed items={itens} isActive activeAgentName="Futurista" activeStageType="busca" />
    </div>
  );
};
