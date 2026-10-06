# Commit 16 — Read model e consultas de aplicação

Implementação validada em 06/10/2026. **606 testes passaram, sem skips. Nenhum commit criado.**

1. **Resumo.** Camada de leitura para o dashboard futuro, cobrindo summary, funil, lista/detalhe de oportunidades, documentos, evidências, timeline, fila humana, rodadas e cobertura de fontes. Sem HTTP, frontend, escrita ou mudança de schema.

2. **Arquivos.** Novos contratos em `collector/src/collector/application/read_model/`: `__init__.py`, `models.py`, `filters.py`, `pagination.py`, `errors.py`, `ports.py`, `service.py`. Infra: `collector/src/collector/infra/database/read_model_store.py`, `read_model_sql.py`, `read_model_timeline.py`. Testes: `collector/tests/application/read_model/test_contracts.py`, `collector/tests/infra/database/test_postgres_read_model.py`, `test_read_model_urls.py`. Atualizados README, ARCHITECTURE e export do adaptador em `infra/database/__init__.py`. Este relatório registra a entrega. Nenhum serviço write-side foi alterado.

3. **Arquitetura do read model.** `Write Side → PostgreSQL → Read Model → Future HTTP API → Future Dashboard`. `DashboardQueries` é a fachada tipada da aplicação, `ReadModelQueries` é a porta, `SqlAlchemyReadModelStore` é o adaptador. Mesmo banco, sem CQRS distribuído, event sourcing, banco separado ou materialized view.

4. **DTOs.** Dataclasses imutáveis: OpportunityListItem/Detail, LatestObservation, SourceIdentityItem, InitialScreeningItem/InitialEvidenceItem, DocumentScreeningItem/DocumentCoverage, OperationalResolutionItem, HumanReviewItem, OpportunityCounters, OpportunityDocumentItem/DocumentMemberItem/ExtractionMetadata, DocumentEvidenceItem, OpportunityTimelineItem, CollectionRoundListItem/Detail/ModalityOutcomeItem, SourceCoverageSummary, DashboardReviewQueueItem, DashboardSummary/CurrentSnapshot/PeriodActivity/PilotFunnel e Page. Decimal e datetime aware permanecem nativos; não há serialização HTTP.

5. **DashboardSummary.** Composto por profile_id, period, current_snapshot, period_activity, funnel e source_coverage. Contagens atuais e históricas ficam em campos distintos, evitando misturar estados vigentes com eventos.

6. **CurrentSnapshot.** processes_total, current_candidate/pending/discarded, needs_review, selected, human_pending/discarded, stale_reviews, documents_total/with_artifact/with_text. Quando há período, aplica-se ao cohort de processos cuja primeira persistência ocorreu nele; mostra o estado atual desse cohort. Não é um snapshot retroativo no fim do intervalo.

7. **PeriodActivity.** records_collected, processes_first_seen, documents_discovered, document_screenings_total, operational_resolutions_total, human_reviews_total e rounds_total/success/partial/failed. Avaliações/resoluções/reviews respeitam o perfil. Coleta e documentos são globais, pois não pertencem a um perfil.

8. **PilotFunnel.** records_collected do período, unique_processes do cohort, latest initial candidate/pending/discarded, processos document_evaluated, operational candidate/pending/discarded e decisões humanas vigentes. São unidades/estágios diferentes; números não precisam formar uma sequência monotônica. Não interpretar como taxas de conversão sem análise adicional.

9. **Semântica temporal.** `TimeRange` valida datetimes timezone-aware e intervalo `[from_datetime, to_datetime)`. Cohort/processes_first_seen: processes.created_at. Rodadas/records_collected: started_at. Documentos descobertos: first_seen_at. Document screening: evaluated_at. Resoluções: resolved_at. Reviews: decided_at. Snapshot de um cohort usa decisões atuais sem cortar o histórico necessário para encontrar latest. Documento posterior ao intervalo pode aparecer no estado atual do cohort; atividade documental continua filtrada pela descoberta. Sem limites explícitos, todo o histórico. Tabela detalhada na seção 36 de ARCHITECTURE.

