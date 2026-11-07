import { FlaskConical } from 'lucide-react';

const SUGESTOES = [
  {
    titulo: 'Matriz energética Brasil',
    descricao: 'Renováveis, hidrogênio verde e segurança energética.',
  },
  {
    titulo: 'IA generativa em TI',
    descricao: 'Produtividade, competências e automação de código.',
  },
  {
    titulo: 'Fusão nuclear comercial',
    descricao: 'ITER/SPARC, marcos e cronogramas operacionais.',
  },
  {
    titulo: 'Regulação global de IA',
    descricao: 'AI Act, EUA e marco brasileiro PL 2338.',
  },
  {
    titulo: 'Criptografia pós-quântica',
    descricao: 'Padrões NIST, migração de chaves e segurança bancária.',
  },
  {
    titulo: 'Baterias estado sólido',
    descricao: 'Densidade energética, veículos elétricos e custos.',
  },
];

/**
 * Hero/estado vazio da rota Pesquisa (sem pesquisa ativa): título + temas
 * de exemplo que preenchem o formulário. Estilo próprio do V12, reaproveitando
 * as classes .empty-state/.sample-topic-* do CSS legado.
 */
export function HeroV12({ aoEscolher }: { aoEscolher: (tema: string) => void }) {
  return (
    <section className="empty-state" aria-label="Comece uma investigação">
      <div className="empty-state-badge" aria-hidden="true">
        <FlaskConical size={22} />
      </div>
      <h2 className="empty-state-title">O que vamos investigar hoje?</h2>
      <p className="empty-state-text">
        Descreva o tema abaixo — o dossiê acompanha cada ponto ao vivo, com auditoria
        e fontes.
      </p>
      <ul className="sample-topics-grid" aria-label="Temas de exemplo">
        {SUGESTOES.map((s) => (
          <li key={s.titulo} className="sample-topic-item">
            <button
              type="button"
              className="sample-topic-card"
              onClick={() => aoEscolher(s.titulo)}
            >
              <span className="sample-topic-title">{s.titulo}</span>
              <span className="sample-topic-desc">{s.descricao}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
