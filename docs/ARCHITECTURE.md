# Contrato arquitetural — Automação de Licitações (Usinaria)

Este documento é o contrato oficial do projeto. Não altere a arquitetura, tecnologias ou regras de negócio sem antes explicar o motivo e solicitar aprovação.

O desenvolvimento será feito de forma incremental, através de commits Git independentes. Cada commit deve possuir escopo pequeno, testável e claramente definido.

---

## 1. Objetivo do projeto

Construir um sistema automatizado capaz de coletar oportunidades de licitação, inicialmente utilizando o PNCP como fonte principal, aplicar regras configuráveis de triagem para o perfil USIAR e registrar de maneira auditável:

* o que foi coletado;
* o que foi considerado processo único;
* o que foi considerado candidato;
* o que foi selecionado;
* o que foi descartado;
* o motivo do descarte;
* o que ficou pendente;
* quais documentos foram encontrados;
* quais documentos não puderam ser acessados;
* em qual rodada cada informação foi detectada;
* quais fontes contribuíram para a descoberta.

O primeiro piloto terá duração de 15 dias, com 3 rodadas diárias.

O objetivo do piloto NÃO é automatizar participação em pregões, envio de propostas, lances ou comunicação automática com clientes.

---

## 2. Perfil inicial

O primeiro perfil será:

USIAR

Regras atuais de negócio:

### Interesse principal

* manutenção preventiva;
* manutenção corretiva;
* higienização.

Não existe restrição inicial de equipamento.

### Avaliação

Manutenção acompanhada de instalação deve entrar para avaliação humana.

### Não selecionar automaticamente

* instalação isolada;
* compra de aparelhos;
* fornecimento isolado de peças.

### NÃO usar como critério automático de descarte

* valor;
* distância;
* modalidade;
* exigência de equipe;
* capacidade técnica;
* prazo.

Esses dados devem ser apresentados para decisão humana.

As regras devem ser configuráveis e não podem ficar espalhadas pelo código.

---

## 3. Arquitetura

Arquitetura inicial:

```text
Google Cloud
|
+-- Cloud Scheduler
|
+-- Cloud Run Jobs
|       |
|       +-- Python Collector
|
+-- Cloud Storage
|
+-- Secret Manager
|
+-- IAM
|
+-- PostgreSQL
|
+-- Dashboard Next.js
```

A definição final entre Cloud SQL PostgreSQL e uma solução PostgreSQL gerenciada externa ainda deverá ser confirmada antes da implantação definitiva.

Não acople o código do domínio a um fornecedor de banco.

---

## 4. Tecnologias

### Coletor

Python 3.13+

Preferências:

* httpx;
* Pydantic;
* pytest;
* tenacity quando necessário;
* logging da biblioteca padrão;
* openpyxl para exportações Excel posteriormente.

### Frontend

Next.js
TypeScript
Tailwind CSS

### Banco

PostgreSQL

### Infraestrutura

Google Cloud:

* Cloud Run Jobs;
* Cloud Scheduler;
* Cloud Storage;
* Secret Manager;
* IAM.

### Versionamento

Git + GitHub.

---

## 5. PNCP

O PNCP é a fonte principal de coleta.

O sistema deverá trabalhar com a API oficial do PNCP e não depender de scraping da interface web quando houver endpoint oficial disponível.

O coletor deverá ser preparado para:

* consulta por período;
* modalidade;
* estado/localização quando suportado;
* paginação completa;
* retry;
* backoff;
* retomada;
* controle de páginas processadas;
* registro de falhas;
* deduplicação;
* revisita de publicações anteriores.

Não assumir que uma falha de consulta significa zero oportunidades.

Uma rodada parcial deve ser explicitamente marcada como parcial/falha.

---

## 6. Rodadas

Cada execução do coletor deve possuir um identificador único.

Exemplo conceitual:

```text
2026-09-25-01
2026-09-25-02
2026-09-25-03
```

Cada rodada deverá permitir registrar:

* início;
* fim;
* status;
* fonte;
* período consultado;
* páginas esperadas;
* páginas processadas;
* páginas com erro;
* quantidade de registros obtidos;
* quantidade de processos únicos;
* quantidade de candidatos;
* quantidade de descartados;
* quantidade de pendentes;
* quantidade de documentos encontrados;
* erros;
* informações de execução.

---

## 7. Raw data e evidências

As respostas brutas das fontes devem poder ser armazenadas para auditoria.

Documentos, editais, anexos e versões também deverão poder ser armazenados.

O banco deve guardar metadados e referências aos arquivos.

Não colocar grandes arquivos binários diretamente no PostgreSQL.

Arquivos devem ser tratados como objetos de armazenamento.

---

## 8. Processo único

Não usar o título ou o número visível do edital como identificador principal.

Usar os identificadores oficiais fornecidos pela fonte, especialmente os identificadores do PNCP.

O modelo deve permitir:

* deduplicação;
* atualização;
* múltiplas fontes;
* múltiplas detecções;
* múltiplos documentos;
* versões.

Possíveis duplicidades devem poder ser marcadas para conferência humana.

---

## 9. Triagem

O sistema deve separar claramente:

```text
PUBLICAÇÃO BRUTA
|
v
PROCESSO ÚNICO
|
v
CANDIDATO
|
+----> DESCARTADO + MOTIVO
|
+----> PENDENTE + MOTIVO
|
v
SELECIONADO
|
v
CONFIRMADO COM EVIDÊNCIA
```

Uma licitação não deve ser considerada confirmada apenas porque uma palavra-chave apareceu no título.

Sempre que a classificação exigir confirmação documental, registrar a evidência correspondente.

---

## 10. Perfis de busca

Não implementar as palavras da USIAR diretamente em condicionais espalhadas pelo sistema.

Criar uma estrutura de perfil configurável.

Exemplo conceitual:

```text
USIAR
|
+-- termos de inclusão
+-- termos condicionais
+-- termos de exclusão
+-- regras
+-- critérios de confirmação
```

O sistema deverá futuramente permitir outros perfis sem duplicação do código.

---

## 11. Fontes

### Principal

PNCP.

### Referência/benchmark

RHS, respeitando acesso, contrato e condições de uso.

### Possíveis fontes complementares

* BLL;
* BNC;
* Licitações-e;
* diários;
* portais oficiais de órgãos.

Não implementar integrações com fontes complementares sem que o acesso e as condições de uso estejam definidos.

Nenhuma fonte complementar deve ser necessária para o funcionamento básico do coletor PNCP.

---

## 12. Documentos

Uma contratação pode possuir múltiplos documentos.

Não criar somente um campo "url_edital" no modelo definitivo.

Criar uma relação de documentos.

Exemplos:

* edital;
* termo de referência;
* anexos;
* planilhas;
* documentos complementares.

Guardar:

* título;
* tipo;
* URL;
* identificador da fonte;
* data;
* versão quando disponível;
* localização no armazenamento quando aplicável.

O contrato observado da API de arquivos e a persistência do catálogo estão na seção 30. A aquisição de binários e o armazenamento local estão na seção 31.

---

## 13. Planilha

A planilha é uma interface operacional/saída, não a fonte primária de verdade do sistema.

O banco deve ser a fonte de verdade.

O sistema deverá posteriormente permitir exportar os processos selecionados para a planilha mestre escolhida pela Usinaria.

Preservar, quando aplicável:

* estrutura;
* fórmulas;
* hyperlinks;
* histórico;
* campos de revisão humana.

A integração definitiva com Google Sheets ou Excel ainda deve ser confirmada.

---

## 14. Dashboard

O dashboard deverá permitir visualizar pelo menos:

* processos;
* candidatos;
* selecionados;
* descartados;
* pendentes;
* motivo do descarte;
* evidências;
* documentos;
* rodada de detecção;
* fonte;
* data de publicação;
* data de detecção;
* situação da coleta.

Deve existir diferenciação visual entre:

* execução concluída;
* execução parcial;
* execução com falha.

Nunca apresentar uma rodada que falhou como "zero oportunidades".

---

## 15. IA

NÃO implementar IA para análise semântica de editais no MVP inicial.

A integração com OpenAI será considerada em etapa posterior.

O sistema deve, entretanto, ser projetado para que uma etapa posterior de análise de documentos possa ser adicionada sem reescrever o coletor.

---

## 16. Não fazer no MVP

Não implementar:

* automação de lances;
* participação automática em pregões;
* envio automático de propostas;
* envio automático para clientes;
* decisão automática baseada em valor;
* decisão automática baseada em distância;
* decisão automática baseada em prazo;
* dependência da RHS;
* IA obrigatória para classificação.

---

## 17. Testabilidade

Todo componente importante deverá possuir testes.

Priorizar testes para:

* paginação;
* retry;
* retomada;
* deduplicação;
* normalização;
* regras de triagem;
* classificação;
* documentos;
* falhas;
* rodadas.

O coletor não deve depender da API real do PNCP para executar os testes unitários.

Utilizar mocks/fixtures.

---

## 18. Observabilidade

Toda execução importante deve gerar logs estruturados.

Registrar:

* rodada;
* fonte;
* etapa;
* status;
* erro;
* quantidade processada;
* tempo.

Não registrar secrets, tokens ou credenciais.

---

## 19. Segurança

Credenciais nunca devem ser commitadas.

Usar:

`.env` localmente durante desenvolvimento.

Secret Manager em produção.

Princípio do menor privilégio para contas de serviço.

Não utilizar credenciais pessoais.

---

## 20. Estratégia de commits

O desenvolvimento seguirá aproximadamente:

1. Fundação e contrato arquitetural
2. Infraestrutura inicial
3. Modelo de dados
4. Cliente PNCP
5. Paginação e retomada
6. Armazenamento RAW
7. Perfil USIAR
8. Normalização e deduplicação
9. Motor de triagem
10. Estados e decisões
11. Documentos PNCP
12. Evidências
13. Rodadas
14. Logs e cobertura
15. Dashboard
16. Filtros/revisão
17. Exportação
18. Automação 3x/dia
19. Monitoramento
20. Benchmark RHS
21. Relatório do piloto

