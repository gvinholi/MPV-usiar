# Operação das três coletas PNCP diárias

## Estado e estratégia

O repositório não define uma plataforma de produção: há Docker Compose apenas para o
PostgreSQL local, e não há evidência de Cloud Run, VPS, systemd ou outro supervisor. O
mecanismo entregue é `python -m collector.cli.schedule daemon`, um processo Python que
deve ser executado por **um único** supervisor escolhido na implantação. Nada é
registrado ou habilitado automaticamente.

O daemon permanece fechado por padrão. `COLLECTION_SCHEDULER_ENABLED=false` impede seu
início. Os horários padrão são 06:00, 12:00 e 18:00 em `America/Sao_Paulo`; podem ser
substituídos antes da ativação.

## Configuração

| Variável | Regra/default |
| --- | --- |
| `DATABASE_URL` | Obrigatória; armazenar fora do Git. |
| `COLLECTION_SCHEDULER_ENABLED` | `false`; use `true` somente após aprovação. |
| `COLLECTION_TIMEZONE` | `America/Sao_Paulo`. |
| `COLLECTION_SCHEDULE_TIMES` | Exatamente três horários distintos `HH:MM`; default `06:00,12:00,18:00`. |
| `COLLECTION_MODALITIES` | Obrigatória, inteiros distintos separados por vírgula. Não há lista inventada pelo sistema. |
| `COLLECTION_UF` | Deve ser `SP` neste MVP. |
| `COLLECTION_PROFILE` | Deve ser `USIAR/v2`. |
| `COLLECTION_WINDOW_DAYS` | 1..31; default 2 dias, incluindo o dia local atual. |
| `COLLECTION_PAGE_SIZE` | 10..500; default 50. O PNCP rejeita valores menores que 10. |
| `COLLECTION_MAX_PAGES` | 2..10000 por modalidade; default 200. O scheduler rejeita 1. |
| `COLLECTION_TIMEOUT_SECONDS` | 1..300; default 30 por chamada HTTP. |
| `COLLECTION_RETRY_ATTEMPTS` | 1..10; default 3 para falhas transitórias. |
| `COLLECTION_RETRY_INITIAL_SECONDS` | 0..60; default 0,5. |
| `COLLECTION_RETRY_BACKOFF` | 1..10; default 2. |
| `COLLECTION_RETRY_MAX_SECONDS` | 0..300; default 8 e nunca menor que o atraso inicial. |

`show-config` valida tudo antes da execução e mostra apenas valores não secretos:

```powershell
cd D:\MPV-usiar\collector
$env:DATABASE_URL = "<conexão obtida do gerenciador de segredos>"
$env:COLLECTION_MODALITIES = "6,8" # exemplo; confirme no PNCP antes de operar
.\.venv\Scripts\python.exe -m collector.cli.schedule show-config
```

O UUID exibido deve ser `42227c23-f6ea-5a43-b640-56ed6eb6981c`. No servidor Next.js,
use o mesmo valor em `API_PROFILE_ID` e deixe `API_PROFILE_CODE` vazio.

## Instalar, validar, ativar e desativar

1. Instale as dependências do `collector`, configure `DATABASE_URL` fora do Git e aplique
   `python -m alembic upgrade head`.
2. Configure modalidades, horários e limites no ambiente do supervisor.
3. Rode `python -m collector.cli.schedule show-config`.
4. Rode `python -m collector.cli.schedule run-once` para uma validação explícita. Este
   comando funciona com o daemon desativado e devolve os mesmos códigos do runner.
5. Somente após aprovação, defina `COLLECTION_SCHEDULER_ENABLED=true` e mantenha
   `python -m collector.cli.schedule daemon` sob o supervisor escolhido.

Para desativar, interrompa o processo (Ctrl+C no foreground) e volte
`COLLECTION_SCHEDULER_ENABLED=false` antes de reiniciá-lo. Não mantenha simultaneamente
Task Scheduler, cron, systemd, Kubernetes CronJob ou outra réplica do daemon. O advisory
lock protege a execução, mas não torna múltiplos agendadores uma implantação correta.

## Janela, retomada e concorrência

A API de publicações PNCP aceita datas, não um cursor temporal. Cada ocorrência usa o
dia local como fim e, por default, também consulta o dia anterior. Essa sobreposição
reduz o risco de atraso na publicação, falha de uma rodada, reinício e virada do dia.
Novas rodadas preservam o histórico; identidades de processos são reutilizadas e a
persistência interna da mesma rodada é idempotente.

Não há checkpoint por página nem garantia de captura instantânea de toda publicação. Uma
falha reinicia da página 1 na próxima tentativa. Se todas as páginas não couberem em
`COLLECTION_MAX_PAGES`, a rodada é `PARTIAL`, nunca `SUCCESS`. O operador deve ampliar a
janela/limite de forma controlada ou executar backfill.

O lock usa `pg_try_advisory_lock` em uma conexão dedicada durante toda a operação. Ele é
compartilhado pelo daemon e por `collector.cli.collect`; concorrência retorna código 4 e
não espera. Fechamento da conexão libera o lock mesmo após falha; há também unlock
explícito no caminho normal.

## Logs, resultado e recuperação

Logs são JSON em stdout/stderr. Eventos informam espera, início/fim, janela, modalidades,
`round_id`, páginas, erros de página, registros, processos, CANDIDATE, PENDING,
DISCARDED, retries e status. Exceções são reduzidas ao tipo/código; URL do banco, headers,
tokens e corpos não são registrados.

Códigos: `0=SUCCESS`, `1=FAILED/falha inesperada`, `2=configuração/uso inválido`,
`3=PARTIAL`, `4=já existe rodada em andamento`. Somente 0 é rodada completa.

Para verificar a última rodada no PostgreSQL local:

```powershell
docker compose exec -T postgres psql -U usiar -d usiar -c "SELECT id,status,started_at,finished_at,pages_processed,pages_with_error,records_collected,candidates,pending,discarded FROM collection_rounds ORDER BY started_at DESC,id DESC LIMIT 1;"
```

Backfill controlado continua explícito e usa o runner manual:

```powershell
python -m collector.cli.collect run `
  --start-date 2026-10-12 --end-date 2026-10-13 --uf SP `
  --modality 6 --profile USIAR/v2 --page-size 50 --max-pages 200
```

Repita `--modality` somente para códigos confirmados. `PARTIAL` preserva o que foi
persistido; investigue outcomes da rodada e reexecute a janela. `FAILED` não significa
ausência de oportunidades.

## Consulta das oportunidades

Após uma rodada, consulte a API autenticada com parâmetros repetidos:

```text
GET /api/v1/opportunities?profile_id=42227c23-f6ea-5a43-b640-56ed6eb6981c&operational_state=CANDIDATE&operational_state=PENDING&page=1&page_size=25
```

O frontend usa o mesmo contrato em `/opportunities`. Campos sem origem oficial continuam
como `—`; não são preenchidos artificialmente.

## Limitação geográfica

`uf=SP` cobre publicações cuja unidade informada pelo PNCP está em São Paulo. Esse campo
não comprova o local de execução e pode omitir contratação de órgão federal sediado fora
de SP cuja execução ocorra no estado. Os snapshots atuais não possuem um campo oficial
inequívoco de local de execução para corrigir isso. Portanto, não há garantia de cobertura
integral de órgãos federais em SP e o scheduler não amplia a consulta para todo o Brasil.
Uma solução futura deve usar um campo oficial de execução ou uma segunda etapa documental
auditável antes de ampliar a abrangência.
