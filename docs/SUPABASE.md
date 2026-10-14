# Supabase: credenciais, migrations e role de runtime

Procedimento para preparar o projeto Supabase `usiar`. Nada aqui é executado
automaticamente; cada etapa remota exige autorização humana.

## 1. Duas credenciais, dois arquivos fora do repositório

| Uso | Role | Onde | Formato |
|---|---|---|---|
| Migrations Alembic, `runtime_role.sql`, bootstrap de `app_admins` e do primeiro usuário interno | `postgres` (administrativa) | máquina do operador, só durante a manutenção | `postgresql+psycopg://` |
| API e coletor Python | `usiar_runtime` (restrita) | ambiente do servidor | `postgresql+psycopg://` |
| Worker Cloudflare (Next/OpenNext e Cron) | `usiar_runtime` (restrita) | **somente** na configuração do Hyperdrive (seção 6); o Worker não recebe `DATABASE_URL` | `postgresql://` |

Regras:

- Guardar os arquivos **fora do repositório e fora do OneDrive** (por exemplo
  `C:\MPV-usiar-secrets\admin.env` e `runtime.env`), uma linha `DATABASE_URL=...`.
- Nunca imprimir o arquivo nem a variável (`Get-Content`, `echo $env:DATABASE_URL`,
  `env`, `Get-ChildItem Env:`), nem colar a URL em issues, chats ou logs.
- Senhas com caracteres especiais devem ser percent-encoded na URL. Os colchetes
  `[YOUR-PASSWORD]` do painel do Supabase não fazem parte da senha.
- Usuário no pooler: `<role>.<project_ref>` (ex.: `usiar_runtime.<project_ref>`).
- O Python só tem `psycopg` 3: a URL Python precisa de `postgresql+psycopg://`.
  O validador TS (`frontend/src/lib/server/env.ts`) só aceita `postgres:`/`postgresql:`.

### TLS e pooler

- **TLS com verificação de certificado, sempre.** O pooler apresenta
  `*.pooler.supabase.com` emitido pela *Supabase Intermediate 2021 CA* / *Supabase Root
  2021 CA*, uma CA **privada**. Baixe o certificado do projeto no painel (Database →
  Settings → SSL Configuration → Download certificate) e guarde-o fora do repositório.
  - Python/Alembic: `?sslmode=verify-full&sslrootcert=<caminho do .crt>`.
    `sslmode=require` cifra, mas **não** verifica o servidor; não usar em produção.
  - Worker: sockets do Workers não aceitam CA própria (o handshake com o pooler falha
    e o `pg` acusa `SELF_SIGNED_CERT_IN_CHAIN`). Por isso o Worker conecta **só** pelo
    Hyperdrive, que faz `verify-full` com a CA enviada (seção 6). `rejectUnauthorized:
    false` não é usado em lugar nenhum.
- **Session Pooler, porta 5432** (ou conexão direta) para Python/Alembic e como origem
  do Hyperdrive. Transaction Pooler (6543) continua não recomendado.
- **Exclusão da coleta: lease persistido (0013), não advisory lock.** O Hyperdrive
  agrupa conexões em modo transação: duas consultas seguidas podem cair em sessões
  diferentes, então um `pg_try_advisory_lock` de sessão não é confiável. Runner TS e
  coletor Python disputam a mesma linha `collection_leases.PNCP_COLLECTION` (seção 2).
  Locks de **transação** (`pg_advisory_xact_lock`, usados na revisão humana e na auth
  interna) continuam válidos, porque ficam dentro de um BEGIN..COMMIT.
- Cada coleta TS abre 2 conexões (trabalho + heartbeat), e cada coleta Python, 2 a 3.
  `usiar_runtime` tem `CONNECTION LIMIT 20`; o Hyperdrive mantém até ~20 conexões de
  origem por configuração no plano Free (~100 no Paid). Se o Supabase recusar conexões
  por limite, ajustar o `CONNECTION LIMIT` junto com o pool do Hyperdrive.

### Carregar DATABASE_URL sem exibi-la (PowerShell)

```powershell
$line = Get-Content 'C:\MPV-usiar-secrets\admin.env' | Where-Object { $_ -like 'DATABASE_URL=*' }
$env:DATABASE_URL = $line.Substring('DATABASE_URL='.Length)
Remove-Variable line
# ... comandos ...
Remove-Item Env:DATABASE_URL
```

O código Python lê somente `os.environ["DATABASE_URL"]` (`collector/infra/database/config.py`);
nenhum `.env` é carregado implicitamente. Mensagens de erro e o `repr` do engine
mascaram a senha (`tests/infra/database/test_database_url_redaction.py`).

## 2. O que as migrations fazem no Supabase

- 0001–0010: tabelas da aplicação em `public`. Não usam extensões, roles, `auth` ou
  `storage`.