Não implementar vários commits de uma vez.

Antes de cada commit:

1. explicar objetivo;
2. listar arquivos a alterar;
3. implementar;
4. executar testes;
5. verificar lint/typecheck quando aplicável;
6. mostrar resumo;
7. sugerir mensagem de commit.

Ao terminar cada etapa, parar e aguardar aprovação.

---

## 21. Regra principal para o Cursor

Não invente requisitos.

Não simplifique regras de negócio importantes.

Não introduza uma nova biblioteca ou serviço sem justificar.

Não misture infraestrutura, domínio e interface.

Não avance automaticamente para o próximo commit.

O objetivo é construir um sistema pequeno, auditável, testável e expansível.

---

## 22. Modelo de domínio da coleta

Decisões do modelo de domínio. Não substituem as seções anteriores.

* **Fonte:** `Enum` com `PNCP` e `RHS`. É suficiente neste estágio: o conjunto de fontes é fechado e novas fontes só entram como membros quando o acesso for aprovado. Não usar strings soltas como `"pncp"`. Não há membro genérico "outras".
* **Identidade do processo:** UUID interno do sistema e uma ou mais identidades oficiais (`fonte` + identificador oficial da fonte). Título e número visível do edital não são identidade. O mesmo UUID interno pode reunir identidades de fontes distintas; o algoritmo de deduplicação não faz parte deste modelo.
* **Timestamps:** timezone-aware. O domínio não assume `America/Sao_Paulo`. Conversão para exibição fica nas bordas.
* **Rodada:** `SUCCESS` com zero registros coletados é distinto de `FAILED` e de `PARTIAL`. O status declara o desfecho da execução; as métricas não são inferidas a partir do status.
* **Métricas:** representação de contadores; sem cálculo automático.
* **Triagem:** estados `RAW`, `UNIQUE`, `CANDIDATE`, `SELECTED`, `PENDING`, `DISCARDED`, `CONFIRMED`. Motivo de descarte ou pendência é um campo opcional. As regras USIAR não estão neste modelo.

---

## 23. Cliente HTTP PNCP

Decisões do adaptador `collector.infra.pncp`. Não substituem as seções anteriores.

* A URL base oficial é `https://pncp.gov.br/api/consulta`, configurável no construtor. O path deste commit é `GET /v1/contratacoes/publicacao`.
* O cliente aceita `date` e formata `AAAAMMDD`. Não hard-code de UF (incluindo `SP`).
* Uma chamada busca exatamente uma página. Paginação automática, retry e mapeamento para `domain.Process` ficam para commits posteriores.
* A resposta é `PncpPublicationPage` (contrato da fonte em `infra`). Itens em `data` permanecem no formato JSON do PNCP.
* Dependência HTTP: `httpx`. Sem credenciais; `Accept: application/json` e `User-Agent` configurável.
* HTTP 200 é sucesso com corpo JSON. HTTP 204 No Content é sucesso sem conteúdo: página vazia (`data` vazia, contadores zerados, `empty=True`, `numero_pagina` da página solicitada), sem parse de JSON. Qualquer outro status vira erro explícito e não pode ser lido como zero oportunidades. 204 descreve só aquela chamada, não o desfecho de uma rodada multi-modalidade.

---

## 24. Paginação e resiliência

Decisões da orquestração em `collector.application`. Não substituem as seções anteriores.

* A paginação sequencial vive em `application`, não no domínio e não em `PncpClient`. O cliente continua devolvendo uma página por chamada.
* A aplicação depende da porta `PublicationPageFetcher`. `PncpPublicationFetcher` (infra) adapta `PncpClient` e classifica erros. A aplicação não importa `httpx` nem tipos internos do cliente.
* HTTP 204 na primeira página encerra a consulta com sucesso e zero itens. 204/vazio inesperado depois de páginas que ainda indicavam restante é coleta incompleta, não sucesso.
* Falha definitiva após retries (ou inconsistência de metadados, ou limite técnico) levanta `IncompleteCollectionError` com o progresso parcial. O retorno normal de `collect()` só ocorre quando `complete is True`. Páginas já obtidas não são descartadas nem apresentadas como coleta completa.
* Retry somente para falhas transitórias: timeout, transporte, HTTP 429 e HTTP 5xx. Sem retry para 4xx permanentes, JSON inválido ou payload inválido. Política configurável (`max_attempts`, atraso inicial, fator, teto). A espera é injetável; a implementação padrão usa `time.sleep`. Sem suporte a `Retry-After` neste commit (exigiria alterar o contrato de `PncpHttpError`).
* Limite máximo de páginas por consulta (`max_pages`, default 200) é proteção técnica contra loop ou metadados incorretos, não regra de negócio. Atingir o limite sem término natural deixa a coleta incompleta.
* Não há rate limiting nem intervalo fixo entre requisições bem-sucedidas neste estágio.

---

## 25. Mapeamento PNCP → domínio

Decisões do adaptador `collector.infra.pncp.mapper`. Não substituem as seções anteriores.

* A tradução de um item `data[]` para `domain.Process` vive na fronteira PNCP (`map_pncp_publication`). O domínio não conhece nomes da API. O paginador continua devolvendo a representação externa.
* Identidade oficial: `numeroControlePNCP` → `SourceIdentity(Source.PNCP, official_id)`. UUID interno é gerado por chamada (`uuid4`) ou recebido do chamador. Sem UUID determinístico e sem deduplicação.
* Campos PNCP utilizados: `numeroControlePNCP`, `orgaoEntidade.cnpj`, `orgaoEntidade.razaoSocial`, `objetoCompra`, `modalidadeNome`, `dataPublicacaoPncp`, `dataEncerramentoProposta`, `unidadeOrgao.ufSigla`, `unidadeOrgao.municipioNome`, `valorTotalEstimado`. Demais campos permanecem fora do domínio.
* Ausência legítima vira `None`. Não se inventam textos como "Não informado".
* Datas: o manual oficial declara `dataAberturaProposta` e `dataEncerramentoProposta` como horário de Brasília. As strings observadas não têm offset. Strings sem offset recebem UTC−03:00 (horário oficial de Brasília; sem horário de verão desde 2019), não porque a consulta tenha `uf=SP`. Offset explícito é preservado. `captured_at` é injetado, timezone-aware, e preenche primeira e última captura na primeira transformação. Sem pacote `tzdata`.
* URL: endpoint da API (`/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}`) ≠ página pública navegável. `linkSistemaOrigem` e `linkProcessoEletronico` também não são promovidos a `official_url`. O mapper deixa `official_url=None` até o commit de documentos/editais. Nenhuma rota de frontend (`/app/editais/...`) foi inferida. `build_pncp_api_resource_url` monta só o recurso técnico da API, sem alimentar o domínio.
* Valor estimado: `Decimal`, sem conversão via `float` como tipo intermediário inventado; números JSON já materializados em `float` usam `Decimal(str(value))`. Payload monetário inválido gera `PncpInvalidMoneyError`.
* Erros de mapeamento: `PncpMissingFieldError`, `PncpInvalidTypeError`, `PncpInvalidDateError`, `PncpInvalidMoneyError`, `PncpInvalidIdentityError`. Não vazam `KeyError`/`ValueError`/`TypeError` como contrato.

---

## 26. Orquestração multi-modalidade

Decisões de `collector.application.collection`. Não substituem as seções anteriores.

* O orquestrador (`CollectionOrchestrator`) executa uma coleta lógica: inicia `CollectionRound` em `RUNNING`, percorre as modalidades da request em sequência, pagina cada uma, mapeia itens via porta `PublicationMapper` e finaliza a rodada. Sem fail-fast global: falha em uma modalidade não impede as seguintes.
* Modalidades vêm só do chamador. Duplicatas na request são rejeitadas (não normalizadas), para não executar a mesma consulta duas vezes e não confundir a observação de duplicatas da fonte.
* Status da rodada: `SUCCESS` se todas as modalidades pedidas foram paginadas e mapeadas com sucesso, inclusive com zero registros. `PARTIAL` se houve falha ou item inválido, mas alguma parte útil foi obtida (modalidade completa, itens brutos ou processos mapeados). `FAILED` só quando nenhuma modalidade produziu coleta útil. Zero oportunidades válidas não é `FAILED`.
* Erro de mapper em um item: registra modalidade, índice e identidade disponível; preserva os demais itens; marca a modalidade incompleta; a rodada pode ficar `PARTIAL`. Não se inventa `Process` inválido.
* Paginação incompleta: mapeia os itens já obtidos, registra página/razão, marca a modalidade incompleta e segue.
* Duplicatas de `numeroControlePNCP` entre modalidades/páginas continuam nas observações brutas (`CollectionResult.processes`). A consolidação posterior calcula `unique_processes` sobre esse conjunto.
* Métricas preenchidas: `pages_processed`, `pages_with_error` (falhas de página), `records_collected` (itens brutos), `unique_processes` (grupos consolidados da rodada), `errors` (paginação + mapeamento). Candidatos/selecionados/pendentes/descartados/documentos ficam 0.
* Relógio injetável; um `captured_at` timezone-aware por rodada, aplicado a todos os processos. Sem `datetime.now()` espalhado no orquestrador.

---

## 27. Identidade, deduplicação e consolidação

Decisões de `collector.application.consolidation`. Não substituem as seções anteriores.

