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
```

O dashboard Next.js e a infraestrutura Google Cloud entram em commits posteriores.

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

Coleta, persistência, triagem, catálogo e aquisição de artefatos são passos separados. `CatalogProcessDocuments.catalog()` consulta metadados; `AcquireDocumentArtifact.acquire(document)` baixa um documento já catalogado, sob demanda.

## Catálogo de documentos PNCP

Endpoint observado (não inventado): `GET https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos`. A API de consulta (`/api/consulta`) responde 404 neste path.

A identidade documental é `PNCP` + `{cnpj}/{ano}/{sequencial}/{sequencialDocumento}`. Título e URL não são identidade. Zero documentos (`200` + `[]`) é sucesso; HTTP 404 de compra inexistente é falha. `Process.official_url` continua sem receber URL técnica de API. `documents_found` da rodada de coleta não é atualizado por este passo.

## Aquisição de artefatos

SHA-256 é identidade técnica do conteúdo observado, não versão oficial. O armazenamento local (`ARTIFACT_STORAGE_PATH`, default `var/artifacts`) é content-addressed e não entra no Git. Limite padrão: `DOCUMENT_MAX_DOWNLOAD_BYTES=52428800` (50 MiB). Destinos privados e esquemas não HTTP(S) são bloqueados. ZIP é inspecionado sem extrair membros. Sem análise de texto.

## Camadas do coletor

* `collector.domain` — conceitos e regras de negócio; sem I/O e sem fornecedor.
* `collector.application` — orquestração de casos de uso; depende do domínio, não de adaptadores concretos.
* `collector.infra` — adaptadores (PNCP e PostgreSQL).

## Segurança

Credenciais não devem ser commitadas. Use `.env` apenas em desenvolvimento local. Em produção, use Secret Manager.
