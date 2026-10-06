# Commit 15 — revisão humana auditável

Validação em 06/10/2026. Implementado e testado; **nenhum commit criado**.

1. **Resumo.** Quarta camada histórica de revisão humana, com decisões explícitas, auditoria, idempotência, detecção de resolução obsoleta, filas e métricas independentes.

2. **Arquivos.** Novos: `collector/src/collector/application/human_review/{__init__,models,service}.py`, `collector/src/collector/infra/database/human_review_store.py`, `collector/alembic/versions/0008_human_reviews.py`, `collector/tests/application/human_review/test_models.py`, `collector/tests/infra/database/test_postgres_human_review.py` e este relatório. Atualizados: `README.md`, `docs/ARCHITECTURE.md`, export do adaptador em `infra/database/__init__.py`, expectativa de head no teste de migration limpa e `.gitignore` para ferramentas locais. Nenhuma implementação das três camadas anteriores foi alterada.

3. **Quatro camadas.** Initial Screening e Document Screening → Operational Resolution → Human Review. As triagens e a resolução permanecem históricas. Nenhum campo de estado atual foi adicionado a `processes`.

4. **HumanReviewDecision.** Enum próprio: `SELECTED`, `DISCARDED`, `PENDING`. `CANDIDATE` e `CONFIRMED` são rejeitados. SELECTED significa seguir para análise/atuação, sem confirmar habilitação, documentação completa, participação, proposta, vitória ou contrato.

5. **Reason codes.** SELECTED: `RELEVANT_SCOPE_CONFIRMED`, `COMMERCIAL_INTEREST`, `TECHNICAL_FIT`, `REVIEWED_AND_APPROVED`. DISCARDED: `OUT_OF_SCOPE`, `ISOLATED_INSTALLATION`, `EQUIPMENT_PURCHASE_ONLY`, `PARTS_SUPPLY_ONLY`, `DEADLINE_NOT_VIABLE`, `TECHNICAL_REQUIREMENT_NOT_VIABLE`, `COMMERCIAL_DECISION`, `DUPLICATE_OPPORTUNITY`, `OTHER`. PENDING: `NEEDS_TECHNICAL_REVIEW`, `NEEDS_COMMERCIAL_REVIEW`, `NEEDS_DOCUMENT_REVIEW`, `INSUFFICIENT_INFORMATION`, `OTHER`. Prazo e exigência técnica são razões exclusivamente humanas, nunca novos critérios automáticos.

6. **Validação decision × reason.** Matriz central `ALLOWED_REASONS` e validator puro na aplicação. Migration congela a mesma matriz em CHECK; testes exercitam cada par permitido no PostgreSQL e rejeitam combinações incompatíveis.

7. **Reviewer.** Id obrigatório não branco, até 200 caracteres, display name opcional até 200. Identidade auditável declarada pelo caller, **não autenticada**. Sem usuários/accounts, auth ou RBAC.

8. **Comentário.** Opcional até 4000 caracteres. OTHER exige comentário não branco. Validação na aplicação e no banco.

9. **Modelo relacional.** `human_reviews`: UUID, sequência identity única, FK da resolução revisada, reviewer, decisão, reason, comentário, chave global, allow_stale, was_stale_at_decision, FK latest_resolution_id_at_decision, fingerprint/estado do snapshot, decided_at e created_at. Process/profile são normalizados pela resolução e expostos nos DTOs, evitando colunas redundantes que poderiam divergir. Trigger valida snapshot e igualdade de processo/perfil entre as duas resoluções.

10. **Migration.** `0008_human_reviews`, após `0007_operational`, cria tabela, constraints, índice de latest e triggers. Sem `create_all`.

11. **Append-only.** Nenhum método UPDATE/DELETE. Trigger rejeita ambos, inclusive SQL direto. Mudança de decisão cria nova linha. A infraestrutura de testes usa TRUNCATE; administradores continuam capazes de alterar schema/triggers.

12. **Idempotência.** Chave obrigatória do caller, global, até 200 caracteres, UNIQUE. Mesmo payload retorna a mesma review; payload diferente gera `IdempotencyConflictError`. Comparação inclui resolution, reviewer/display name, decision, reason, comment e allow_stale. Retry de operação já gravada continua válido após surgir nova resolução.

13. **Stale detection.** Dentro da transação de gravação, latest é consultada por processo/perfil e comparada com a resolução solicitada. `StaleOperationalResolutionError` informa ambos os ids.