* **Observação** é uma ocorrência recebida na coleta (processo já mapeado). **Processo único** é o grupo consolidado das observações com identidade externa comprovadamente igual. A visão consolidada não substitui as observações.
* **Identidade externa** é `SourceIdentity(source, official_id)`. Para o PNCP: `Source.PNCP` + `numeroControlePNCP`. UUID interno não é chave de deduplicação e não é regenerado: o grupo herda o UUID do processo representativo.
* Deduplicação neste commit é **exata e conservadora**. Sem fuzzy matching. Sem equivalência inferida por título, descrição, CNPJ, valor, datas, número visível do edital ou similaridade textual.
* Sem matching cruzado inferido entre fontes. `PNCP/ABC` e `RHS/XYZ` só se unem se alguma observação do conjunto comprovar interseção exata de identidades.
* Agrupamento: componentes conectados por interseção exata de `SourceIdentity`. Se A compartilha identidade com B e B compartilha outra com C, A/B/C formam um único grupo. Uma observação que liga grupos antes separados une o componente; isso não é equivalência inventada — é o fecho transitivo da identidade comprovada.
* Representante do grupo: a observação com `last_captured_at` mais recente. Empate (incluindo ambos ausentes) preserva a ordem de entrada. As demais observações permanecem no grupo para auditoria. Sem merge campo a campo.
* Resultado auditável (`ConsolidationResult`): observações recebidas, processos únicos, duplicatas (`observações − grupos`), grupos e a relação grupo → observações. Ordem determinística: grupos na ordem da primeira observação do componente; observações internas na ordem de entrada.
* Integração: modalidades → paginação → mapper → observações → consolidação → resultado da rodada. `CollectionResult.processes` continua sendo as observações brutas; `CollectionResult.consolidation` é a visão consolidada. `CollectionRound.metrics.unique_processes` passa a ser a quantidade de grupos. Em rodada `PARTIAL`, esse número cobre só o conjunto efetivamente observado.
* Falha estrutural da consolidação levanta `ConsolidationError` e impede que a rodada seja marcada `SUCCESS`. Sem persistência, histórico entre rodadas ou merge persistente.

---

## 28. Persistência PostgreSQL e histórico

Decisões de `collector.application.persistence` e `collector.infra.database`. Não substituem as seções anteriores. Cloud SQL não é decisão deste commit.

* PostgreSQL é a fonte de verdade persistente no coletor. Acesso Python: SQLAlchemy 2.x, Alembic e `psycopg` 3. O domínio não importa SQLAlchemy, Alembic nem psycopg. A aplicação não importa psycopg nem SQLAlchemy. Modelos ORM não substituem `domain.Process`.
* Coleta e persistência são operações separadas: `orchestrator.collect(request)` depois `PersistCollection.persist(result)`. O orquestrador não grava no banco.
* **Processo** persistente (`processes`) é só a identidade interna (UUID, `created_at`, `updated_at`). Campos mutáveis da fonte não ficam aí.
* **Identidade externa** (`source_identities`): `UNIQUE(source, official_id)`. Uma identidade exata pertence a um único processo. Texto com CHECK (`PNCP`, `RHS`), sem ENUM nativo do PostgreSQL.
* **Observação** (`process_observations`) é snapshot append-only da rodada. `CollectionResult.processes` continua com as observações brutas em memória. A persistência guarda **um** snapshot por processo consolidado por rodada: o representante do Commit 07. `UNIQUE(round_id, process_id)`. Métricas da rodada seguem distinguindo registros brutos e processos únicos.
* **Rodada** usa `CollectionRound.id` como PK. Métricas principais são colunas explícitas, não JSON. Status e fonte são texto com CHECK. `finished_at` corresponde a `ended_at` do domínio.
* **Resultado de modalidade** (`collection_modality_outcomes`): `UNIQUE(round_id, modality_code)`. Erros de mapeamento em JSONB estruturado.
* Histórico entre rodadas: mesma identidade reutiliza o processo e cria nova observação. Reexecutar o mesmo `CollectionResult` é idempotente (mesma rodada, sem duplicar). Rodada já persistida com estado diferente levanta `IncompatibleRoundError`.
* Resolução cross-round: busca todas as identidades do grupo. Nenhuma existente → cria processo com o UUID do representante e associa identidades. Existentes no mesmo processo → reutiliza e anexa identidades novas. Existentes em processos distintos → `IdentityConflictError`, sem escolha silenciosa.
* Uma persistência = uma transação. Falha estrutural faz ROLLBACK. Exceções de driver viram `PersistenceError`; a causa técnica permanece encadeada.
* Schema de produção vem do Alembic. Desenvolvimento local: PostgreSQL 16 via Docker Compose (porta hospedeira 5433) e `DATABASE_URL`. Sem Supabase e sem Cloud SQL neste estágio.

---

## 29. Perfil USIAR e motor de triagem

Decisões de `collector.application.screening`. Não substituem as seções anteriores.

* Fluxo: coleta → consolidação → persistência → observação → avaliação por perfil. Coleta e triagem permanecem operações separadas. O motor não executa SQL.
* USIAR é o primeiro `ScreeningProfile` (`USIAR/v1`). Termos ficam na configuração do perfil, não no algoritmo. Outro perfil reutiliza o mesmo motor.
* O motor é determinístico, explicável e sem IA, embeddings, fuzzy matching ou análise de PDF/edital. Analisa só `description` do snapshot. Descrição vazia → `PENDING / EMPTY_DESCRIPTION`.
* Normalização: caixa, acentos, hífen, barra e pontuação simples; casamento por tokens consecutivos, sem substring dentro de outra palavra.
* Estados automáticos possíveis: `CANDIDATE`, `PENDING`, `DISCARDED`. O motor não atribui `SELECTED` nem `CONFIRMED`.
* O estado comercial pertence à **avaliação** (`screening_evaluations`), não ao processo persistente. Um processo pode ser descartado para USIAR v1 e reavaliado em v2 ou em outro perfil. Avaliações antigas não são sobrescritas.
* Precedência centralizada em `decide()`: serviço relevante (contexto HVAC + manutenção/higienização) → `CANDIDATE`; o mesmo com instalação ou compra/peças → `PENDING` (misto, sem descarte); só instalação, só peças ou só compra em contexto HVAC → `DISCARDED` isolado (peças prevalecem sobre “aquisição/fornecimento” genérico); só contexto HVAC, ou serviço sem contexto HVAC mas com instalação/compra/peças → `PENDING` ambíguo; nenhum sinal do perfil → `DISCARDED / NO_RELEVANT_SCOPE`. Valor, município, modalidade e prazo não entram na decisão.
* Reason codes estáveis separados do texto humano. Evidências em tabela filha (`screening_evidence`): categoria, termo configurado, campo e texto casado.
* Persistência: `screening_profiles` com `UNIQUE(code, version)` e JSONB da configuração; `screening_evaluations` com `UNIQUE(observation_id, profile_id, engine_version)`; mesma observação + nova versão do perfil cria nova avaliação.
* Métricas `candidates`/`pending`/`discarded` da rodada **não** são atualizadas neste commit. Rodadas já persistidas permanecem históricas. Integração futura deve calcular esses contadores a partir das avaliações da rodada/perfil, sem reescrever a rodada em silêncio.

---

## 30. Catálogo de documentos PNCP

Decisões de `collector.application.documents` e `collector.infra.pncp` (cliente de documentos). Não substituem as seções anteriores.

* Endpoint **observado** (não inventado): `GET https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos`. A API de consulta (`https://pncp.gov.br/api/consulta`) responde 404 neste path. O Swagger de consulta não lista `/arquivos`.
* Resposta observada: lista JSON (não o envelope `{documentos: [...]}` do manual de integração). Cada item tem `sequencialDocumento`, `titulo`, `url`, `uri`, `tipoDocumentoId`, `tipoDocumentoNome`, `tipoDocumentoDescricao`, `dataPublicacaoPncp`, `statusAtivo`, `cnpj`, `anoCompra`, `sequencialCompra`.
* `https://pncp.gov.br/pncp-api/v1/...` também responde, mas devolve URL com porta interna; o cliente usa `/api/pncp`.
* Identidade documental: `Source.PNCP` + `{cnpj}/{ano}/{sequencial}/{sequencialDocumento}`. `sequencialDocumento` é único na contratação, não global. Título, nome de arquivo e URL **não** são identidade (a URL variou entre aliases).
* `url` é a URL oficial do arquivo. A URL técnica do catálogo é o endpoint de metadados. A página navegável da contratação continua outro conceito. `Process.official_url` permanece `None`.
* Zero documentos = consulta `200` + lista vazia (sucesso). Compra inexistente = HTTP 404 (falha). Não confundir os dois. Lista vazia não foi observada na amostra de 10 contratações; o cliente trata `[]` como sucesso porque o contrato observado é uma lista.
* Catálogo e coleta são operações separadas: `CatalogProcessDocuments.catalog(query)` não roda automaticamente após a triagem. A regra futura esperada (CANDIDATE/PENDING consultam; DISCARDED normalmente não) **não** está automatizada neste commit.
* `CollectionRound.metrics.documents_found` continua sem integração. A métrica deste passo vive em `DocumentCatalogResult.documents_found` (documentos mapeados daquela consulta). O significado da métrica da rodada (únicos, observados ou processos com documento) ainda não foi definido.
* Persistência: `process_documents` (visão corrente, `UNIQUE(source, official_document_id)`, `last_seen_at`); `document_catalog_queries` (uma consulta); `document_observations` (snapshot append-only por consulta, `UNIQUE(query_id, document_id)`). Mesma consulta não duplica. Nova consulta registra nova observação. Sem download automático e sem análise de conteúdo.
* Sem campo de versão oficial no payload. Mudança de metadados observáveis fica no snapshot da observação; não se afirma que o arquivo mudou.

---

## 31. Aquisição segura de artefatos

Decisões de `collector.application.acquisition` e `collector.infra.acquisition`. Não substituem as seções anteriores.