10. **OpportunityListItem.** Id, fonte/official id, description_preview de até 300 caracteres, organização/CNPJ, localidade/UF, modalidade, Decimal, publicação/deadline, URL pública disponível, operational id/state/reason/resolved_at, human status/decision/reason/reviewed_at, documents_count, has_text, has_document_screening e latest_capture_at. Não há título de processo separado no schema; não foi inventado. Preview não altera a descrição persistida nem transporta texto de PDF.

11. **Filtros.** Operational state, human status/decision, source, UF, municipality/locality, modality, publicação/deadline/captura, has_documents, has_text, has_document_screening, busca literal em description via ILIKE e fila humana. Busca parametrizada, escapa %, _ e !; sem FTS. Município/modalidade usam igualdade exata. Source considera identidades persistidas do processo. Datas usam o timestamp indicado pelo filtro; captura desconhecida não é substituída silenciosamente.

12. **Paginação.** Offset server-side. Page >= 1, tamanho padrão 25, máximo 100; rejeita bool, frações e limites inválidos. Page contém tuple de items, page, page_size, total_items, total_pages. COUNT e página no mesmo snapshot. Página além do fim retorna vazio e mantém total. Disponível para oportunidades, filas, documentos, evidências documentais, timeline e rodadas.

13. **Ordenação.** Allowlist fechada: publication_at, proposal_deadline_at, estimated_value, latest_capture_at, operational_resolved_at, reviewed_at; ASC/DESC. Default captura mais recente. NULLS LAST e process_id ASC como desempate de paginação. Nenhum nome SQL arbitrário vindo do caller. Todos os 12 pares sort/direction foram exercitados no PostgreSQL.

14. **OpportunityDetail.** Identidades completas, descrição integral do processo, dados correntes da listagem, observação vigente, latest initial/document screening, resolução vigente, review humana vigente, última review histórica separada e counters de documentos/artifacts/sources/páginas. Sem PDFs ou texto integral de páginas extraídas.

15. **Initial screening no detalhe.** Evaluation id, state, reason, engine version, evaluated_at e evidências category/configured_term/matched_text/field. Latest por evaluated_at/created_at/engine_version/id descendentes. Não inventa página para evidência da description.

16. **Document screening no detalhe.** Evaluation id/state/reason/engine version/fingerprint/evaluated_at e cobertura de documentos, sources, páginas, páginas com texto, scanned/failed/unsupported e complete. Latest por evaluated_at/created_at/fingerprint/id descendentes. Evidências documentais têm consulta paginada própria para não inflar o detalhe.

17. **Operational resolution no detalhe.** Id, state, reason, rule, fingerprint, resolved_at e ids das avaliações usadas. Latest com a semântica do Commit 14: resolved_at DESC, created_at DESC, resolution_fingerprint DESC. Latest screenings podem ser posteriores à resolução; os ids tornam essa diferença explícita e auditável.

18. **Human review no detalhe.** Current human review apenas sobre a resolução vigente, com decisão/motivo/reviewer/display name/comment/decided_at e flag stale registrada na decisão. Última review histórica fica em campo separado. Status humano está no item de oportunidade. STALE não mostra decisão antiga como atual; SELECTED histórico substituído por DISCARDED também não aparece no filtro SELECTED.

19. **Divergências.** state_diverged e reason_diverged preservados; divergence_kind derivado como NONE, STATE_ONLY, REASON_ONLY ou STATE_AND_REASON. Sem comparação documental, permanece null.

20. **Documentos.** Metadados públicos, primeira/última descoberta, última tentativa de aquisição, artifact SHA/type, acquisition_status, extrações latest por source, páginas e likely_scanned. Acquisition status projeta complete como COMPLETE/INCOMPLETE; null sem tentativa. A última tentativa é usada inclusive quando falha, sem fallback oculto para artifact anterior; histórico continua na timeline. Extrações com estados diferentes geram text_status MIXED, preservando metadados por source. MIME/versão PNCP não foram inventados.

21. **ZIP/members.** Entradas persistidas com path, SHA/type quando conhecidos, safe, extracted, pages e text_status. Safe deriva dos flags de path/encriptação/symlink, não certifica limites globais do ZIP. Sem source, SHA/type são null; sem extração, páginas/status são null; UNSUPPORTED persistido com zero páginas permanece zero. Query não abre storage, inspeciona ou extrai ZIP/PDF.