14. **Stale override.** `allow_stale=False` por padrão. Override explícito preserva a resolução antiga e audita `was_stale_at_decision=True` e latest observada. Não transfere a decisão para a nova resolução.

15. **Race/concurrency.** Advisory lock transacional por chave serializa retries; UNIQUE/ON CONFLICT protegem a inserção. Requests simultâneos iguais retornam uma review; diferentes geram um conflito. READ COMMITTED permite resolução nova entre SELECT e INSERT: documentado e reproduzido por teste. Auditoria representa a resolução observada no check; consulta posterior mostra STALE. Sem lock distribuído ou SERIALIZABLE global.

16. **Current review status.** Derivado da latest review da resolução vigente por processo/perfil, sem atualizar processos. Uma review posterior de resolução antiga não esconde a review vigente.

17. **Status.** UNREVIEWED: nenhuma review vigente nem histórica no escopo. REVIEWED: há review vigente. STALE: há histórico humano, mas não há review vigente. Sem resolução, consulta retorna `None`. PENDING humano continua REVIEWED, pois houve uma decisão inconclusiva registrada.

18. **Latest review.** `decided_at DESC, created_at DESC, sequence DESC`; desempate por sequência do banco, nunca UUID. Testados empates de horário e inserção posterior com horário de decisão anterior.

19. **Filas humanas.** NEEDS_REVIEW, SELECTED, HUMAN_DISCARDED, HUMAN_PENDING e STALE_REVIEW. Descarte automático sem review não entra na fila principal; inclusão explícita disponível. STALE_REVIEW é consultável inclusive para descarte automático. Filtros por perfil. Ordem determinística por resolved_at/created_at/fingerprint e process/profile para desempate entre escopos.

20. **ReviewQueueItem.** Process/profile, resolution id/state/reason/resolved_at, human status, decision, reason, reviewer e reviewed_at. Sem texto documental. No STALE, campos da decisão atual são nulos; o histórico permanece separado e consultável.

21. **Métricas.** Summary próprio: current_resolutions, needs_review, reviewed, stale_reviews, selected, human_discarded, human_pending, reviews_total, stale_overrides_total. Nenhuma alteração em CollectionRound.metrics. Snapshot REPEATABLE READ mantém coerência dos SELECTs do summary.

22. **Auditabilidade.** Review → resolution → initial/document evaluation → evidence/page pelas FKs existentes. Snapshots validados; evidências não duplicadas. Comparação integral das linhas de processos, triagens e resoluções confirma ausência de alteração pela revisão.

23. **Testes unitários.** 36 novos testes sem banco: matriz de razões, entradas inválidas, limite do comentário, reviewer/chave, stale policy, status, porta atômica com Clock e fronteira arquitetural. Total da suíte sem PostgreSQL: 430.

24. **Testes PostgreSQL.** 26 novos testes de revisão humana; 73 testes PostgreSQL no total. Cobertura de decisões, constraints/FKs/snapshots, append-only, idempotência e concorrência, stale/override, filas, summary, isolamento por perfil, timestamps e demos. **Suíte completa: 503 passed em 25,10 s, sem skips.** Comando executado a partir de `collector`: `..\.venv\Scripts\python.exe -m pytest -q`, com DATABASE_URL apontando para banco isolado.

25. **Migration limpa.** Teste real criou banco vazio, aplicou 0001 → 0008 e confirmou `human_reviews` e `alembic_version=0008_human_reviews`. Rodada focada: 27 passed (26 de revisão + migration limpa). PostgreSQL portátil 16.4 em 127.0.0.1:55433; banco `usiar_commit15`, separado do banco padrão 5433. Python 3.13 em `.venv`. Ferramentas e dados locais em `.local-tools`, ignorados pelo Git.

26. **Demonstração 3341.** Fixture persistida controlada `COMMIT15-CONTROLLED-3341`, com PDF sintético, não dados vivos do PNCP nem resolução supostamente preservada do Commit 14. Fluxo real de catálogo/aquisição/extração/triagens/resolução. Operational `PENDING / DOCUMENT_DID_NOT_CONFIRM_INITIAL_RELEVANCE`; review `PENDING / NEEDS_DOCUMENT_REVIEW`, reviewer `gabriel`, comentário `Descrição do PNCP não foi confirmada pelos documentos analisados.` Review `230315f3-72e9-4dad-b20b-9ab148958b98`; resolution `d72a95b8-cb24-4bbe-9645-abb48b07554d`; status REVIEWED; stale=False.