* Documento PNCP (`process_documents`) ≠ artefato (`artifacts`). O artefato é o binário observado. SHA-256 é identidade **técnica local**, não versão oficial nem identificador PNCP.
* A aquisição é explícita: `AcquireDocumentArtifact.acquire(document)`. Não há `collect() → baixar tudo` e a triagem USIAR não muda.
* Download em streaming (httpx), com `DocumentAcquisitionPolicy` centralizada: 50 MiB por arquivo (os ZIPs observados no piloto tinham ~1,4–2,0 MiB), timeout 60s (a primeira tentativa com 30s falhou em conexão fria), no máximo 5 redirects. `Content-Length` é aviso; o limite real é pelos bytes recebidos.
* URL é entrada externa. Só `http`/`https`. Destinos loopback, RFC1918, link-local, multicast, reservados e não globais são bloqueados **depois da resolução DNS**, inclusive em redirects. Há janela TOCTOU/DNS rebinding entre o check e o connect; isto não é firewall.
* Storage abstraído (`ArtifactStorage`). Implementação local content-addressed: `var/artifacts/sha256/{ab}/{cd}/{sha256}`. Nome remoto é só metadado. Diretório em `.gitignore`.
* `UNIQUE(artifacts.sha256)` deduplica o blob. `document_artifacts` é histórico append-only documento ↔ artefato. Dois documentos PNCP com o mesmo hash compartilham o blob e **não** são colapsados. Hash diferente no mesmo documento cria novo artefato (“conteúdo técnico observado diferente”).
* Tipo por magic bytes: `PDF` (`%PDF-`), `ZIP` (`PK…`), senão `UNKNOWN`. UNKNOWN válido não é rejeitado. Content-Type e extensão não decidem o tipo.
* ZIP é inspecionado **sem extração**. Manifesto em `artifact_archive_entries`. Flags: path traversal, absoluto, symlink, criptografado, limites (500 entries, 100 MiB/entry, 250 MiB total descompactado, razão 100:1) via metadados ZIP, não extração.
* Filesystem e PostgreSQL não compartilham transação. Download vai para temp controlado; commit atômico; se o DB falhar depois de um blob **novo**, o órfão content-addressed pode ser reutilizado. Blob já compartilhado não é apagado.
* Sem extração textual, OCR, IA ou Cloud Storage neste commit. A extração textual está na seção 32.

---

## 32. Extração textual determinística

Decisões de `collector.application.extraction` e `collector.infra.extraction`. Não substituem as seções anteriores.

* Cadeia: `process_document` → `document_artifact` → `artifact` → `artifact_text_sources` → `text_extractions` → `text_extraction_pages`. A triagem inicial (descrição PNCP) **não** é alterada. A triagem documental é a seção 33.
* Biblioteca: `pypdf` (faixa `>=5.4,<7`), local, somente leitura. Sem OCR, Tesseract, JS, anexos ou serviço externo. Limitações: PDFs escaneados/sem camada de texto ficam `LIKELY_SCANNED`; layouts complexos podem perder ordem.
* PDF direto: o blob do artifact. PDF em ZIP: só se a reinspeção for `safe=True`; member materializado um a um, sem `extractall()`. Formato escolhido por magic bytes, não por extensão.
* Integridade: SHA-256 do storage é recalculado antes de extrair. Divergência → `ARTIFACT_INTEGRITY_MISMATCH`.
* Source member: path `artifact:{sha256}` (PDF direto) ou path do entry (ZIP) + `member_sha256`. Não é identidade oficial PNCP.
* Texto persistido **por página** (número humano a partir de 1), quase cru: só remove NUL e normaliza `\r\n`. Sem FTS, resumo ou correção.
* Heurística conservadora: há páginas e nenhuma tem texto após strip → `LIKELY_SCANNED`. Alguma página com texto → `DIGITAL_TEXT`. Extração sem páginas → `EMPTY_TEXT`.
* Policy: 50 PDFs/artifact, 100 MiB/member, 1000 páginas/PDF, 5 milhões de caracteres/PDF.
* Idempotência: `UNIQUE(source_id, extractor_name, extractor_version)`. Nova versão do extractor coexiste. Falha de um PDF no ZIP não apaga os outros.

---

## 33. Triagem documental determinística

Decisões de `collector.application.document_screening`. Não substituem as seções anteriores. **Ainda não existe decisão comercial final.**

* Duas avaliações independentes:

  ```text
  description PNCP  →  initial screening   (screening_evaluations)
  documents         →  artifact → text → document screening
                       (document_screening_evaluations)
  ```

  A triagem inicial do Commit 09 permanece histórica. Nunca se transforma `PENDING` em `CANDIDATE` atualizando a linha antiga.
* O motor documental reutiliza o mesmo `ScreeningProfile` (USIAR versionado). Termos de negócio não são duplicados nem hard-coded no motor. Cues de negação são linguísticos e ficam na `DocumentScreeningPolicy`.
* Unidade de análise: **página**. Não se concatena o edital inteiro. Evidência aponta documento/artefato/source/member, `extraction_page_id`, `page_number`, termo, categoria e snippet original.
* Casamento: mesma normalização da triagem inicial (caixa, acento, hífen, pontuação) via `tokenize_with_spans`. O match ocorre na forma normalizada; `matched_text` e snippet vêm do texto original, com offsets no original.
* Snippet: raio de 120 caracteres, teto de 300, reticências se truncado. Não guarda a página inteira. Não corta caractere combinante.
* Proximidade (determinística, sem NLP): HVAC e serviço/instalação/compra/peças só se combinam na **mesma página extraída** e com distância de tokens ≤ 80 (`proximity_token_window`). Páginas diferentes nunca se combinam. Mesma página muito distante não se combina automaticamente.
* Negação simples: se um cue configurado (`nao`, `sem`, `nao inclui`, `nao havera`, …) é sufixo da janela de até 6 tokens imediatamente antes do termo, o match é gravado com `negated=True` e não entra na decisão. Frases complexas não são interpretadas.
* Filename não decide. Só texto encontrado.
* Estados automáticos: `CANDIDATE`, `PENDING`, `DISCARDED`. Sem `SELECTED`, `CONFIRMED`, IA, OCR, FTS ou `confidence` numérico.
* Precedência: HVAC+manutenção/higienização próximos sem misto → `CANDIDATE`; o mesmo com instalação ou compra/peças (não negados, próximos do HVAC) → `PENDING` misto; só exclusão isolada próxima do HVAC e cobertura completa → `DISCARDED`; HVAC sem serviço próximo → `PENDING / DOCUMENT_AMBIGUOUS_RELEVANT_CONTEXT`; nenhum HVAC → `PENDING / DOCUMENT_NO_DECISIVE_EVIDENCE` (ausência de termo no texto extraído não prova irrelevância). `LIKELY_SCANNED`, falha ou formato não suportado tornam `complete=False` e bloqueiam descarte isolado.
* Fingerprint: SHA-256 UTF-8 de `profile.code/profile.version`, `engine_version` e member SHA-256 ordenados. Sem UUID de row, timestamp ou `acquisition_id`. Mesmo conjunto + perfil + engine → idempotente (`UNIQUE(process_id, profile_id, engine_version, document_set_fingerprint)`). Member/perfil/engine novos → nova avaliação. Histórico antigo permanece.
* Comparação `compare_screenings(initial, document)` expõe `state_diverged`, `reason_diverged` e `divergence_kind` (`NONE`, `STATE_ONLY`, `REASON_ONLY`, `STATE_AND_REASON`). Reason codes de namespaces diferentes: strings distintas contam como `reason_diverged`. A resolução operacional está na seção 34.
* Avaliação carrega um processo (ou um artefato) por vez. Sem regex catastrófica.

---

## 34. Resolução operacional

Decisões de `collector.application.resolution`. Não substituem as seções anteriores. **Esta camada não produz decisão humana nem `SELECTED`/`CONFIRMED`.** A quarta camada está na seção 35.

```text
PNCP description → Initial Screening
                                 \
                                  → Operational Resolver → fila operacional atual
                                 /
documents → artifact → text → Document Screening
```

* Três camadas independentes. Nenhuma sobrescreve a outra. `processes` **não** ganha `current_state` mutável. O estado atual é a resolução mais recente (`resolved_at DESC`, `created_at DESC`, `resolution_fingerprint DESC`).
* `OperationalResolver.resolve(initial, document | None)` é puro. Sem SQL, HTTP ou filesystem. Sem peso/confidence. Sem initial → `INITIAL_SCREENING_REQUIRED`. Processos ou perfis distintos → erro explícito. Document sozinho não resolve.
* Força documental: `POSITIVE_DECISIVE` (`DOCUMENT_RELEVANT_*`), `MIXED_DECISIVE` (`DOCUMENT_MIXED_*`), `NEGATIVE_DECISIVE` (`DOCUMENT_ISOLATED_*`), `NON_DECISIVE` (ambíguo, sem evidência, sem texto, cobertura incompleta).
* Matriz: sem documento → replica initial (`INITIAL_SCREENING_ONLY`); positivo → `CANDIDATE` mesmo com cobertura incompleta; misto → `PENDING`; negativo completo com evidência de exclusão → `DISCARDED`; negativo incompleto ou não decisivo → `PENDING` (nunca descarte). Documento não decisivo **não** mantém `DISCARDED` inicial.
* Fingerprint: SHA-256 de `profile.code/version`, versão do resolver, `initial:{hash do sinal inicial}` e `document:{document_set_fingerprint|NONE}`. Identidade inicial lógica = perfil + engine + campo + estado + reason + evidências ordenadas — **não** `evaluation.id`. O FK histórico usa o UUID da row.
* Persistência append-only: `operational_resolutions` com `UNIQUE(process_id, profile_id, resolver_engine_version, resolution_fingerprint)`. Fila: `list_current_resolutions(state=...)`. Métricas próprias (`recovered_from_initial_discard`, `candidate_downgraded_to_discarded`); não entram em `CollectionRound.metrics`.

## 35. Revisão humana auditável

```text
Initial Screening ──┐
                    ├─ Operational Resolution ── Human Review
Document Screening ─┘   CANDIDATE/PENDING/         SELECTED/PENDING/
                        DISCARDED                 DISCARDED
```