22. **Evidências.** Initial evidence embutida no detalhe, sem página. DocumentEvidenceItem paginado da latest avaliação documental do perfil: category, configured_term, matched_text, context_snippet, page_number, source_path, source_sha256, document_id e negated. Não seleciona texto integral da página.

23. **Timeline.** UNION ALL dos nove eventos solicitados, sem tabela nova. Ordem occurred_at ASC/event_type/reference_id. Usa timestamps persistidos: primeira persistência, captura, avaliação, descoberta, aquisição, fim da extração, resolução e decisão. Se captured_at é null, usa created_at da observação e identifica o fallback nos metadados. Eventos incompletos/falhos mantêm essa condição no summary. Histórico humano/operacional respeita o perfil; documentos/coleta são compartilhados.

24. **Collection rounds.** Lista/detalhe com fonte, status, timestamps, páginas previstas/processadas/com erro, records_collected, unique_processes, modalidades/outcomes, errors e métricas históricas. Outcomes incluem complete, failed_page, contagens, indicador COLLECTION_FAILURE e quantidade de erros de mapping. Mensagens brutas de transporte não são devolvidas, pois podem conter URLs ou headers sensíveis. Métricas antigas das rodadas não são reinterpretadas como seleção humana.

25. **Source coverage.** Somente fontes presentes nas rodadas selecionadas: rounds/successful/partial/failed, records_collected e processos distintos observados nessas rodadas. Não soma unique_processes de rodadas como se fossem processos globalmente distintos. Não cria cobertura RHS fictícia.

26. **Review queue.** DashboardReviewQueueItem combina OpportunityListItem com o ReviewQueueItem anterior, sem alterá-lo. Compilação finita da política pura `in_queue` do Commit 15 para SQL; paridade testada para todas as filas. NEEDS_REVIEW exclui descarte automático por padrão, com inclusão explícita. SELECTED/HUMAN_PENDING/HUMAN_DISCARDED usam decisão vigente. STALE_REVIEW preservada. Filtros, count, order e paginação em SQL.

27. **Source identity lookup.** `get_opportunity_by_source_identity(source, official_id, scope)` resolve process_id por identidade persistida e retorna o mesmo detalhe no mesmo snapshot. Parâmetros SQL vinculados; sem inventar URL ou identidade.

28. **Not found.** OpportunityNotFoundError para process_id/identidade ausente; CollectionRoundNotFoundError para rodada ausente; ProfileNotFoundError para perfil ausente; AmbiguousProfileError quando code identifica múltiplas versões. Coleções vazias de documentos/evidências são legítimas, distintas de oportunidade inexistente.

29. **Read consistency.** Todas as respostas usam REPEATABLE READ/READ ONLY. COUNT/página, summary e detalhe composto não misturam snapshots. Teste concorrente insere um processo por outra sessão durante a leitura e confirma que a transação leitora continua vendo o snapshot anterior. Teste de DML acidental confirma rejeição pelo PostgreSQL. Comparação integral das linhas antes/depois de todas as consultas confirma ausência de mutação.

30. **Anti-N+1.** CTEs/window functions para latest observation/resolution/review/acquisition/extraction, EXISTS e agregações por processo. Lista retorna só colunas de apresentação e preview. Documentos buscam sources/extrações/members em lote por página. Detalhe faz consultas por seção, nunca por página/evidência. Não carrega todas as oportunidades em Python para filtrar/paginar.

31. **Queries medidas.** Listagem com 7 processos: 4 statements; com 30 processos: 4 statements. Composição: SET TRANSACTION READ ONLY, resolução do perfil, COUNT e SELECT paginado. São 3 SELECTs, quantidade constante. A medição usa listener `before_cursor_execute` no PostgreSQL real, com assertion no teste; não é estimativa.

32. **Testes unitários.** 55 novos testes sem banco: 42 de contratos/aplicação e 13 de URLs de referência. Cobrem filtros, tipos/limites, enum sort/SQL injection por nome, preview Unicode, paginação, imutabilidade, datetime aware, intervalo, perfil, source lookup, not found e fronteira arquitetural. Decimal/nullability também exercitados com valores reais do banco. Total sem PostgreSQL na suíte: 485.