27. **Demonstração SELECTED.** Resolution `20e1f5cf-89c6-4db6-b13d-4cb8fc664443` permaneceu CANDIDATE. Review `e6a20294-ac94-4b9e-aee2-4417924d1183`, gabriel, SELECTED/RELEVANT_SCOPE_CONFIRMED. Comparação integral comprovou processos, triagens e resolução intactos. Depois PENDING e DISCARDED geraram novas linhas, preservando SELECTED no histórico.

28. **Demonstração stale.** A=`be3bece0-7cf4-47df-a662-f313ec445877` recebeu SELECTED; B=`b483ec0b-cc49-4b87-8e9b-da12940d95d3` tornou o status STALE. Novo pedido sobre A sem override foi rejeitado com ambos os ids; override `846b0d42-c0a2-4676-8c8f-b6fd142c9752` registrou stale=True. Review de B retornou REVIEWED. Override posterior sobre A não substituiu a review de B.

29. **Demonstração idempotência.** Chave `commit15-demo-001` enviada duas vezes retornou `e6a20294-ac94-4b9e-aee2-4417924d1183`. Mesmo key com DISCARDED/COMMERCIAL_DECISION foi rejeitado. As quatro demonstrações foram executadas novamente com saída explícita via três testes dirigidos (`pytest -q -s ...`): 3 passed em 1,39 s. São demonstrações controladas pela suíte, sem CLI de produção novo. Cada fixture limpa o banco de testes; IDs dos cenários SELECTED/stale não permanecem após a fixture final 3341.

30. **Contagens verificadas após a fixture final 3341.** processes=1, source_identities=1, process_observations=1, collection_rounds=1, collection_modality_outcomes=1, screening_profiles=1, screening_evaluations=1, screening_evidence=5, process_documents=1, document_catalog_queries=1, document_observations=1, artifacts=1, document_artifacts=1, artifact_archive_entries=0, artifact_text_sources=1, text_extractions=1, text_extraction_pages=1, document_screening_evaluations=1, document_screening_evidence=0, operational_resolutions=1, human_reviews=1. Zero evidências documentais é coerente com o PDF não confirmar relevância. Essas são contagens do banco isolado, não do banco de produção/piloto anterior.

31. **Dependências.** Nenhuma nova dependência declarada; `pyproject.toml` intacto. uv/Python/PostgreSQL foram baixados localmente apenas para executar a validação neste Windows sem runtime disponível. O servidor temporário foi encerrado ao final; dados da fixture final preservados em `.local-tools/pgdata`.

32. **Limitações.** Reviewer declarado, sem autenticação/autorização. Race READ COMMITTED explicitada no item 15. Filas materializam os itens atuais e aplicam filtros puros; paginação SQL fica para evolução de volume. Auditoria protegida contra UPDATE/DELETE comuns, não contra administradores do banco. Sem confirmação de elegibilidade comercial/técnica implícita em SELECTED.

33. **Decisões/dificuldades.** Mantido PENDING humano em enum próprio. Process/profile normalizados pela resolução; sequência resolve empates sem UUID. Clock é interno/injetável, sem horário de cliente. O ambiente exigiu preparação de Python/PostgreSQL portáteis; nenhum serviço Windows foi instalado. A inicialização do PostgreSQL exigiu sair do sandbox. As camadas anteriores não foram modificadas para eliminar phantom de resolução; a limitação foi testada e documentada.

34. **Fora do escopo.** Não implementados CONFIRMED, autenticação, RBAC, accounts, dashboard, Next.js, API HTTP, threads/anexos humanos, edição/exclusão de review, IA/OpenAI/LLM/OCR, e-mail, Telegram, GCP, RHS, proposta ou participação automática.

35. **Mensagem sugerida de commit.** `feat(collector): add auditable human review workflow and opportunity selection`

Os 36 critérios de fechamento do pedido estão atendidos, com a limitação de concorrência explicitamente prevista e registrada acima. Revisões humanas não atualizam as três camadas anteriores; SELECTED é exclusivamente humano; CONFIRMED é rejeitado; atualidade é derivada; filas e métricas são independentes; migration limpa e suíte completa passaram. Aguardando revisão/aprovação, sem commit automático.