As quatro camadas são históricas e independentes. Human Review não atualiza processos, avaliações, evidências ou resoluções. `SELECTED` é exclusivamente uma decisão humana de seguir para análise/atuação; não atesta habilitação, documentação completa, participação, proposta, vitória ou contrato. `HumanReviewDecision` é separado de `ScreeningStatus`; não aceita `CANDIDATE` nem `CONFIRMED`.

**Aplicação.** `RecordHumanReviewCommand`, DTOs imutáveis, validação pura, compatibilidade `ALLOWED_REASONS`, política stale, derivação de status e filtros de fila estão em `application/human_review`. `HumanReviewRepository.record` é uma porta atômica: o adaptador precisa consultar latest e inserir na mesma transação. `HumanReviewQueries` define a porta de leitura. Não há SQLAlchemy na aplicação. O serviço fornece Clock interno em UTC (injetável para teste); o command não recebe horário do cliente.

**Reviewer e motivos.** `ReviewerIdentity` exige id estável não vazio (até 200 caracteres) e permite display name (até 200). Essa identidade é fornecida pelo caller, não autenticada; autenticação e autorização ficam para a API futura. Qualquer caller válido pode revisar. Razões permitidas:

| Decisão | Reason codes |
|---|---|
| SELECTED | RELEVANT_SCOPE_CONFIRMED, COMMERCIAL_INTEREST, TECHNICAL_FIT, REVIEWED_AND_APPROVED |
| DISCARDED | OUT_OF_SCOPE, ISOLATED_INSTALLATION, EQUIPMENT_PURCHASE_ONLY, PARTS_SUPPLY_ONLY, DEADLINE_NOT_VIABLE, TECHNICAL_REQUIREMENT_NOT_VIABLE, COMMERCIAL_DECISION, DUPLICATE_OPPORTUNITY, OTHER |
| PENDING | NEEDS_TECHNICAL_REVIEW, NEEDS_COMMERCIAL_REVIEW, NEEDS_DOCUMENT_REVIEW, INSUFFICIENT_INFORMATION, OTHER |

Comentário opcional até 4000 caracteres; `OTHER` exige conteúdo não branco. Descartes por prazo, exigência técnica ou decisão comercial são escolhas humanas após análise. Não são regras automáticas. Valor, distância, modalidade, equipe, capacidade técnica e prazo continuam proibidos como critérios de descarte automático.

**Modelo relacional.** `human_reviews`: UUID, sequência BIGINT identity única, FK obrigatória `operational_resolution_id`, reviewer id/display name, decisão, reason, comentário, chave global de idempotência, `allow_stale`, `was_stale_at_decision`, FK `latest_resolution_id_at_decision`, fingerprint e estado operacional de snapshot, decided_at/created_at. `process_id` e `profile_id` são obtidos pela FK da resolução (expostos no DTO), evitando duplicação e inconsistência. A FK continua a fonte principal. Não duplicamos razão operacional nem evidências. Cadeia: review → resolution → initial/document evaluation → evidence → extraction page.

Migration 0008 cria constraints de decisão/motivo, reviewer, chave, comentário e flags stale, índice de latest e triggers. Um trigger valida os snapshots e o mesmo processo/perfil para as duas resoluções referenciadas; outro rejeita UPDATE/DELETE. Não há métodos de edição/exclusão. Mudar de ideia exige nova review/chave. TRUNCATE continua disponível à infraestrutura de testes; não existe recurso de exclusão na aplicação. Administradores do banco ainda podem alterar schema/desativar triggers.

**Idempotência e concorrência.** O caller fornece chave global não vazia até 200 caracteres. Igualdade do payload é exata, incluindo resolution, reviewer/display name, decisão, motivo, comentário e `allow_stale`; timestamps e flags derivados não entram. Retry idêntico retorna antes da verificação stale, mesmo que outra resolução tenha surgido. Uma chave repetida com payload diferente gera `IdempotencyConflictError`. Advisory lock transacional por hash da chave serializa retries; UNIQUE e `INSERT ON CONFLICT DO NOTHING` protegem o banco. Colisões de hash só causam espera adicional. Não há lock distribuído.

Latest operacional usa processo **e perfil**, com a ordem já existente: `resolved_at DESC, created_at DESC, resolution_fingerprint DESC`. Resolução diferente da latest gera `StaleOperationalResolutionError` com ambos os ids. `allow_stale=True` permite decisão histórica e registra stale e latest observada; nunca transfere a decisão para outra resolução.

**Limitação de stale race.** A verificação ocorre na mesma transação do INSERT, sob READ COMMITTED. Não bloqueia a gravação de resoluções. Uma nova resolução pode ser confirmada entre SELECT e INSERT: os campos de auditoria registram a latest observada no check, não prometem exclusão de concorrência. A consulta posterior detecta STALE. Um teste provoca exatamente essa janela. Eliminar essa janela exigiria coordenação também com escritores de resolução; não introduzimos SERIALIZABLE global nem alteramos a terceira camada.

**Estado derivado por processo/perfil.** A review atual é a mais recente **sobre a resolução vigente**, ordenada por `decided_at DESC, created_at DESC, sequence DESC`. Nunca por UUID. Revisão de uma resolução antiga, mesmo gravada depois, não substitui a review da atual.

| Status | Definição |
|---|---|
| UNREVIEWED | Não há review da resolução atual nem histórico humano no processo/perfil. |
| REVIEWED | Há review sobre a resolução atual; a decisão pode ser SELECTED, DISCARDED ou PENDING. |
| STALE | Há histórico humano, mas nenhuma review sobre a resolução vigente. |

Sem resolução, `review_status_for_process` retorna `None`. STALE tem decisão/reason/reviewer atuais nulos; a decisão antiga permanece consultável no histórico. Nova review vigente retorna REVIEWED. PENDING humano é revisão registrada e inconclusiva, não ausência de revisão.

**Filas e métricas.** `NEEDS_REVIEW`: CANDIDATE/PENDING sem review vigente, incluindo STALE. `include_operational_discarded=True` também inclui descarte automático sem review; não cria review. Filas SELECTED/HUMAN_DISCARDED/HUMAN_PENDING usam a decisão vigente, inclusive quando alguém revisou um descarte automático. STALE_REVIEW expõe todo histórico obsoleto sem review vigente, inclusive descarte automático. A consulta sem filtro exclui apenas descartes automáticos sem review vigente, salvo inclusão explícita.

`ReviewQueueItem` expõe process/profile, resolution id/state/reason/resolved_at, human status/decision/reason/reviewer/reviewed_at; não carrega textos documentais. A query ranqueia resoluções e reviews em SQL e lê estado/histórico no mesmo statement. Ordem da fila: resolved_at/created_at/fingerprint descendentes; process/profile desempata entre escopos. Filtros finais são puros na aplicação. Para o piloto, a leitura materializa os itens atuais; paginação SQL fica para evolução com volume real.

`HumanReviewSummary` independente: current_resolutions, needs_review (exclui descarte automático), reviewed, stale_reviews (todos os estados operacionais), selected, human_discarded, human_pending, reviews_total e stale_overrides_total. Opcionais filtros por perfil. Current conta pares processo/perfil, histórico conta linhas. Summary usa snapshot REPEATABLE READ para manter seus dois SELECTs coerentes, sem locks de escrita. Não altera `CollectionRound.metrics`.

Sem novas dependências de runtime. Fora do escopo: CONFIRMED, auth/RBAC/accounts, dashboard/API/Next.js, threads/anexos humanos, edição/exclusão, IA/LLM/OpenAI/OCR, e-mail/Telegram/GCP/RHS, proposta ou participação automática.

## 36. Read model e consultas do dashboard

```text
Write Side → PostgreSQL → Read Model → Future HTTP API → Future Dashboard
```

Mesmo banco e schema dos commits anteriores. Sem event sourcing, CQRS distribuído, banco de leitura separado, materialized views ou cache. Nenhuma migration no Commit 16. As quatro camadas de decisão continuam independentes; SELECTED exclusivamente humano e CONFIRMED fora do escopo.

**Contratos.** `application/read_model` define dataclasses imutáveis, filtros, paginação, erros, `ReadModelQueries` (Protocol) e fachada tipada `DashboardQueries`. `infra/database/read_model_store.py` implementa a porta; `read_model_sql.py` contém projeção comum/filtros SQL; `read_model_timeline.py` contém a união de eventos. Nenhum método da fachada chama serviços de escrita ou integrações. As consultas abrem transação PostgreSQL `REPEATABLE READ` e executam `SET TRANSACTION READ ONLY`. Até uma tentativa acidental de DML nessa transação é rejeitada pelo banco. Fechar a sessão encerra o snapshot sem commit de escrita.

**Perfis.** Consultas com screening/resolution/review exigem `ProfileScope` com exatamente um `profile_id` ou `profile_code`. Code é aceito quando identifica uma única versão; se houver várias, `AmbiguousProfileError` exige id. Perfil inexistente gera `ProfileNotFoundError`. Não há USIAR hard-coded nem escolha implícita de versão ativa. Processo sem avaliação no perfil continua na lista, com campos de decisão nulos; dados de coleta/documentos não são atributos de perfil. Rodadas, documentos e cobertura de fonte não recebem perfil porque são globais.

**Estado atual.** Uma oportunidade por processo no perfil solicitado. Latest operational: `resolved_at DESC, created_at DESC, resolution_fingerprint DESC`, igual ao Commit 14. Latest human sobre essa resolução: `decided_at DESC, created_at DESC, sequence DESC`, igual ao Commit 15. Review histórica sem review vigente gera STALE e campos de decisão atuais nulos. A última review histórica aparece apenas no detalhe em campo separado. PENDING humano é REVIEWED. Filtros SELECTED usam exclusivamente a review vigente, nunca um histórico selecionado.