- 0011: `app_admins` e RLS habilitado, sem políticas, em todas as tabelas da aplicação.
- 0012 (`0012_supabase_hardening`):
  - RLS em `public.alembic_version`;
  - `REVOKE ALL` de `anon`, `authenticated` e `service_role` em tabelas, sequências e
    funções de `public` (só quando as roles existem; no PostgreSQL local é no-op);
  - default privileges da role de migrations em `public` deixam de conceder qualquer
    coisa a essas roles; `EXECUTE` em funções novas deixa de ir para `PUBLIC`;
  - funções de trigger da 0008 com `search_path = pg_catalog, public, pg_temp` e sem
    `EXECUTE` para `PUBLIC` (o disparo do trigger não depende desse privilégio).
  - Downgrade reverte RLS de `alembic_version`, `search_path` e o `EXECUTE` das funções,
    mas **não** devolve privilégios às roles da Data API.

- 0013 (`0013_collection_leases`): tabela `collection_leases` com uma linha fixa
  `PNCP_COLLECTION` e RLS. Protocolo (todo horário pelo relógio do banco,
  `clock_timestamp()`):
  - **aquisição atômica**: um único `UPDATE ... WHERE owner_id IS NULL OR expires_at <=
    clock_timestamp()` que incrementa `fencing_token` e grava `owner_id` (UUID da
    execução) e `owner_kind` (`worker:scheduled`, `worker:manual`, `python:cli`);
    aquisições concorrentes serializam no lock da linha e só uma casa o predicado;
  - **renovação** a cada 30 s (TTL de 120 s), numa conexão própria, condicionada a
    dono + token + não expirado;
  - **expiração**: execução morta libera o lease após o TTL; quem assume fecha como
    `FAILED` as rodadas `RUNNING` órfãs;
  - **liberação** condicionada a dono + token;
  - **fencing**: toda transação de gravação começa com `SELECT ... FOR SHARE` no próprio
    (dono, token) e aborta com `COLLECTION_LEASE_LOST` se o lease foi perdido. O
    `FOR SHARE` faz uma tomada de lease esperar as transações em curso, então uma
    execução antiga nunca grava depois que outra assumiu;
  - trigger `guard_collection_lease_update` (sem `EXECUTE` para `PUBLIC`): `name`
    imutável, `fencing_token` nunca diminui e troca de dono exige token novo.

Tabelas novas devem ser criadas sempre por Alembic com a role `postgres`: objetos
criados por outra role (por exemplo pelo editor do painel) não herdam essa proteção.

## 3. Role de runtime (`collector/sql/runtime_role.sql`)

- Sem `SUPERUSER`, `BYPASSRLS`, `CREATEROLE`, `CREATEDB`, `REPLICATION`, sem herança e
  sem pertencer a outras roles; não é dona de nenhum objeto; não cria nada em `public`.
- Acesso por `GRANT` por tabela + políticas RLS `TO usiar_runtime` (uma por operação
  concedida). O script termina com uma verificação que aborta se algo exceder isso ou se
  houver acesso a tabelas de `auth`/`storage`.
- Mapa de privilégios:

| Tabelas | Operações |
|---|---|
| collection_rounds, processes, process_documents, auth_sessions | SELECT, INSERT, UPDATE |
| auth_login_attempts | SELECT, INSERT, UPDATE, DELETE |
| collection_modality_outcomes, source_identities, process_observations, screening_profiles, screening_evaluations, screening_evidence, operational_resolutions, document_catalog_queries, document_observations, artifacts, document_artifacts, artifact_archive_entries, artifact_text_sources, text_extractions, text_extraction_pages, document_screening_evaluations, document_screening_evidence, human_reviews, auth_audit_events | SELECT, INSERT |
| auth_users | SELECT; UPDATE só em password_hash, password_version, last_login_at, updated_at |
| collection_leases | SELECT; UPDATE só em owner_id, owner_kind, fencing_token, acquired_at, heartbeat_at, expires_at, released_at (sem INSERT/DELETE; o `FOR SHARE` do fencing depende desse UPDATE) |
| auth_permissions, auth_user_permissions, app_admins | SELECT |
| alembic_version | nenhum |

- Sequências: nenhuma concessão (a única é a identity de `human_reviews.sequence`, que
  não exige `USAGE`).
- Ficam com a credencial administrativa: migrations, `runtime_role.sql`,
  `npm run admin:grant` (escreve `app_admins`), bootstrap do primeiro usuário interno
  (`auth_users`/`auth_user_permissions`) e qualquer DDL.
- Tabela nova em `public` sem entrada no mapa faz o script falhar de propósito.

## 4. Procedimento de aplicação (com autorização)

1. **Rotacionar a senha** do banco no painel e confirmar a rotação. A senha anterior é
   considerada comprometida.
