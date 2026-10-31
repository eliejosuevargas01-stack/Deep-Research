# Adendo 002: Inversão da Precedência de Credenciais (Banco Cifrado > Ambiente)

> **Status:** Aprovado  
> **Data:** 2026-10-26  
> **Referência:** Revisão Normativa da Regra RN-10  

---

## 1. Motivação

Permitir o controle dinâmico dos modelos e parâmetros operacionais diretamente pelo painel administrativo/web sem que variáveis estáticas declaradas no arquivo `.env` travem ou sobreponham as configurações salvas pelo usuário no banco de dados relacional cifrado.

Na especificação original da RN-10, as variáveis de ambiente possuíam precedência estrita sobre o banco cifrado. Essa abordagem impedia alterações em tempo de execução via UI sempre que o servidor estivesse provisionado com valores em variáveis de ambiente, exigindo reinicialização de serviços ou modificações no arquivo `.env`.

---

## 2. Decisão Normativa (Revisão da RN-10)

A resolução de credenciais e parâmetros operacionais passa a obedecer à seguinte cadeia de precedência:

1. **Prioridade Primária — Banco de Dados Relacional Cifrado (tabela `credenciais`)**:
   - Se a chave estiver cadastrada com valor não-vazio (`valor is not None and valor.strip() != ""`), este valor é utilizado de forma prioritária.
2. **Prioridade Secundária (Fallback) — Variáveis de Ambiente (`os.environ` / `.env`)**:
   - Se a chave não existir no banco de dados (ou estiver com valor vazio), o sistema consulta a variável de ambiente correspondente.
3. **Exceção de Bootstrap — `CREDENTIALS_MASTER_KEY`**:
   - A chave-mestra de cifragem (`CREDENTIALS_MASTER_KEY`) permanece obrigatoriamente restrita ao ambiente do sistema operacional (`os.environ`), pois é indispensável para abrir e decifrar os registros da base relacional antes de qualquer consulta.
4. **Ausência Total**:
   - Se a credencial ou parâmetro estiver ausente tanto no banco cifrado quanto no ambiente, o sistema lança expressamente um erro `ValueError` sem adotar valores de fallback hardcoded (conforme diretriz RN-02).

---

## 3. Impacto nos Componentes do Sistema

| Componente | Artefato / Arquivo | Impacto |
|---|---|---|
| **Repositório de Credenciais** | `app/db/credentials_repository.py` | Inversão do fluxo de busca: consulta primeiro tabela `credenciais`, recorrendo a `os.environ` como fallback. |
| **Resolução de Credenciais** | `app/services/credential_resolver.py` | Adequação da lógica de resolução e inspeção de origem ativa (`banco_cifrado` vs `ambiente`). |
| **Frontend / Configurações** | `frontend/src/components/SettingsView.tsx` | Atualização do aviso explicativo de precedência RN-10 para refletir Banco Cifrado > Ambiente. |
| **Testes Automatizados** | `tests/unit/test_credentials_repository.py` | Atualização de cenários para validar precedência do banco sobre o ambiente e fallback seguro. |

---

## 4. Rastreabilidade e Conformidade

- **RN-02**: Proibição de fallbacks silenciosos ou hardcoded mantida integralmente em caso de ausência em ambas as camadas.
- **RN-10**: Atualizada normativamente por este adendo para: `Banco Cifrado (tabela credenciais) > Variáveis de Ambiente (.env) > Erro Explícito`.
- **RF-11 / RF-12**: Gestão administrativa de credenciais via rotas `/api/v1/admin/credentials` e criptografia Fernet/AES preservadas.
