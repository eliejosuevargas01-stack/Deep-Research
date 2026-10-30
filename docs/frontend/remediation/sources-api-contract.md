# Contrato da API: Separação Contábil de Fontes (Consultadas, Utilizadas e Não Utilizadas)

Este documento define o contrato oficial de tipagem e endpoints para a separação pública de fontes de pesquisa (`consultadas`, `utilizadas` e `nao_utilizadas`), aplicável tanto à resposta do redator (`POST /api/v1/writer`) quanto ao endpoint de consulta sob demanda e hidratação de relatórios (`GET /api/v1/pipeline/{id_pesquisa}/sources`).

---

## 1. Definições Semânticas

1. **Fontes Consultadas (`consultadas`)**:
   - URLs HTTP(S) únicas efetivamente lidas com sucesso pelo Reader (`status == "read_ok"`), com corpus textual material registrado nas coletas do banco de dados (`conteudo_coletado`).
   - Engloba todas as personas, pontos e tentativas/rodadas da pesquisa.
   - **Exclusões estritas**: URLs candidatas da SERP não lidas (`snippet_only`), buscas preliminares, leituras com falha (HTTP 4xx/5xx/timeout) e links inventados **não** são considerados consultados.

2. **Fontes Utilizadas (`utilizadas`)**:
   - Fontes citadas explicitamente no texto Markdown do dossiê final publicado (`dossier_final`) e rastreáveis às evidências lidas com sucesso.

3. **Fontes Não Utilizadas (`nao_utilizadas`)**:
   - Subconjunto de fontes consultadas com sucesso que não receberam citação explícita no relatório final (`consultadas - utilizadas`).
   - Não representam fontes rejeitadas ou inválidas; representam material de referência e contexto investigado não diretamente citado.

---

## 2. Tipagem Canônica

### 2.1. TypeScript (Frontend)

```typescript
export type FontesStatus = 'completo' | 'parcial' | 'indisponivel';

export interface FonteItem {
  url: string;
  titulo?: string | null;
  dominio?: string | null;
}

export interface FontesResumo {
  id_pesquisa?: string | null;
  status: FontesStatus;
  total_consultadas: number | null;
  total_utilizadas: number | null;
  total_nao_utilizadas: number | null;
  consultadas: FonteItem[];
  utilizadas: FonteItem[];
  nao_utilizadas: FonteItem[];
  observacao?: string | null;
  artifact_hash?: string | null;
}

// Extensão no WriterResponse existente
export interface WriterResponse {
  id_pesquisa: string;
  tema: string;
  status: 'concluido' | 'incompleto' | 'falha';
  total_caracteres_dossier: number;
  concluido_em?: string | null;
  webhook_entrega?: WebhookEntregaMetadata | null;
  dossier_final?: string | null;
  dossier_resumo?: string | null;
  diagnostico?: string | null;
  qualidade_artigo?: Record<string, unknown> | null;
  fontes?: FontesResumo | null; // Aditivo opcional
}
```

### 2.2. Pydantic v2 (Backend)

```python
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

FontesStatus = Literal["completo", "parcial", "indisponivel"]

class FonteItem(BaseModel):
    url: str = Field(..., description="URL canônica pública da fonte")
    titulo: Optional[str] = Field(default=None, description="Título público da página/documento quando disponível")
    dominio: Optional[str] = Field(default=None, description="Domínio normalizado extraído da URL")

class FontesResumo(BaseModel):
    id_pesquisa: Optional[str] = Field(default=None, description="Identificador da pesquisa")
    status: FontesStatus = Field(..., description="Status de integridade contábil das fontes")
    total_consultadas: Optional[int] = Field(default=None, ge=0, description="Total de URLs únicas lidas com sucesso (null se desconhecido)")
    total_utilizadas: Optional[int] = Field(default=None, ge=0, description="Total de URLs citadas no dossiê final (null se desconhecido)")
    total_nao_utilizadas: Optional[int] = Field(default=None, ge=0, description="Total de URLs lidas mas não citadas (null se desconhecido)")
    consultadas: List[FonteItem] = Field(default_factory=list, description="Lista de fontes com leitura confirmada")
    utilizadas: List[FonteItem] = Field(default_factory=list, description="Lista de fontes citadas no artigo")
    nao_utilizadas: List[FonteItem] = Field(default_factory=list, description="Lista de fontes lidas sem citação no artigo")
    observacao: Optional[str] = Field(default=None, description="Observação diagnóstica sobre disponibilidade de evidências")
    artifact_hash: Optional[str] = Field(default=None, description="SHA-256 do texto publicado para vinculação estrita")
```

---

## 3. Endpoints da API

### 3.1. `GET /api/v1/pipeline/{id_pesquisa}/sources`