2. Criar `admin.env` fora do repositório/OneDrive (seção 1).
3. Revisar o SQL sem conectar:
   ```powershell
   cd collector
   $env:DATABASE_URL = 'postgresql+psycopg://offline@localhost/offline'
   alembic upgrade head --sql > $env:TEMP\usiar-migrations.sql
   Remove-Item Env:DATABASE_URL
   ```
4. Carregar a URL administrativa e conferir, somente leitura:
   ```sql
   SELECT current_database(), current_user, version();
   SELECT count(*) FROM pg_tables WHERE schemaname = 'public';   -- esperado: 0
   SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role','usiar_runtime');
   ```
5. `alembic upgrade head` (uma transação para todas as revisões).
6. Aplicar a role:
   `psql "<url admin sem +psycopg>" -v ON_ERROR_STOP=1 --single-transaction -f collector/sql/runtime_role.sql`
   e definir a senha com `\password usiar_runtime` (psql interativo, ex.:
   `docker run -it --rm postgres:17 psql "<url admin>"`). Não usar
   `ALTER ROLE ... PASSWORD '...'` no SQL Editor (fica no histórico).
7. Verificar (somente leitura):
   ```sql
   SELECT version_num FROM alembic_version;                       -- 0013_collection_leases
   SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity;   -- vazio
   SELECT r, c.relname FROM unnest(ARRAY['anon','authenticated','service_role']) r,
          pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m')
      AND has_table_privilege(r, c.oid, 'SELECT,INSERT,UPDATE,DELETE');  -- vazio
   ```
   e, pela Data API com a chave anon, `GET /rest/v1/alembic_version` deve ser negado.
8. Criar `runtime.env` com a URL de `usiar_runtime` e configurar os secrets do runtime.
9. Conceder `app_admins` com `npm run admin:grant` usando a URL **administrativa**.

### Atualizar um banco que já está na 0012 (caso do projeto `usiar`)

Com autorização, usando a credencial administrativa:

1. Revisar o SQL offline: `alembic upgrade 0012_supabase_hardening:head --sql`.
2. `alembic upgrade head` (aplica só a 0013).
3. Reaplicar `collector/sql/runtime_role.sql` (idempotente; agora mapeia
   `collection_leases`). Sem isso a `usiar_runtime` não enxerga o lease e toda coleta
   falha logo na aquisição.
4. Verificar: `SELECT name, owner_id, fencing_token FROM collection_leases;` → uma linha
   `PNCP_COLLECTION`, sem dono, token 0.

## 5. Testes

PostgreSQL local descartável (nunca Supabase: o `conftest` recusa hosts não locais sem
`USIAR_TEST_ALLOW_REMOTE_DB=1`):

```powershell
cd collector
$env:DATABASE_URL = 'postgresql+psycopg://usiar:usiar@localhost:5433/usiar'
python -m pytest                                  # credencial administrativa
$env:USIAR_TEST_RUNTIME_ROLE = '1'; python -m pytest   # código da aplicação como usiar_runtime
```

`test_postgres_supabase_hardening.py` simula o Supabase num banco próprio (dono sem
superusuário, roles `anon`/`authenticated`/`service_role` e default privileges do
Supabase) e verifica Data API, `alembic_version`, RLS, default privileges, funções da
0008, downgrade, privilégios e limites da role de runtime e o lease. Ele cria
roles no cluster local de teste. `test_postgres_operational_lock.py` cobre corrida de
aquisição, renovação, expiração, perda do lease, fencing e recuperação de rodadas órfãs.

## 6. Cloudflare Hyperdrive (Worker → Supabase)

Pré-requisitos: banco em `0013_collection_leases`, `runtime_role.sql` reaplicado, senha
da `usiar_runtime` definida e `npx wrangler login` feito pelo operador. O Hyperdrive está
nos planos Free (100 mil consultas/dia, até 10 configurações) e Paid, sem cobrança
adicional; ainda assim é um recurso de produção e só deve ser criado com autorização.