Latest observation: `captured_at DESC NULLS LAST, created_at DESC, id DESC`. A lista mostra a identidade da fonte da observação; se houver múltiplos official_ids na mesma fonte, escolhe o menor lexicalmente. Detalhe lista todas as identidades. Processo sem observação tem campos de observação nulos, sem criar description/deadline/valor/URL. `publication_at` projeta `published_at`; `proposal_deadline_at` projeta `closes_at`; `uf` projeta `state`; `municipality_name` projeta `locality`. Não existe título separado de processo no schema: busca e preview usam description. Não foi inventado título.

**Paginação e filtros.** `Pagination(page=1, page_size=25)`, page >= 1, tamanho 1..100, rejeita booleanos/fracionários. `Page` retorna tuple de items, page/page_size/total_items/total_pages; vazio tem zero páginas; página além do fim preserva total e retorna vazio. Lista, fila, documentos, evidências documentais, timeline e rodadas são paginadas no PostgreSQL. COUNT e página compartilham snapshot.

Filtros: operational_state, human_review_status, human_decision, source (qualquer identidade do processo), UF, municipality/locality, modality, intervalos de publicação/deadline/captura, has_documents, has_text, has_document_screening e substring case-insensitive de description. `ILIKE` parametrizado, sem FTS; %, _ e ! do caller são escapados como caracteres literais. Filtros de localidade/modalidade são igualdade exata. Busca e strings de filtro têm teto de 300 caracteres. Datas sempre timezone-aware; intervalo fechado no início e aberto no fim. Filtro captured usa o captured_at da observação vigente, sem substituir null por created_at.

Sort fechado: publication_at, proposal_deadline_at, estimated_value, latest_capture_at, operational_resolved_at, reviewed_at; ASC/DESC. Default latest_capture_at DESC. NULLS LAST em ambas as direções e desempate por process_id ASC; nomes de coluna/direção não são SQL fornecido pelo caller. UUID é desempate de paginação, nunca critério de latest review. Timeline tem ordem própria ascendente, rodadas started_at descendente.

**DashboardSummary e tempo.** Resposta composta por profile_id, period, CurrentSnapshot, PeriodActivity, PilotFunnel e SourceCoverageSummary. Não existem contagens temporais sem semântica explícita:

| Projeção/métrica | Timestamp e escopo |
|---|---|
| CurrentSnapshot.processes_total | Cohort por `processes.created_at`, primeira persistência, não primeira publicação/captura. |
| CurrentSnapshot estados operacionais/humanos | Latest atual de cada membro do cohort, sem filtrar suas resolutions/reviews por data; não é as-of histórico. |
| CurrentSnapshot documentos/artifacts/texto | Estado atual dos documentos dos processos do cohort. Um documento posterior ao período pode estar no snapshot atual. |
| PeriodActivity.records_collected, rounds_* | `collection_rounds.started_at`; soma records_collected e conta status persistido, incluindo RUNNING no total. |
| PeriodActivity.processes_first_seen | `processes.created_at`. Não é records_collected, nem soma de unique_processes por rodada. |
| PeriodActivity.documents_discovered | `process_documents.first_seen_at`. |
| PeriodActivity.document_screenings_total | `document_screening_evaluations.evaluated_at`, perfil solicitado. |
| PeriodActivity.operational_resolutions_total | `operational_resolutions.resolved_at`, perfil solicitado. |
| PeriodActivity.human_reviews_total | `human_reviews.decided_at`, perfil da resolução. Inclui histórico/overrides do período. |
| SourceCoverageSummary | Rodadas selecionadas por started_at; processos distintos observados nessas rodadas, agrupados por source. |

Sem limites, o escopo temporal é todo o histórico. Com limites, nenhum deles é ignorado. CurrentSnapshot contém processes_total, current_candidate/pending/discarded, needs_review, selected, human_pending/discarded, stale_reviews, documents_total/with_artifact/with_text. Não conta SELECTED histórico como atual. PeriodActivity contém contagens de eventos e rounds_total/success/partial/failed; rodadas são independentes do perfil. Valores monetários permanecem Decimal; timestamps permanecem aware, sem conversão de apresentação para São Paulo.

**PilotFunnel.** records_collected vem da atividade de rodadas no período. unique_processes é o tamanho do cohort. Initial candidate/pending/discarded usa latest initial de cada processo do cohort no perfil (`evaluated_at DESC, created_at DESC, engine_version DESC, id DESC`). document_evaluated conta processos do cohort com avaliação documental no perfil, não número de avaliações. Estados operational/human vêm do CurrentSnapshot. São estágios/unidades distintos e podem não ser monotônicos; não representar como percentuais de conversão sem análise adicional. `pilot_funnel` reutiliza a mesma composição do summary para não divergir.

**Detail.** Identidades, description integral do processo (não PDF), campos atuais de lista, ids/timestamps/source da observação, latest initial e evidências category/configured_term/matched_text/field, latest document evaluation e cobertura, current operational com ids das avaliações usadas, rule/fingerprint/divergências, current human e latest historical human, counters. Latest document: evaluated_at/created_at/fingerprint/id descendentes. Avaliações latest podem ser mais novas que a resolution: os ids da resolução deixam essa diferença auditável, sem fingir que a resolução já as incorporou. `divergence_kind` deriva dos dois flags persistidos, permanecendo null quando não há comparação documental. Evidências documentais paginadas referem-se à latest avaliação documental do perfil, retornam página/snippet/source path/hash/document_id/negated e nunca texto integral da página.

**Documentos e ZIP.** Latest acquisition por acquired_at/created_at/id descendentes; representa a última tentativa, inclusive se falhou. Não faz fallback silencioso para um artifact de tentativa anterior. has_artifact, has_text e counters atuais seguem essa mesma regra. Timeline preserva todas as tentativas anteriores. Acquisition status é projeção `COMPLETE`/`INCOMPLETE` de complete, ou null se não houve tentativa. SHA/type vêm do artifact persistido; não inventamos MIME/versão PNCP.

Para cada source, latest extraction usa finished_at/created_at/extractor_name/extractor_version/id descendentes. `extractions` traz metadata por source, sem texto/error_text. has_text requer pages_with_text > 0 nessa extração. Sem extração, status/páginas/likely_scanned são null; extração UNSUPPORTED persistida com zero páginas permanece zero/UNSUPPORTED. Documento com fontes de estados distintos recebe agregação `MIXED`, com detalhes individuais preservados. Counters do detalhe contam artifacts distintos ligados às últimas tentativas, sources com extração e páginas das latest extractions, sem duplicar artifact compartilhado entre documentos.

Membros ZIP vêm de archive entries/text sources persistidos. `safe` significa ausência dos flags has_unsafe_path/is_encrypted/is_symlink naquele entry; não certifica política global de tamanho/quantidade do ZIP. Sem source persistido, sha256/detected_type são null. `extracted` exige resultado DIGITAL_TEXT/EMPTY_TEXT/LIKELY_SCANNED; falha ou UNSUPPORTED não significam extração concluída. Diretórios e membros não processados permanecem consultáveis. Nenhuma query abre storage, baixa, inspeciona ou extrai arquivo.

**Timeline.** UNION ALL de fatos persistidos, sem tabela nova. Página ordenada por occurred_at ASC, event_type ASC, reference_id ASC; mesmo evento de extração compartilhado não duplica por documento. Metadados pequenos indicam o timestamp usado, não incluem texto documental ou payload arbitrário:

| Evento | Timestamp |
|---|---|
| PROCESS_FIRST_SEEN | processes.created_at (primeira persistência) |
| PROCESS_CAPTURED | process_observations.captured_at; se null, created_at com fallback identificado nos metadados |
| INITIAL_SCREENED | screening_evaluations.evaluated_at |
| DOCUMENT_DISCOVERED | process_documents.first_seen_at |
| DOCUMENT_ACQUIRED | document_artifacts.acquired_at; inclusive tentativa incompleta |
| TEXT_EXTRACTED | text_extractions.finished_at; inclusive falha/unsupported |
| DOCUMENT_SCREENED | document_screening_evaluations.evaluated_at |
| OPERATIONAL_RESOLVED | operational_resolutions.resolved_at |
| HUMAN_REVIEWED | human_reviews.decided_at |

Eventos de decisões respeitam o perfil; coleta/documentos são compartilhados. Não há timestamps gerados na leitura nem eventos de sucesso inferidos a partir de falhas.

**Rodadas e fontes.** CollectionRoundListItem/Detail preservam status, início/fim, páginas previstas/processadas/com erro, records_collected, unique_processes, métricas históricas, modalities_attempted e outcomes. Cada outcome expõe modalidade, complete, contagens, failed_page, indicador estruturado COLLECTION_FAILURE e quantidade de mapping_errors. Mensagens brutas de transporte e mapping errors não são devolvidas porque podem conter URLs/headers/segredos. SUCCESS com zero registros permanece distinto de FAILED/PARTIAL, mesmo com zero registros. SourceCoverageSummary enumera somente fontes realmente presentes nas rodadas selecionadas, sem inventar RHS.

**Fila humana.** DashboardReviewQueueItem combina OpportunityListItem com ReviewQueueItem, sem alterar o DTO antigo. A política pura `in_queue` do Commit 15 é compilada para predicados SQL por enumeração finita de estados possíveis. Paridade testada contra a fila antiga. Todos os filtros/paginação ocorrem em SQL. NEEDS_REVIEW exclui descarte automático por padrão, permite inclusão explícita; STALE_REVIEW permanece consultável; queues SELECTED/HUMAN_PENDING/HUMAN_DISCARDED usam review vigente. O sort padrão do novo contrato é captura recente, não ranking comercial.