33. **Testes PostgreSQL.** 48 novos testes do read model. Fixtures incluem candidate/pending/discarded, selected/human pending/human discarded/stale, múltiplas reviews/resolutions/observações, documentos/sem documentos, PDF/ZIP, extração/evidências, rodadas SUCCESS/PARTIAL/FAILED, perfis distintos. Total PostgreSQL da suíte: 121. Rodada focada dos novos testes: **103 passed em 16,26 s**. Suíte completa: **606 passed em 40,02 s**, sem skips, usando PostgreSQL real 16.4 no banco local isolado já preparado no Commit 15. Nenhum dado externo novo foi coletado.

34. **Teste temporal.** `[NOW, NOW+1s)` conta 7 resoluções iniciais e exclui a oitava em NOW+1min; conta 4 reviews do período. Mover a primeira persistência de um processo selecionado para antes do período reduz cohort de 7 para 6 e selected de 1 para 0, preservando as 4 reviews como atividade. Intervalo sem dados zera cohort/atividade/funil/cobertura. Limite superior exclusivo exclui eventos exatamente em NOW. Filtros próprios de captura/publicação/deadline também testados.

35. **SUCCESS zero × FAILED.** Fixtures persistem SUCCESS, PARTIAL e FAILED com zero registros. Lista/detalhe preservam os três status e errors 0/1; cobertura separa contagens. Erro bruto com token sintético não aparece na resposta. Zero registros não é convertido em sucesso nem falha escondida como ausência de oportunidades.

36. **Profile isolation.** Dois perfis com decisões distintas sobre o mesmo processo: perfil original mantém SELECTED; segundo retorna DISCARDED. Summary, evidências, detalhes e history respeitam scope. Processos sem screening no segundo perfil não herdam decisões do primeiro. Code com múltiplas versões é rejeitado até o caller escolher profile_id.

37. **Migration/schema.** Nenhuma migration nova ou edição nas existentes; head permanece 0008_human_reviews. Nenhuma coluna, índice, tabela timeline, view ou materialized view adicionada. A suíte completa inclui o teste já existente de migration em banco vazio.

38. **Dependências.** `pyproject.toml` intacto, nenhuma dependência nova. Reutilizados Python/.venv e PostgreSQL portátil locais, sem serviço Windows instalado. Ferramentas/dados temporários permanecem ignorados pelo Git.

39. **Limitações.** Offset/ILIKE sem FTS ou índice novo, adequados ao piloto sem garantia de latência em grandes volumes. Lookup por code exige versão única. Snapshot temporal é cohort atual, não reconstrução histórica as-of. Eventos/documents/activity possuem timestamps diferentes por definição. Metadados de membros/extrações de um documento não têm paginação interna adicional. Safe do ZIP é apenas projeção dos flags persistidos. Filtro conservador de URLs omite query strings legítimas junto das potencialmente sensíveis; não faz DNS ou rede. Erros de coleta são resumidos em indicadores/contagens, sem mensagem livre.

40. **Decisões/dificuldades.** Perfil explícito evita misturar versões ou duplicar oportunidade por perfil. Cohort vs activity evita funil enganoso. Últimas tentativas/extrações são determinísticas, com histórico mantido na timeline. Nenhuma escrita foi adicionada para facilitar projeção. Uma fixture de perfil inicialmente reutilizava o UUID fixo de USIAR; foi corrigida com novo id. O caso ZIP confirmou que UNSUPPORTED persistido tem zero páginas, diferente de ausência de extração; o contrato preserva essa diferença. Todas as correções foram validadas na suíte final.

41. **Fora do escopo.** Não implementados FastAPI/Flask/Pydantic HTTP, endpoints, Next.js/React/dashboard visual, auth/RBAC, GCP/scheduler/Cloud Run, RHS novo, Google Sheets, OpenAI/IA/OCR/embeddings, FTS, Redis/Elasticsearch/materialized views, export CSV/XLSX, SELECTED automático ou CONFIRMED.

42. **Mensagem sugerida de commit.** `feat(collector): add read-only dashboard query models and paginated projections`

Os 37 critérios de fechamento foram verificados: camada separada, somente leitura, sem migration, contratos completos, semântica temporal explícita, isolamento de perfil, paginação e sort seguros, latest/current/stale corretos, documentos/evidências/timeline/rodadas, fontes/fila/lookup, Decimal/aware/nulls, N+1 constante, snapshot consistente, sem credenciais de infraestrutura/HTTP/frontend/IA e suíte verde. Aguardando aprovação, sem commit automático.
