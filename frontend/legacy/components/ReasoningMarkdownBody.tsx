import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Corpo markdown do cartão de raciocínio, isolado num chunk próprio.
 *
 * Antes este import vivia no cartão, que é montado junto com o feed: isso
 * puxava react-markdown + remark-gfm (~35 KB gzip) para o primeiro paint de
 * qualquer rota. Agora o chunk só baixa quando o primeiro cartão de trace
 * aparece, e o fallback do Suspense mostra o texto com negrito/código.
 */
function ReasoningMarkdownBody({ text }: { text: string }) {
  return (
    <div className="reasoning-markdown-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

export default React.memo(ReasoningMarkdownBody);