**Segurança e not found.** OpportunityNotFoundError para process_id/source identity ausente, CollectionRoundNotFoundError para rodada ausente. Lookup source + official_id é parametrizado. DTOs não contêm DATABASE_URL, credenciais, headers, storage_key, requested/final download URLs ou erros brutos. URLs de referência persistidas passam por filtro conservador HTTP(S): rejeita credenciais embutidas, query/fragment, hosts locais/internos conhecidos e IPs não globais. URLs com query legítima também podem ser omitidas; não há resolução DNS/requisição na leitura. Source path de evidência/member é o identificador persistido do member, não storage key.

**Performance e limites.** Lista/fila usam window functions, subqueries/aggregações e projeção de apenas 300 caracteres da descrição; nenhuma consulta individual por processo. Medição: 4 statements (SET READ ONLY + perfil + count + página), tanto com 7 como com 30 processos; 3 são SELECTs. Documentos buscam extrações e members em lote para a página. Detalhe usa queries especializadas por seção, sem consulta por página/evidência. Contagens, detalhes e summaries compartilham snapshot consistente; teste concorrente confirma que uma inserção durante a leitura só aparece no próximo snapshot. Offset e ILIKE são adequados ao piloto; não há promessa de latência em milhões de linhas, FTS ou índices novos.

Sem dependências novas, schema/migrations intactos. Sem API HTTP, frontend, auth/RBAC, scheduler/GCP/Cloud Run, RHS novo, Google Sheets, IA/OpenAI/OCR/embeddings, Redis/Elasticsearch/materialized views ou export CSV/XLSX.
---

## 37. API HTTP read-only

```text
PostgreSQL
    ↓
SqlAlchemyReadModelStore
    ↓
DashboardQueries
    ↓
FastAPI
    ↓
Future Dashboard
```

A API FastAPI é uma borda síncrona e versionada em `/api/v1`. Endpoints de banco
usam funções `def`, permitindo ao framework executá-los fora do event loop. Cada
operação continua abrindo sua própria sessão no `SqlAlchemyReadModelStore`, em
transação `READ ONLY / REPEATABLE READ`; nenhuma `Session` é global ou compartilhada.

A camada HTTP depende apenas de `DashboardQueries` e DTOs de aplicação. Ela não
consulta models SQLAlchemy diretamente, não escolhe versões `latest`, não calcula
reviews stale, não reconstrói o funil, não abre artifacts/storage e não baixa ou
extrai documentos. Schemas Pydantic e mappings explícitos formam a barreira do
contrato HTTP.

Não existem rotas POST, PUT, PATCH ou DELETE. Também não há autenticação; a API não
deve ser exposta publicamente sem proteção apropriada de rede e identidade. CORS é
desabilitado por padrão e, quando configurado, aceita somente origens explícitas.

---

## 38. API autenticada de revisão humana

```text
OIDC Provider → Bearer JWT → JWKS Validation → reviews:write
                                                    ↓
POST /api/v1/reviews → RecordHumanReview → PostgreSQL
```

Esta seção estende a seção 37 e substitui, somente para revisão humana, a restrição
anterior de API integralmente read-only. A única escrita HTTP deste commit é
`POST /api/v1/reviews`. No Commit 18, as rotas GET ainda eram públicas e exigiam
proteção adicional de implantação; a seção 39 substitui essa limitação ao exigir
OIDC e `dashboard:read` nas leituras operacionais. A rota de escrita reutiliza
`RecordHumanReview` e `SqlAlchemyHumanReviewRepository`; decisão/motivo,
idempotência, stale, append-only, auditoria e atomicidade continuam pertencendo
às camadas existentes. A borda FastAPI não duplica essas regras e não compartilha
uma `Session` SQLAlchemy global. As rotas GET mantêm a semântica do Commit 17.

**Autenticação.** Bearer JWT é validado com `PyJWT[crypto]` e chave assimétrica
obtida por JWKS. Issuer, audience, URL JWKS, algoritmos aceitos e tempo de cache
são configuração de ambiente. A allowlist de algoritmos é definida no servidor;
algoritmos simétricos e tokens sem assinatura não são aceitos. Assinatura, `iss`,
`aud`, `exp`, `sub` e `nbf` quando presente são validados. A URL JWKS deve ser HTTPS,
sem credenciais embutidas, e vem exclusivamente da configuração — headers/claims do
token não escolhem endpoint. O conjunto JWKS possui cache com TTL entre 1 e 3600
segundos e permite atualização por `kid` desconhecido. Não existe cache individual de chave sem TTL.
A remoção/revogação de uma chave não é instantânea enquanto o conjunto atualmente
armazenado ainda estiver dentro do TTL. Configuração incompleta ou indisponibilidade da
validação falham de forma fechada. Tokens e headers de autorização não entram nos
logs nem nas respostas de erro.

**Identidade e autorização.** `AuthenticatedPrincipal` é imutável e contém
issuer, subject, display name e permissions. O identificador persistido do
reviewer é uma representação estável, inequívoca e reversível de `iss` + `sub`,
com separação por tamanho. Se exceder 200 caracteres, a requisição é rejeitada;
não há truncamento, hash ou colisão silenciosa. Display name vem somente do claim
`name` válido. Permissões vêm do claim OAuth2 `scope`, separado por espaços, e a
rota exige `reviews:write`; ausência nega por padrão. Identidade, display name e
permissões enviados no corpo são campos extras e são rejeitados.

**Contrato HTTP.** O payload aceita somente `operational_resolution_id`,
`decision`, `reason`, `comment`, `idempotency_key` e `allow_stale`. Decisões
permitidas continuam `SELECTED`, `PENDING` e `DISCARDED`, com reason code validado
pelo contrato do Commit 15. Sucesso retorna 201 e a representação auditável da
review. Credencial ausente/inválida retorna 401 com `WWW-Authenticate: Bearer`;
permissão insuficiente, 403; resolução inexistente, 404; conflito de idempotência
ou resolução stale, 409; payload/comando inválido, 422. Falha inesperada retorna
500 sanitizado. Indisponibilidade da configuração ou JWKS retorna 503 sem abrir a
rota de escrita.

**Configuração e implantação.** `OIDC_ISSUER`, `OIDC_AUDIENCE` e
`OIDC_JWKS_URL` são obrigatórios para habilitar a autenticação composta pela
aplicação; `OIDC_ALGORITHMS` e `OIDC_JWKS_CACHE_SECONDS` controlam allowlist e
cache. Dependências podem ser injetadas explicitamente em testes sem credenciais
reais. Nenhum provedor foi escolhido. Produção depende da aprovação do provedor,
dos valores de issuer/audience/JWKS e da concessão controlada de `reviews:write`,
além de proteção de rede e transporte TLS. Não há cadastro local, login/senha,
refresh token, revogação própria, RBAC em banco ou endpoint genérico de escrita.

Sem migration nova: a identidade OIDC derivada usa os campos auditáveis de reviewer
já existentes em `human_reviews`.

---

## 39. Proteção OIDC das consultas operacionais

```text
OIDC Provider → Bearer JWT → JWKS Validation
                                  ├─ dashboard:read → GET operacional / ready
                                  └─ reviews:write  → POST /api/v1/reviews
```

As consultas operacionais do dashboard deixam de ser públicas. Todas as rotas GET
sob `/api/v1`, além de `/ready`, exigem a mesma autenticação OIDC Bearer/JWKS da
seção 38 e a permissão explícita `dashboard:read`. A verificação é centralizada e
reutiliza `AuthenticatedPrincipal`; não há segundo validador JWT, segundo cliente
JWKS, RBAC no PostgreSQL ou permissão implícita. `reviews:write` não concede
`dashboard:read`, `dashboard:read` não concede `reviews:write`, e um principal pode
receber ambas somente quando o provedor as conceder explicitamente.

Os contratos de `DashboardQueries`, `SqlAlchemyReadModelStore`, filtros, paginação,
ordenação, schemas e respostas de sucesso permanecem inalterados. A autenticação e
autorização ocorrem antes de qualquer consulta operacional. Credencial ausente ou
inválida retorna 401; principal sem `dashboard:read`, 403; indisponibilidade do
serviço JWKS/configuração OIDC, 503; falha interna inesperada, 500 sanitizado. Tokens
e headers de autorização não são registrados. As transações de leitura continuam
`READ ONLY / REPEATABLE READ` e cada operação mantém sua própria sessão.

`/health` é a única rota funcional pública: retorna somente o estado básico do
processo e não acessa PostgreSQL nem dados operacionais. `/ready` consulta o banco e,
por isso, também exige `dashboard:read`. Não foi criado health check público com
consulta a dependências ou retorno de informações operacionais.

**Documentação e OpenAPI.** Em `development` e testes, `/docs`, `/redoc` e
`/openapi.json` permanecem disponíveis para desenvolvimento do cliente. Em
`ENVIRONMENT=production` ou `prod`, os três endpoints são desabilitados por padrão.
`API_DOCS_ENABLED=true` é um opt-in explícito; sua habilitação em produção depende
de proteção segura de rede/identidade na implantação. O OpenAPI usa HTTP Bearer com
`bearerFormat: JWT`, sem simular um fluxo OAuth2, e documenta `dashboard:read` nas
leituras protegidas e `reviews:write` na escrita.

Sem `OIDC_ISSUER`, `OIDC_AUDIENCE` e `OIDC_JWKS_URL`, as rotas protegidas falham de
forma fechada: ausência de credencial continua 401 e uma credencial Bearer não pode
ser validada, resultando em 503. Produção depende da configuração de um provedor
OIDC real, URL JWKS HTTPS, audience/issuer corretos, concessão dos scopes mínimos e
TLS/proteção de rede. O cache JWKS e suas limitações de rotação/revogação permanecem
os definidos na seção 38.

Sem migration, endpoint de escrita adicional, usuário/senha local ou mudança nas
regras de coleta, triagem, revisão humana, idempotência, stale e auditoria.

---

## 40. Fundação frontend e BFF

