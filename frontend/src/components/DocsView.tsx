import React from 'react';
import { ArchitectureGraph } from './ArchitectureGraph';
import { BookOpen, ShieldCheck, Search, PenTool, Compass } from 'lucide-react';

export const DocsView: React.FC = () => {
  return (
    <div className="docs-view">
      <ArchitectureGraph />
      <header style={{ marginBottom: '28px', borderBottom: '1px solid var(--color-border)', paddingBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BookOpen size={24} color="var(--color-primary)" aria-hidden="true" />
          <h1 className="card-title" style={{ fontSize: '1.6rem' }}>
            Como o Deep Research funciona
          </h1>
        </div>
        <p style={{ marginTop: '8px', color: 'var(--color-text-secondary)', fontSize: '0.95rem' }}>
          As quatro etapas, do plano ao dossiê.
        </p>
      </header>

      <div className="markdown-body">
        <h2>1. Visão Geral da Arquitetura</h2>
        <p>
          O <strong>Deep Research</strong> pega um tema, divide em pontos, busca fontes públicas e audita cada
          ponto nos 12 critérios. O dossiê só cita o que passou.
        </p>

        <div className="docs-steps">
          <div className="docs-step">
            <Compass size={20} style={{ marginBottom: '6px' }} />
            <h3 style={{ margin: '0 0 4px 0', fontSize: '0.95rem' }}>1. Planejamento (Plan)</h3>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--color-text-secondary)' }}>
              Divide o tema em pontos e define o que cada um precisa provar.
            </p>
          </div>

          <div className="docs-step">
            <Search size={20} style={{ marginBottom: '6px' }} />
            <h3 style={{ margin: '0 0 4px 0', fontSize: '0.95rem' }}>2. Busca Agêntica (Search)</h3>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--color-text-secondary)' }}>
              Quatro personas varrem a web em paralelo: Historiador, Visionário, Cético e Futurista.
            </p>
          </div>

          <div className="docs-step">
            <ShieldCheck size={20} style={{ marginBottom: '6px' }} />
            <h3 style={{ margin: '0 0 4px 0', fontSize: '0.95rem' }}>3. Auditoria (Audit)</h3>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--color-text-secondary)' }}>
              Cada ponto é julgado nos 12 critérios. Se não atingir o limiar, volta para a busca com o motivo.
            </p>
          </div>

          <div className="docs-step">
            <PenTool size={20} style={{ marginBottom: '6px' }} />
            <h3 style={{ margin: '0 0 4px 0', fontSize: '0.95rem' }}>4. Redação (Writer)</h3>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--color-text-secondary)' }}>
              Escreve o dossiê em Markdown com a fonte de cada trecho.
            </p>
          </div>
        </div>

        <h2>2. Como Formular Temas de Pesquisa</h2>
        <p>
          O campo aceita de <strong>5 a 500 caracteres</strong>. Quanto mais claro o recorte, melhor o plano: diga o
          período, o lugar ou a decisão que o tema precisa responder.
        </p>
        <ul>
          <li><strong>Bom:</strong> "O futuro da matriz de energia limpa no Brasil até 2035: viabilidade de hidrogênio verde, energia eólica offshore e gargalos de transmissão."</li>
          <li><strong>Evitar:</strong> "energia no brasil" (amplo demais, gera ambiguidades e pontos generalistas).</li>
          <li><strong>Evitar:</strong> perguntas com respostas fechadas de sim/não ou meras definições de dicionário.</li>
        </ul>

        <h2>3. Personas Investigativas Especializadas</h2>
        <p>
          A etapa de busca executa varreduras web independentes e paralelas utilizando um subconjunto selecionável
          de até quatro personas analíticas configurado no plano (via preferências de pesquisa <code>+</code>). O plano
          captura a seleção ativa de personas e a preserva durante toda a execução, sem impor obrigatoriamente todas as quatro:
        </p>
        <ul>
          <li><strong>Historiador:</strong> Levanta antecedentes, precedentes regulatórios, marcos legais e séries históricas comprovadas.</li>
          <li><strong>Visionário:</strong> Explora tendências emergentes, inovações tecnológicas e cenários de expansão de fronteira.</li>
          <li><strong>Cético:</strong> Procura ativamente contra-evidências, riscos financeiros, falhas documentadas e críticas de mercado.</li>
          <li><strong>Futurista:</strong> Projeta cenários prospectivos de médio e longo prazo, dependências sistêmicas e impactos de segunda ordem.</li>
        </ul>

        <h2>4. Auditoria de Qualidade e Limiar de Corte (11/12)</h2>
        <p>
          Cada ponto investigado só avança para a redação se for aprovado no checklist das <strong>12 perguntas de qualidade</strong> avaliadas pelo LLM forte:
        </p>
        <ol>
          <li>Clareza temática e resposta à pergunta principal do ponto.</li>
          <li>Corroboração canônica por fontes primárias independentes.</li>
          <li>Atualidade das evidências coletadas.</li>
          <li>Ausência de contradições internas não explicadas.</li>
          <li>Embasamento factual com dados concretos (sem alucinações).</li>
          <li>Aderência estrita ao escopo delimitado no plano.</li>
          <li>Profundidade analítica adequada ao público-alvo.</li>
          <li>Precisão métrica e quantitativa dos números citados.</li>
          <li>Neutralidade e equilíbrio na exposição de visões divergentes.</li>
          <li>Densidade de evidências por parágrafo.</li>
          <li>Declaração explícita de incertezas e lacunas de informação.</li>
          <li>Solidez lógica e causalidade demonstrável.</li>
        </ol>
        <p>
          O limiar padrão exige aprovação em pelo menos <strong>11 dos 12 critérios</strong>. Caso um ponto seja reprovado, o sistema executa buscas direcionadas para suprir as lacunas apontadas antes de tentar nova auditoria (até o teto de 4 tentativas).
        </p>

        <h2>5. Credenciais, Segurança e Precedência (RN-10)</h2>
        <p>
          O Deep Research implementa uma política de segurança rigorosa em camadas e resolução de parâmetros:
        </p>
        <ul>
          <li>
            <strong>Sessão Integrada Same-Origin:</strong> No navegador, o acesso é autenticado automaticamente via cookies HttpOnly SameSite=Strict assinados no mesmo endereço, sem exigir fornecimento manual de segredos no cliente. Chaves externas continuam suportadas para clientes programáticos via header <code>X-API-Key</code>.
          </li>
          <li>
            <strong>Cifra em Repouso:</strong> As credenciais cadastradas na aba de Configurações são cifradas no
            SQLite usando Fernet (AES-128-CBC com HMAC-SHA256).
          </li>
          <li>
            <strong>Precedência RN-10 (Adendo 002):</strong> O Banco de Dados Relacional Cifrado (tabela <code>credenciais</code>) possui
            prioridade primária sobre as variáveis de ambiente (<code>.env</code> ou sistema operacional). Quando cadastrada no banco com valor válido e não-vazio, a credencial salva tem prevalência; caso contrário, as variáveis de ambiente atuam como fallback seguro. A listagem de configurações indica em tempo real se a origem ativa provém de <code>banco_cifrado</code> ou <code>ambiente</code>.
          </li>
          <li>
            <strong>Exceção de Bootstrap:</strong> A chave-mestra de cifragem (<code>CREDENTIALS_MASTER_KEY</code>) permanece
            obrigatoriamente restrita ao ambiente do sistema operacional (<code>os.environ</code>), pois é indispensável para abrir e decifrar os registros da base relacional antes de qualquer consulta.
          </li>
          <li>
            <strong>Ausência Total (RN-02):</strong> Se uma credencial ou parâmetro estiver ausente tanto no banco cifrado quanto no ambiente, o sistema lança expressamente um erro <code>ValueError</code>, sem adotar fallbacks silenciosos ou hardcoded.
          </li>
        </ul>

        <h2>6. Contabilidade e Categorias de Fontes</h2>
        <p>
          Toda referência do ciclo entra nesta conta:
        </p>
        <ul>
          <li>
            <strong>Fontes Consultadas (<code>consultadas</code>):</strong> Páginas e documentos com leitura confirmada (status <code>read_ok</code>, texto obtido pelo Jina Web Reader).
          </li>
          <li>
            <strong>Fontes Utilizadas (<code>utilizadas</code>):</strong> Fontes explicitamente citadas no dossiê final publicado e rastreáveis às evidências comprovadas da pesquisa.
          </li>
          <li>
            <strong>Fontes Não Utilizadas (<code>nao_utilizadas</code>):</strong> Fontes lidas na varredura que não entraram no texto final (<code>consultadas</code> menos <code>utilizadas</code>).
          </li>
          <li>
            <strong>Pesquisas antigas e valores desconhecidos:</strong> quando a contagem não existe, a tela mostra <code>não disponível</code> em vez de zero.
          </li>
          <li>
            <strong>Isolamento Operacional:</strong> O carregamento e visualização da contabilidade de fontes consultam exclusivamente os registros analíticos já persistidos da pesquisa. Carregar fontes não executa novamente a pesquisa nem gera novos custos ou requisições adicionais de busca.
          </li>
        </ul>

        <h2>7. Integração com Webhook de Callback</h2>
        <p>
          O sistema pode notificar sistemas externos após a conclusão da redação. As notificações são assinadas via
          header <code>X-Hub-Signature-256</code> com HMAC-SHA256 utilizando a chave <code>WEBHOOK_HMAC_SECRET</code>.
        </p>

        <h2>8. Escopo dos Checkpoints</h2>
        <ul>
          <li>
            <strong>Checkpoint 1 (Atual):</strong> Execução síncrona com transições de estado reais (Plan → Search → Audit → Writer), renderização de dossiês Markdown e administração de credenciais.
          </li>
          <li>
            <strong>Checkpoint 2 (Futuro):</strong> Suporte a Server-Sent Events (SSE) para streaming em tempo real de tokens e eventos detalhados do agente.
          </li>
        </ul>
      </div>
    </div>
  );
};
