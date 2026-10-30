# Documentação em HTML

Versão navegável da documentação, com o mesmo sistema visual do frontend
(tokens, tipografia, cores e componentes). É estática: não precisa de Node nem
de servidor de aplicação.

## Abrir

- Duplo clique em [`index.html`](index.html); ou
- sirva a pasta para evitar restrições de `file://`:

```bash
python3 -m http.server 8099 --directory docs/html
```

Depois acesse `http://127.0.0.1:8099/`.

## Conteúdo

| Página | Fonte |
| :--- | :--- |
| `index.html` | [`../README.md`](../../README.md) |
| `arquitetura.html` | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| `api.html` | [`../API.md`](../API.md) |
| `operacoes.html` | [`../OPERATIONS.md`](../OPERATIONS.md) |

A busca é offline: o índice em `assets/search-index.js` é gerado no build e
carregado por cada página. Não há requisições externas.

## Regerar

Os arquivos Markdown continuam sendo a fonte de verdade. Depois de editá-los:

```bash
.venv/bin/pip install markdown
.venv/bin/python scripts/build_docs_html.py
```

O script:

1. remove o H1 de cada fonte (vira título do cabeçalho);
2. converte Markdown em HTML com tabelas, blocos de código e âncoras;
3. reescreve links entre documentos (`docs/API.md` → `api.html`) e links para
   arquivos do repositório;
4. gera `assets/search-index.js` e as quatro páginas;
5. sincroniza as fontes de `frontend/dist/assets` para `assets/fonts/`.

## Estrutura

```
docs/html/
├── index.html
├── arquitetura.html
├── api.html
├── operacoes.html
└── assets/
    ├── docs.css
    ├── docs.js
    ├── search-index.js
    ├── favicon.svg
    └── fonts/
```