O Commit 20 adiciona `frontend/` ao mesmo monorepo: Next.js 16 App Router, Node.js
24.x, React 19, TypeScript strict, Tailwind CSS 4 e componentes shadcn/ui. A interface
usa Server Components por padrão, com Client Components restritos à interação do
layout. Sidebar responsiva, header, navegação, loading, erro e vazio são reutilizáveis.
Dashboard, Oportunidades, Fila de Revisão e Rodadas de Coleta têm páginas iniciais,
sem métricas, oportunidades fictícias, gráficos, tabelas completas ou decisões.

```text
Navegador → cookie opaco HttpOnly → Next.js BFF → Bearer → FastAPI → PostgreSQL
                                      ↕
                                Provedor OIDC
```

O frontend não tem ORM nem acesso direto ao PostgreSQL. Autorização efetiva continua
na FastAPI: `dashboard:read` para leitura e `reviews:write` para escrita, independentes.
Cada entrada de página protegida verifica sessão e `/ready` na API, além da proteção
do layout. A indisponibilidade não vira lista vazia. Não há consulta operacional
pública, proxy HTTP genérico nem endpoint BFF de escrita de revisão.

**OIDC.** `openid-client` 6 implementa discovery, Authorization Code com PKCE S256,
state e nonce aleatórios e validação de ID token com assinatura/JWKS habilitada
explicitamente. Issuer, client ID, autenticação do cliente e eventual audience/resource
são configuração exclusiva do servidor. Não há provedor ou credenciais reais presumidos.
ID token autentica no BFF; somente access token vai à FastAPI. Provedor deve anunciar
S256, usar endpoints HTTPS e retornar validade positiva do access token. Claims não
validados não concedem acesso. Redirecionamentos de chamadas OIDC são bloqueados.

**Transações e sessões.** Pré-login e transação OIDC expiram em cinco minutos. A
transação de callback é consumida atomicamente antes da troca do código, inclusive
quando o fluxo falha. A sessão usa identificador aleatório de 256 bits em cookie,
com chave hash no store. Access token fica somente no servidor; ID/refresh tokens
não são persistidos. Não há refresh; expiração requer novo login. Padrões: inatividade
de 30 minutos, máximo absoluto de oito horas e limite adicional da validade do token.
Nova autenticação substitui a sessão anterior. Logout POST invalida o store e apaga
cookie; não promete logout global do provedor ou revogação instantânea do access token.

Cookie HttpOnly, SameSite=Lax, Path=/ e sem Domain. Secure em produção/HTTPS;
prefixo `__Host-` em produção. HTTP de desenvolvimento usa nome sem esse prefixo.
Nenhum access token vai para JavaScript, HTML, RSC props, localStorage ou sessionStorage.
O token CSRF não é credencial OIDC e pode estar no formulário associado à sessão.

**CSRF e origem.** Login POST e logout exigem Origin exato, Fetch Metadata compatível,
tipo de conteúdo explícito e token sincronizador de sessão/pré-login, com comparação
em tempo constante. Callback usa state/nonce/PKCE e cookie de vínculo. URLs de retorno
são fixas e construídas de `APP_ORIGIN`, nunca de Host arbitrário ou retorno fornecido
pelo navegador. Corpo CSRF é limitado a 2 KiB. Logs de requisição do Next dev são
desabilitados para não expor código/state do callback; proxy de produção deve aplicar
a mesma política de sigilo.

**Limite de produção.** `SessionStore` possui implementação somente em memória para
desenvolvimento/testes em processo único. Reinício encerra sessões. Não é fallback
de produção: requisições falham fechadas enquanto não houver adaptador compartilhado
aprovado, mesmo com OIDC configurado. Build pode ser produzido, mas isso não habilita
autenticação de produção. A aprovação de store, TTL/consumo atômico, proteção em repouso,
TLS, segredos, política de SSO/revogação e controles operacionais precede implantação.

**Cliente HTTP.** Módulos `server-only` separam dados de interface. Operações de leitura
são nomeadas, com paths fixos, UUIDs e filtros validados e Bearer obtido exclusivamente
da sessão vigente. Base URL é configuração server-side; redirects e cookies do browser
são proibidos. Timeout padrão de 10 segundos, limite de resposta de 4 MiB, `no-store`
e schemas Zod evitam consumo/cache acidental de dados incompatíveis. Não há retry de
escrita. Erros 401/403/404/409/422/500/503, rede e timeout são normalizados; mensagens
internas e tokens não são expostos. 401 invalida sessão, 403 mantém acesso negado sem
loop. Request ID é criado pelo BFF e enviado à API para correlação.

**Contratos.** Schemas TypeScript/Zod são derivados do AST dos schemas HTTP Python,
sem importar ou alterar coletor/API. Script de geração e verificação de divergência
fica no frontend. Respostas preservam UUID, timestamps com fuso, strings decimais,
nulos e paginação. Queries preservam exatamente um perfil onde requerido, intervalo
`[início, fim)`, allowlist de sort/direction e limites da API. Campo de filtro interno
não exposto por HTTP não vira parâmetro no BFF. Regras de domínio permanecem na API.

**Exceção temporária de segurança do tooling.** Em 2026-10-08 foi aceita, somente
para desenvolvimento, a exposição ao advisory GHSA-vfj7-8cjw-p6xm /
CVE-2026-93687 em `braces@3.0.3`. A cadeia identificada é
`eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces`;
todos esses pacotes estão na árvore de desenvolvimento e `npm audit --omit=dev`
não encontra a dependência. Na data da decisão não existe versão corrigida publicada
de `braces`. O impacto potencial é stack overflow e negação de serviço ao processar
padrões glob especialmente construídos.

Essa aceitação não autoriza padrões glob vindos de fontes não confiáveis nas
ferramentas afetadas, nem a execução do tooling de desenvolvimento como serviço
exposto publicamente. O `npm audit` completo continua obrigatório e seu alerta deve
ser reportado como exceção, nunca ocultado ou contado como verificação aprovada. A
cadeia deve ser reavaliada assim que houver correção upstream. Esta decisão não é uma
aprovação geral de segurança para produção.

ESLint 9 permanece temporariamente com a configuração oficial do Next.js 16. A
migração para ESLint 10 aguarda suporte completo do Next e dos plugins instalados;
nenhuma regra de segurança ou qualidade foi desabilitada. O fim de suporte do ESLint
9 é risco residual conhecido e também deve ser reavaliado com a atualização upstream.

**Validação.** Vitest cobre configuração, protocolo OIDC com RSA/JWKS de teste,
nonce/state/PKCE/replay, cookies, expiração/invalidação, CSRF e cliente HTTP. Playwright
exercita fluxo real do BFF contra provedor HTTPS/API isolados de teste, desktop/mobile,
navegação, proteção de rotas, logout, falta de permissão e não exposição de tokens.
Fixtures não são importadas pelo aplicativo; não existe modo de bypass no runtime.
Lint, TypeScript e build são verificações separadas. Validação com provedor real
permanece dependente de configuração aprovada. Instruções em `frontend/README.md`.

Sem alteração de FastAPI, coletor, domínio, banco, migrations ou regras USIAR.
Sem implementação de funcionalidades do Commit 21, refresh token ou implantação.

---

## 41. Dashboard operacional

O Commit 21 substitui o estado preparatório de `/dashboard` pela primeira consulta
operacional do frontend. A página é um Server Component dinâmico e usa exclusivamente
`GET /api/v1/dashboard/summary`, por meio da operação nomeada já existente no cliente
BFF. O fluxo lê a sessão opaca pelo cookie HttpOnly, recupera o access token no
`SessionStore`, chama a origem fixa da FastAPI com `cache: no-store` e valida a resposta
com o schema Zod gerado. Não há chamada preliminar a `/ready`, proxy público ou token
serializado para o navegador.

`API_PROFILE_ID` e `API_PROFILE_CODE` são configuração exclusiva do servidor. A página
exige exatamente um deles antes de consultar a API; ausência, UUID inválido ou os dois
simultaneamente produzem um estado de configuração. A URL não aceita perfil. Quando o
código identifica várias versões, o `409 AMBIGUOUS_PROFILE` orienta o operador a usar
o UUID, sem seleção implícita. A resposta identifica o perfil apenas por UUID; nome e
versão não fazem parte do contrato.

O navegador controla somente `from_datetime` e `to_datetime`. O componente interativo
converte `datetime-local` para instantes ISO 8601 UTC e navega por GET. O Server Component
aceita limites abertos, preserva o intervalo `[início, fim)`, rejeita datas sem fuso,
ordem inválida, parâmetros repetidos e qualquer chave fora da allowlist. Ausência de
limites significa todo o histórico, sem janela padrão criada pelo frontend.

**Semântica visual.** O estado atual representa a classificação vigente da coorte de
processos selecionada por `first_seen_at` no período. Avaliações documentais, resoluções
operacionais e revisões humanas são atividades específicas do perfil. Rodadas, registros
coletados, processos e documentos descobertos e cobertura por fonte são métricas gerais
do coletor e são rotulados dessa forma; não são apresentados como exclusivos da USIAR.
Fontes permanecem strings abertas.

O funil agrupa os doze valores absolutos retornados pela API, mas não presume que seus
estágios tenham a mesma base. Nenhuma taxa, perda, tendência, percentual ou quantidade
de rodadas em andamento é derivada. `rounds_total` pode incluir estados não detalhados
pelos três contadores terminais. Um resumo com todas as contagens zeradas e sem fontes
é estado vazio real. Erros de autenticação, autorização, perfil, validação, serviço,
rede e timeout mantêm estados de erro distintos e sanitizados.

Os componentes de apresentação são server-side. Somente o filtro temporal usa Client
Component para conversão de fuso e navegação. A suíte cobre contrato, filtros, perfil,
vazio, erros, responsividade, semântica básica e ausência de tokens no navegador. Não
foram adicionadas dependências, endpoints, tabelas de oportunidades, revisão humana,
exportação, migrations ou mudanças no coletor/FastAPI.
