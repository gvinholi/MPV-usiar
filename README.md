# Automação de Licitações — Usinaria

Sistema de coleta e triagem auditável de oportunidades de licitação. O piloto inicial usa o PNCP como fonte principal e o perfil configurável USIAR.

O contrato oficial do projeto está em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Não altere arquitetura, tecnologias ou regras de negócio sem aprovação.

## Objetivo do piloto

Coletar oportunidades, aplicar triagem configurável e registrar de forma auditável o que foi coletado, unificado, candidato, selecionado, descartado (com motivo), pendente e quais documentos foram ou não acessados — em qual rodada e por quais fontes.

Duração prevista: 15 dias, 3 rodadas diárias.

## O que este sistema não faz

O piloto **não** automatiza:

* participação em pregões;
* envio de propostas;
* lances;
* comunicação automática com clientes;
* decisão automática por valor, distância ou prazo;
* classificação por IA.

## Estrutura

```text
docs/ARCHITECTURE.md    Contrato arquitetural
collector/              Coletor Python (domínio, aplicação, infra)
frontend/               Dashboard Next.js e BFF
```

O frontend Next.js está em `frontend/`, com instruções em [frontend/README.md](frontend/README.md).
A fundação do Commit 20 inclui layout responsivo, BFF OIDC, sessões server-side locais,
cliente HTTP tipado e testes. Sem provedor configurado, o acesso permanece bloqueado.
Não há dados fictícios nem escrita de revisões no frontend. Produção depende de um
SessionStore compartilhado aprovado; a implementação em memória não é habilitada em produção.
A infraestrutura Google Cloud entra em commits posteriores.

Execução local do frontend (Node.js 24.x e npm):

```powershell
cd frontend
npm.cmd ci
Copy-Item .env.example .env.local
npm.cmd run dev
```