- **Finalidade**: Consulta somente-leitura do resumo contábil de fontes da investigação.
- **Comportamento**:
  - Hidrata relatórios existentes sem acionar modelos LLM, buscas, leituras de rede ou mutações de banco de dados.
  - Exige a mesma autenticação dos demais endpoints da API (`X-API-Key`, `Authorization: Bearer` ou cookie de sessão local assinado).
  - Retorna `HTTP 404` com `{"detail": "Pesquisa não localizada: <id>"}` caso o `id_pesquisa` não exista.
  - Retorna `HTTP 200` com `FontesResumo`.

### 3.2. `POST /api/v1/writer`

- A resposta `WriterResponse` inclui opcionalmente o campo de primeiro nível `fontes: FontesResumo`.
- Tanto para execuções novas quanto para respostas atendidas a partir do cache (`status == "concluido"`).

---

## 4. Exemplos de Payload

### 4.1. Pesquisa Completa (`status: "completo"`)

```json
{
  "id_pesquisa": "4f86d8b2-578b-4a5c-bb45-985f401cf012",
  "status": "completo",
  "total_consultadas": 3,
  "total_utilizadas": 2,
  "total_nao_utilizadas": 1,
  "consultadas": [
    {
      "url": "https://pt.wikipedia.org/wiki/Inteligencia_artificial",
      "titulo": "Inteligência artificial – Wikipédia",
      "dominio": "pt.wikipedia.org"
    },
    {
      "url": "https://exemplo.org/artigo-ia",
      "titulo": "Avanços em IA",
      "dominio": "exemplo.org"
    },
    {
      "url": "https://outrosite.com/dados",
      "titulo": null,
      "dominio": "outrosite.com"
    }
  ],
  "utilizadas": [
    {
      "url": "https://pt.wikipedia.org/wiki/Inteligencia_artificial",
      "titulo": "Inteligência artificial – Wikipédia",
      "dominio": "pt.wikipedia.org"
    },
    {
      "url": "https://exemplo.org/artigo-ia",
      "titulo": "Avanços em IA",
      "dominio": "exemplo.org"
    }
  ],
  "nao_utilizadas": [
    {
      "url": "https://outrosite.com/dados",
      "titulo": null,
      "dominio": "outrosite.com"
    }
  ],
  "observacao": null,
  "artifact_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

### 4.2. Relatório Legado sem Evidências Brutas de Leitura (`status: "indisponivel"`)

```json
{
  "id_pesquisa": "legacy-report-1234",
  "status": "indisponivel",
  "total_consultadas": null,
  "total_utilizadas": 1,
  "total_nao_utilizadas": null,
  "consultadas": [],
  "utilizadas": [
    {
      "url": "https://antigo.org/fonte-legada",
      "titulo": null,
      "dominio": "antigo.org"
    }
  ],
  "nao_utilizadas": [],
  "observacao": "Evidências brutas de coleta indisponíveis para este relatório legado.",
  "artifact_hash": "a1b2c3d4..."
}
```

*Nota para Frontend*: Em relatórios com `status: "indisponivel"`, os contadores desconhecidos vêm como `null`. Não apresente `0` para fontes consultadas ou não utilizadas; indique visualmente que as evidências completas não estão disponíveis para relatórios legados e exiba as citações conhecidas.

---

## 5. Regras de Segurança e Privacidade

1. **Campos permitidos**: Apenas `url`, `titulo` (opcional) e `dominio` (opcional).
2. **Campos estritamente proibidos**:
   - Nenhum ID interno (`source_id`, `chunk_id`, `ponto_id`, `claim_id`).
   - Nenhum trecho ou corpo de texto (`body`, `text`, `content`).
   - Nenhum hash interno de trechos (`body_hash`, `text_hash`).
   - Nenhum prompt, raciocínio (`reasoning`) ou envelope de inferência.
   - Nenhuma credencial ou parâmetro sensível na URL (dados de autenticação como `user:pass` e query params como `token`, `api_key`, `secret` são removidos na normalização).

---

## 6. Diretrizes Estritas para o Frontend (Vinculação de Artefato e Rejeição)

1. **Rejeição Obrigatória em caso de Divergência de Hash/ID**:
   - O frontend **deve rejeitar e descartar** ativamente o resumo de fontes caso haja divergência entre o `artifact_hash` do resumo e o hash SHA-256 do relatório em exibição (`dossier_final`), ou se o `id_pesquisa` diferir do relatório carregado.
   - O frontend **não deve** meramente emitir um aviso e prosseguir renderizando ou persistindo o resumo divergente no histórico. Caso o hash não coincida (por exemplo, após uma re-execução ou revisão), as fontes devem ser marcadas como indisponíveis/desatualizadas para o artefato em tela.
2. **Preservação Fiel de URLs e Caminhos**:
   - O frontend deve exibir as URLs exatamente como fornecidas pelo backend, preservando caminhos, maiúsculas/minúsculas e parâmetros de busca sem reescrever ou remover barras finais.
3. **Semântica de Valores Nulos**:
   - Contadores com valor `null` indicam evidência não observada ou legado; o frontend não deve convertê-los em `0` nem inferir completude da partição quando o status for `indisponivel` ou `parcial`.