1. **CA do Supabase.** Baixar o certificado (seção 1) e conferir que é uma única CA (o
   Hyperdrive não aceita bundle com mais de uma):
   ```powershell
   openssl x509 -in C:\caminho\prod-ca-2021.crt -noout -subject -issuer -fingerprint -sha256
   ```
   Esperado: *Supabase Root 2021 CA* como subject e issuer, válida até 26/04/2031,
   SHA-256 `80:70:25:AD:50:D4:ED:21:9D:2C:9C:7D:29:9C:00:4F:82:4E:B0:0C:F7:F6:5A:FE:F6:07:D0:7B:72:E6:CA:FA`
   (conferido em 14/10/2026 contra a cadeia servida pelo Session Pooler de `sa-east-1`:
   folha `*.pooler.supabase.com` → *Supabase Intermediate 2021 CA* → esta raiz).
   Para conferir de novo, sem autenticar:
   ```bash
   openssl s_client -starttls postgres -connect <host do pooler>:5432 -servername <host do pooler> \
     -CAfile prod-ca-2021.crt -verify_hostname <host do pooler> -verify_return_error </dev/null
   ```
   Esperado: `Verify return code: 0 (ok)`. Sem `-CAfile` o resultado é `19 (self-signed
   certificate in certificate chain)`. Em URLs libpq/psycopg, um `sslrootcert` cujo
   caminho tenha espaço precisa de `%20` (o `+` não é decodificado como espaço); mais
   simples é passar `sslrootcert` como parâmetro separado ou usar um caminho sem espaço.
2. **Enviar a CA ao Cloudflare** (Wrangler ≥ 4.9; o arquivo não vai para o repositório):
   ```powershell
   npx wrangler cert upload certificate-authority --ca-cert C:\caminho\prod-ca-2021.crt --name usiar-supabase-ca
   ```
   Anotar o ID retornado.
3. **Criar a configuração** com TLS `verify-full` e **cache desligado** (o cache padrão,
   de 60 s, mostraria dados velhos no dashboard, e as gravações não o invalidam). A URL é
   a da `usiar_runtime` no Session Pooler (porta 5432). Para não deixar a senha no
   histórico do terminal, ler a URL do `runtime.env` e passar host, usuário e senha em
   flags separadas (sem problemas de percent-encoding). `--origin-connection-limit 10`
   deixa folga no `CONNECTION LIMIT 20` da `usiar_runtime` para o coletor Python e a
   manutenção:
   ```powershell
   $line = Get-Content 'C:\caminho\runtime.env' | Where-Object { $_ -like 'DATABASE_URL_TS=*' }
   $uri = [System.Uri]($line.Substring('DATABASE_URL_TS='.Length).Trim()); Remove-Variable line
   $u, $p = $uri.UserInfo.Split(':', 2) | ForEach-Object { [System.Uri]::UnescapeDataString($_) }
   npx wrangler hyperdrive create usiar-db --origin-host $uri.Host --origin-port $uri.Port `
     --database $uri.AbsolutePath.TrimStart('/') --origin-user $u --origin-password $p `
     --ca-certificate-id <ID-da-CA> --sslmode verify-full --caching-disabled --origin-connection-limit 10
   Remove-Variable uri, u, p
   ```
   Flags conferidas no Wrangler 4.150.0 (`wrangler hyperdrive create --help`).
   Na criação o Hyperdrive conecta com essas credenciais: falha de TLS ou de senha
   aparece aqui. Anotar o ID da configuração (não é segredo). Para uma configuração
   existente: `npx wrangler hyperdrive update <ID> --caching-disabled`.
4. **Ligar ao Worker**: o `id` do binding `HYPERDRIVE` em `frontend/wrangler.jsonc` é o
   da configuração. Feito em 14/10/2026: `usiar-db` (`76711eb9b0964825be677011589cee32`),
   CA `usiar-supabase-ca`. Conferir com `npx wrangler hyperdrive get <ID>`: `sslmode`
   `verify-full`, `caching.disabled: true` e `origin_connection_limit: 10`.
   Conectividade real conferida com um Worker de sonda descartável via
   `wrangler dev --remote` (preview temporário, sem deploy), só leitura.
5. **Secrets do Worker**: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `APP_ORIGIN` e
   `API_PROFILE_ID`. **Não** criar `DATABASE_URL` no Worker (se existir de uma tentativa
   anterior: `npx wrangler secret delete DATABASE_URL`). Em produção, `db.ts` exige o
   binding `HYPERDRIVE` e recusa conexão sem ele.
6. **Deploy** (só com autorização), em Linux ou container: `npm run deploy:worker`.
7. **Validação pós-deploy**: `npx wrangler tail`, disparar a Cron pelo painel e conferir
   os eventos `collection_lease_acquired` → `collection_finished` →
   `collection_lease_released`; `/login` responde 200 e as rotas protegidas redirecionam.
   No banco, somente leitura: `SELECT owner_id, fencing_token, released_at FROM
   collection_leases;`.

Desenvolvimento local: `wrangler dev` e `next dev` usam o `localConnectionString` do
`wrangler.jsonc` (Postgres descartável local) ou a variável
`CLOUDFLARE_HYPERDRIVE_LOCAL_CONNECTION_STRING_HYPERDRIVE`, que tem precedência. Nesse
modo o Worker conecta direto ao banco, sem pool nem cache do Hyperdrive: o comportamento
real do Hyperdrive só é comprovado no Cloudflare (`wrangler dev --remote` grava no banco
de produção).