Abra `http://127.0.0.1:3000`. Configuração OIDC, limitações e verificações estão no README
do frontend e na [seção 40 do contrato arquitetural](docs/ARCHITECTURE.md#40-fundação-frontend-e-bff).

## API HTTP

A API read-only é criada com FastAPI e expõe os recursos de consulta sob `/api/v1`.
Configure `DATABASE_URL` para execução real e inicie localmente com:

```powershell
cd collector
uvicorn collector.api.app:create_app --factory --reload
```

`/health` não acessa o banco e permanece público. `/ready`, que verifica a conexão,
e todas as rotas GET operacionais exigem Bearer selecionado por AUTH_MODE com a permissão
`dashboard:read`. A única escrita HTTP é `POST /api/v1/reviews`, protegida pela
permissão independente `reviews:write`. Uma permissão não concede a outra; um
principal pode receber ambas explicitamente.

Em desenvolvimento e testes, a documentação está em `/docs`, `/redoc` e
`/openapi.json`. Em `ENVIRONMENT=production` ou `prod`, esses endpoints ficam
desabilitados por padrão. `API_DOCS_ENABLED=true` permite habilitação explícita,
que deve ser acompanhada da proteção de rede e identidade adequada à implantação.

Exemplos de consulta (o perfil deve ser identificado por `profile_id` ou por um
`profile_code` não ambíguo). A tabela MVP deve selecionar `USIAR/v2` explicitamente e
enviar `operational_state` duas vezes para combinar `CANDIDATE` e `PENDING`:

```text
GET /api/v1/opportunities?profile_id=42227c23-f6ea-5a43-b640-56ed6eb6981c&operational_state=CANDIDATE&operational_state=PENDING&page=1&page_size=25
GET /api/v1/opportunities/by-source?source=PNCP&official_id=00509968000148%2F2026%2F3341&profile_code=USIAR
```

Um único `operational_state` continua aceito e a ausência do filtro preserva a
listagem anterior, inclusive para consumidores que consultam descartes. O frontend do
MVP deve sempre enviar os dois estados acima; o filtro é aplicado no PostgreSQL antes
de `COUNT`, `LIMIT` e `OFFSET`.

`AUTH_MODE` deve selecionar `oidc` ou `internal`. Para OIDC, configure:

```text
OIDC_ISSUER=https://issuer.example
OIDC_AUDIENCE=mpv-usiar-api
OIDC_JWKS_URL=https://issuer.example/.well-known/jwks.json
OIDC_ALGORITHMS=RS256
OIDC_JWKS_CACHE_SECONDS=300
```

Configuração ausente ou incoerente impede a inicialização da API. O provedor de
produção ainda não foi escolhido; conceda explicitamente `dashboard:read` e/ou
`reviews:write` conforme a função do principal. Tokens não devem ser colocados em
arquivos versionados nem registrados em logs.

`OIDC_JWKS_URL` deve ser uma URL HTTPS válida, sem credenciais embutidas. O conjunto
JWKS é mantido em cache pelo TTL configurado, entre 1 e 3600 segundos; chaves
desconhecidas podem provocar atualização do conjunto. A remoção de uma chave não tem efeito instantâneo enquanto
um conjunto ainda válido estiver em cache, portanto o TTL deve ser compatível com a
política operacional de rotação e revogação do provedor.

Exemplo de contrato, usando apenas um placeholder de credencial:

```http
POST /api/v1/reviews HTTP/1.1
Authorization: Bearer <token-oidc>
Content-Type: application/json

{
  "operational_resolution_id": "00000000-0000-0000-0000-000000000000",
  "decision": "SELECTED",
  "reason": "RELEVANT_SCOPE_CONFIRMED",
  "comment": "Escopo confirmado na revisão.",
  "idempotency_key": "review-request-0001",
  "allow_stale": false
}
```

O reviewer é derivado exclusivamente dos claims verificados `iss` e `sub`; nome e
permissões enviados no JSON são rejeitados. O campo `name` pode fornecer apenas o
display name. O endpoint retorna 201 em sucesso; 401/403 para autenticação ou
autorização, 404 para resolução inexistente, 409 para idempotência/stale e 422 para
payload inválido.

CORS fica desabilitado por padrão. Para desenvolvimento com um frontend separado,
defina `API_CORS_ORIGINS` como uma lista de origens explícitas separadas por vírgula.
Wildcard não é aceito e credenciais CORS não são habilitadas.

## Coletor

Requer Python 3.13+.

```powershell
cd collector
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -m "not postgres"
```

## PostgreSQL local

O banco de desenvolvimento sobe com Docker Compose na porta **5433** (para não conflitar com um PostgreSQL local na 5432). Copie `.env.example` para `.env` e ajuste se necessário. Não commite `.env`.

```powershell
docker compose up -d
cd collector
$env:DATABASE_URL = "postgresql+psycopg://usiar:usiar@localhost:5433/usiar"
alembic upgrade head
python -m pytest -m postgres
docker compose down
```

`DATABASE_URL` é a única variável de conexão. A aplicação lê essa variável num único ponto de infra.

## Rodada operacional PNCP

Com o PostgreSQL iniciado e as migrations aplicadas, uma rodada completa coleta o
PNCP, persiste processos e observações, aplica um perfil USIAR explícito, cria a resolução
operacional inicial e atualiza as métricas da própria rodada:

```powershell
cd collector
$env:DATABASE_URL = "postgresql+psycopg://usiar:usiar@localhost:5433/usiar"
python -m collector.cli.collect run `
  --start-date 2026-10-10 `
  --end-date 2026-10-10 `
  --uf SP `
  --modality 6 `
  --profile USIAR/v2 `
  --max-pages 2 `
  --page-size 10
```

Use somente códigos de modalidade confirmados no contrato vigente do PNCP. Repita
`--modality` para consultar mais de uma modalidade. `--uf` é obrigatório para impedir
uma coleta nacional acidental; ele filtra a UF informada pela publicação e não comprova,
por si só, o local de execução do serviço. `--max-pages` é um limite explícito de
segurança por modalidade (padrão 200), não um modo silencioso de teste. O runner aceita
`USIAR/v1` e `USIAR/v2`; o padrão continua sendo `USIAR/v1` para impedir migração
silenciosa. Use `--profile USIAR/v2` em cada rodada que deva aplicar a nova triagem.

A última linha de sucesso é JSON e informa `round_id`, status, modalidades completas e
incompletas, registros recebidos, processos únicos, criações, contagens de
`CANDIDATE`/`PENDING`/`DISCARDED` e erros. Uma modalidade interrompida produz rodada
`PARTIAL` ou `FAILED`; não é reportada como sucesso vazio. Logs e erros não incluem
credenciais nem corpos brutos de respostas.

O código de saída permite automação sem interpretar o texto dos logs: `0` significa
`SUCCESS`, `1` significa `FAILED` ou falha operacional inesperada, `2` é erro de uso
dos argumentos e `3` significa `PARTIAL`. Agendadores devem aceitar somente `0` como
rodada completa; `3` preserva o progresso, mas exige alerta ou nova execução controlada.

Repetir internamente a persistência da mesma rodada é idempotente. Uma nova execução do
comando cria uma nova rodada e novas observações históricas, reutilizando a identidade
dos processos; revisões humanas anteriores não são sobrescritas. Ainda não há
checkpoint entre execuções: após uma interrupção, um novo comando reinicia a paginação
na página 1 e a deduplicação protege os processos. O agendamento das três rodadas
diárias permanece fora deste comando e deve invocá-lo externamente em horários
aprovados.

### Triagem contextual USIAR/v2

`USIAR/v1` permanece imutável e combina categorias encontradas em toda a descrição.
`USIAR/v2` associa serviço e contexto dentro da mesma cláusula por distância semântica:
conectores, números e unidades de medida não aumentam a distância, mas palavras de outro
escopo impedem a associação automática. Assim, “manutenção predial e aquisição de
aparelhos de ar-condicionado” é compra isolada, não manutenção de climatização.

No v2, manutenção preventiva/corretiva, PMOC, higienização e limpeza de dutos com
contexto comprovado são `CANDIDATE`. Manutenção com instalação, fornecimento ou peças,
contexto incompleto e refrigeração/HVAC sem vínculo explícito são `PENDING`. Instalação,
compra ou peças isoladas e climatização veicular são `DISCARDED`. Valor, modalidade,
município, distância, prazo, equipe e capacidade técnica não participam da decisão.
Os reason codes existentes são preservados; `EXCLUDED_CONTEXT` identifica somente um
contexto explicitamente fora do escopo predial. As evidências continuam registrando
categoria, termo configurado, campo e texto casado.

Depois que v1 e v2 forem persistidos, `API_PROFILE_CODE=USIAR` se torna ambíguo por
design. Para mudar a dashboard de forma explícita, deixe `API_PROFILE_CODE` vazio e
configure no servidor Next.js:

```powershell
$env:API_PROFILE_ID = "42227c23-f6ea-5a43-b640-56ed6eb6981c"
$env:API_PROFILE_CODE = ""
```

O UUID acima é a identidade determinística de `USIAR/v2`. A troca deve ocorrer somente
após uma rodada v2 ter persistido o perfil e suas avaliações. O corpus versionado está
em `collector/tests/application/screening/usiar_v2_corpus.json`; registros reais têm
`official_id` e URL de origem, enquanto exemplos complementares são marcados como
`synthetic`.

### Projeção de oportunidades para a tabela UsiAr

`GET /api/v1/opportunities` retorna uma linha por processo e usa a observação mais
recente. A resolução operacional só é projetada quando pertence a essa observação e ao
`profile_id` solicitado; uma observação nova ainda sem triagem v2 não reaproveita uma
classificação antiga. A ordenação sempre termina em `process_id ASC`, mantendo páginas
estáveis.

| Coluna UsiAr | Campo do endpoint | Semântica |
|---|---|---|
| ID RHS | `rhs_id` | `null` para oportunidades PNCP. |
| DATA / Hr | `publication_at` | Timestamp oficial; o frontend separa data e hora. |
| ORGÃO | `organization_name` | Organização oficial informada. |
| CIDADE | `municipality_name` | Município da unidade compradora; não implica local de execução. |
| TIPO | `modality` | Modalidade oficial. |
| SITE | `official_url` | URL pública validada, quando disponível. |
| N EDITAL | `notice_number` | Campo oficial nullable; nunca usa `numeroCompra`. |
| TIPO DO SERVIÇO | `operational_state` e `operational_reason` | Classificação auditável do perfil selecionado. |
| VALOR MENSAL | `monthly_value` | `null` enquanto indisponível em fonte oficial. |
| VALOR ESTIMADO | `estimated_value` | Valor estimado oficial, nullable. |
| OBSERVAÇÃO | `description_preview` | Trecho da descrição oficial, sem texto inventado. |

Os campos existentes foram reutilizados; apenas `rhs_id` e `monthly_value` foram
acrescentados como nullable. Para obter o objeto integral, use o endpoint de detalhe.

### Campos oficiais para a aba UsiAr

O snapshot da contratação preserva os campos oficiais usados pelo read model. No PNCP,
`linkSistemaOrigem` alimenta `official_url` somente como referência pública do sistema
de origem; endpoints técnicos da API e rotas inferidas do frontend PNCP não são usados.
URLs com credenciais, hosts locais/privados, fragmentos ou parâmetros sensíveis são
omitidas na resposta da API. Queries públicas necessárias, como `destino` e `compra`
do Compras.gov.br, são preservadas.

O OpenAPI e o Manual de Integração do PNCP expõem `numeroCompra`, `anoCompra` e
`processo`, mas não um campo inequívoco `numeroEdital` ou `numeroAviso`. Por isso
`notice_number` existe como campo nullable do contrato e permanece `null` para a fonte
PNCP. O sistema não concatena `numeroCompra/anoCompra` nem usa `numeroControlePNCP` ou
o processo administrativo como “N EDITAL”. O mapeamento completo e suas evidências
estão em [docs/PNCP_FIELDS.md](docs/PNCP_FIELDS.md).

### Bootstrap da autenticação interna

A fundação da autenticação própria mantém usuários, permissões, sessões opacas,
tentativas de login e auditoria no PostgreSQL. A migration `0009_internal_auth`
insere somente o catálogo `dashboard:read`/`reviews:write`; não cria credenciais. Depois de
aplicar as migrations, crie a primeira e única conta Admin/Dev de forma interativa:

```powershell
cd collector
$env:DATABASE_URL = "postgresql+psycopg://usiar:usiar@localhost:5433/usiar"
python -m collector.cli.auth bootstrap-admin
```

O comando lê a senha com `getpass`, exige ao menos 15 caracteres, concede as duas
permissões em uma transação e recusa execução quando já existe qualquer usuário.
Não passe senha na linha de comando e não registre sua saída em logs que contenham
entrada interativa. Não existe senha padrão ou usuário criado pela migration.

A FastAPI agora oferece login HTTP e sessões opacas quando `AUTH_MODE=internal`, com
as permissões persistidas aplicadas às mesmas verificações das rotas operacionais.
Não há JWT interno nem formulário frontend integrado; o fluxo OIDC permanece como
modo alternativo. Detalhes estão nas seções
[42](docs/ARCHITECTURE.md#42-fundação-da-autenticação-interna) e
[43](docs/ARCHITECTURE.md#43-autenticação-interna-da-fastapi).

Coleta, persistência, triagem, catálogo e aquisição de artefatos são passos separados. `CatalogProcessDocuments.catalog()` consulta metadados; `AcquireDocumentArtifact.acquire(document)` baixa um documento já catalogado, sob demanda.

## Catálogo de documentos PNCP

Endpoint observado (não inventado): `GET https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos`. A API de consulta (`/api/consulta`) responde 404 neste path.

A identidade documental é `PNCP` + `{cnpj}/{ano}/{sequencial}/{sequencialDocumento}`. Título e URL não são identidade. Zero documentos (`200` + `[]`) é sucesso; HTTP 404 de compra inexistente é falha. `Process.official_url` continua sem receber URL técnica de API. `documents_found` da rodada de coleta não é atualizado por este passo.

## Aquisição de artefatos

SHA-256 é identidade técnica do conteúdo observado, não versão oficial. O armazenamento local (`ARTIFACT_STORAGE_PATH`, default `var/artifacts`) é content-addressed e não entra no Git. Limite padrão: `DOCUMENT_MAX_DOWNLOAD_BYTES=52428800` (50 MiB). Destinos privados e esquemas não HTTP(S) são bloqueados. ZIP é inspecionado sem extrair membros.

## Extração textual

`ExtractArtifactText.extract(artifact)` lê PDFs (diretos ou members de ZIP seguro) com `pypdf`, página a página. Sem OCR. PDF escaneado/sem texto vira `LIKELY_SCANNED`.

## Triagem e revisão em quatro camadas

```text
PNCP description → Initial Screening
                                 \
                                  → Operational Resolver → fila CANDIDATE/PENDING/DISCARDED
                                 /
documents → artifact → text → Document Screening
```

A triagem inicial lê a `description` PNCP. A documental lê o texto extraído. A resolução operacional decide o estado de trabalho **sem sobrescrever** as duas primeiras. Documento decisivo com cobertura completa pode recuperar um `DISCARDED` inicial ou confirmar um descarte. Ausência de evidência documental **não** descarta. Sem documento, o operacional replica a inicial.

A quarta camada é `Human Review`: uma pessoa registra `SELECTED`, `PENDING` ou `DISCARDED` sobre uma resolução específica. `SELECTED` significa seguir para análise/atuação, sem confirmar habilitação, participação, proposta ou contrato. `CONFIRMED` não é aceito. O resolver continua limitado a `CANDIDATE/PENDING/DISCARDED`.

`RecordHumanReview.execute(RecordHumanReviewCommand(...))`, em `collector.application.human_review`, recebe resolução, reviewer, decisão, motivo, comentário opcional, chave de idempotência do caller e `allow_stale=False`. O adaptador é `SqlAlchemyHumanReviewRepository`. Reviewer é identidade declarada, **não autenticada**; não há RBAC neste piloto.

Reviews são append-only; mudar de ideia cria nova linha. `OTHER` exige comentário e comentários têm limite de 4000 caracteres. Retry com a mesma chave global e payload idêntico retorna a mesma review; payload diferente falha. Resolução antiga é rejeitada por padrão; override explícito fica auditado. Nova resolução não herda decisão humana: exige revisão novamente.

As consultas `review_status_for_process(process_id, profile_id)`, `latest_review_for_resolution`, `list_reviews_for_process`, `list_queue` e `summary` preparam a leitura do dashboard. A fila distingue `NEEDS_REVIEW`, `SELECTED`, `HUMAN_DISCARDED`, `HUMAN_PENDING` e `STALE_REVIEW`. Descartes automáticos sem review ficam fora da fila principal, mas podem ser incluídos explicitamente. Nenhum estado humano é gravado em `processes` ou em métricas de coleta.

A migration `0008_human_reviews` introduz essa camada; `alembic upgrade head` aplica
também as migrations posteriores, inclusive em banco vazio. Detalhes de concorrência,
status e auditoria estão em [ARCHITECTURE.md](docs/ARCHITECTURE.md#35-revisão-humana-auditável).

## Read model / dashboard queries

`DashboardQueries` é a entrada de aplicação para summary, funil, oportunidades, detalhe, documentos, evidências, timeline, fila humana e rodadas. `SqlAlchemyReadModelStore` lê o mesmo PostgreSQL em transações `REPEATABLE READ / READ ONLY`; não coleta, adquire, extrai ou grava decisões. Sem migration, HTTP ou frontend.

```python
from datetime import UTC, datetime
from collector.application.read_model import (
    DashboardQueries, OpportunityFilters, Pagination, ProfileScope, TimeRange,
)
from collector.infra.database import SqlAlchemyReadModelStore

queries = DashboardQueries(SqlAlchemyReadModelStore(session_factory))
scope = ProfileScope(profile_id=profile.id)
period = TimeRange(datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 16, tzinfo=UTC))
summary = queries.dashboard_summary(scope, period)
page = queries.list_opportunities(
    scope, OpportunityFilters(human_decision="SELECTED"), Pagination(page=1, page_size=25)
)
detail = queries.get_opportunity(process_id, scope)
```

O intervalo é `[from_datetime, to_datetime)`. `summary.current_snapshot` mostra o estado **atual dos processos cuja primeira persistência está no período**; `period_activity` conta os eventos ocorridos no período, cada qual pelo timestamp documentado. O funil combina estágios e não é necessariamente monotônico. Não é um snapshot retroativo no fim do intervalo.

Perfil é explícito: id ou code; code com múltiplas versões exige id. Paginação server-side (25 por padrão, máximo 100), sort por allowlist e filtros SQL. SELECTED histórico/stale não aparece como seleção atual. DTOs preservam Decimal, timestamps com fuso e campos nulos. Documentos retornam metadados/snippets, sem conteúdo integral de PDFs, storage keys ou erros brutos de transporte. Semântica completa em [ARCHITECTURE.md](docs/ARCHITECTURE.md#36-read-model-e-consultas-do-dashboard).

## Camadas do coletor

* `collector.domain` — conceitos e regras de negócio; sem I/O e sem fornecedor.
* `collector.application` — orquestração de casos de uso; depende do domínio, não de adaptadores concretos.
* `collector.infra` — adaptadores (PNCP e PostgreSQL).

## Segurança

Credenciais não devem ser commitadas. Use `.env` apenas em desenvolvimento local. Em produção, use Secret Manager.

### Autenticação selecionável da FastAPI

`AUTH_MODE` é obrigatório e aceita somente `oidc` ou `internal`; configuração ausente,
inválida ou incompleta impede a inicialização. Em `oidc`, issuer, audience e JWKS URL
continuam obrigatórios. Em `internal`, execute a migration `0009`, crie o primeiro
Admin/Dev pelo comando interativo documentado na seção 42 da arquitetura e defina um
`INTERNAL_AUTH_RATE_LIMIT_KEY` base64url canônico com pelo menos 32 bytes aleatórios.

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$env:INTERNAL_AUTH_RATE_LIMIT_KEY = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
$env:AUTH_MODE = 'internal'
```

`POST /api/v1/auth/session` aceita somente e-mail e senha e devolve uma sessão opaca
e um segredo CSRF. `DELETE /api/v1/auth/session` exige ambos como Bearer e
`X-CSRF-Token`. A API não define cookies. O BFF Next.js seleciona o mesmo `AUTH_MODE`:
em `internal`, envia credenciais somente server-side, cifra token e CSRF da API em cookie
HttpOnly e mantém o PostgreSQL como autoridade; em `oidc`, preserva Authorization Code
com PKCE. Consulte a seção 44 da arquitetura e o README do frontend.
