-- MPV-usiar: role de runtime com privilégios mínimos (API, coletor e backend TS).
--
-- Executar com a credencial ADMINISTRATIVA, depois de `alembic upgrade head`,
-- numa única transação e parando no primeiro erro:
--
--   psql "<url administrativa>" -v ON_ERROR_STOP=1 --single-transaction -f collector/sql/runtime_role.sql
--
-- Idempotente: reexecutar converge privilégios e políticas para este arquivo.
-- Não define senha. Defina-a interativamente, fora de logs e histórico:
--
--   psql "<url administrativa>" -c "\password usiar_runtime"
--
-- A role não é dona de nenhum objeto, não tem BYPASSRLS e não pode criar ou
-- alterar schema. Ela acessa as tabelas por GRANT + políticas RLS explícitas
-- (0011 habilitou RLS sem políticas). Não toca nos schemas `auth` e `storage`.
-- Toda tabela nova em `public` precisa entrar no mapa abaixo; caso contrário o
-- script falha de propósito.
--
-- Operações administrativas continuam com a credencial de migrations:
-- bootstrap do primeiro usuário interno (auth_users/auth_user_permissions),
-- manutenção de app_admins e alterações de schema.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'usiar_runtime') THEN
        CREATE ROLE usiar_runtime LOGIN NOINHERIT;
    END IF;
END $$;

-- Só o que a role postgres do Supabase (sem SUPERUSER) pode alterar. Os demais
-- atributos (SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS) nascem
-- desligados e são verificados no fim, porque alterá-los exige esses poderes.
ALTER ROLE usiar_runtime LOGIN NOINHERIT CONNECTION LIMIT 20;
ALTER ROLE usiar_runtime SET search_path = public;

-- Ponto de partida limpo dentro de public.
REVOKE ALL ON SCHEMA public FROM usiar_runtime;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM usiar_runtime;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM usiar_runtime;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM usiar_runtime;
GRANT USAGE ON SCHEMA public TO usiar_runtime;

DO $$
DECLARE
    item record;
    policy record;
    command text;
    missing text;
BEGIN
    CREATE TEMP TABLE runtime_grants (table_name text PRIMARY KEY, privileges text[] NOT NULL) ON COMMIT DROP;
    INSERT INTO runtime_grants VALUES
        -- Coleta PNCP (coletor Python e runner TS).
        ('collection_rounds',              ARRAY['SELECT','INSERT','UPDATE']),
        ('collection_modality_outcomes',   ARRAY['SELECT','INSERT']),
        -- Lease da coleta: linhas fixas da migration 0013; UPDATE por coluna (abaixo).
        ('collection_leases',              ARRAY['SELECT']),
        ('processes',                      ARRAY['SELECT','INSERT','UPDATE']),
        ('source_identities',              ARRAY['SELECT','INSERT']),
        ('process_observations',           ARRAY['SELECT','INSERT']),
        -- Triagem e resolução operacional (append-only).
        ('screening_profiles',             ARRAY['SELECT','INSERT']),
        ('screening_evaluations',          ARRAY['SELECT','INSERT']),
        ('screening_evidence',             ARRAY['SELECT','INSERT']),
        ('operational_resolutions',        ARRAY['SELECT','INSERT']),
        -- Documentos, artefatos e extração.
        ('process_documents',              ARRAY['SELECT','INSERT','UPDATE']),
        ('document_catalog_queries',       ARRAY['SELECT','INSERT']),
        ('document_observations',          ARRAY['SELECT','INSERT']),
        ('artifacts',                      ARRAY['SELECT','INSERT']),
        ('document_artifacts',             ARRAY['SELECT','INSERT']),
        ('artifact_archive_entries',       ARRAY['SELECT','INSERT']),
        ('artifact_text_sources',          ARRAY['SELECT','INSERT']),
        ('text_extractions',               ARRAY['SELECT','INSERT']),
        ('text_extraction_pages',          ARRAY['SELECT','INSERT']),
        ('document_screening_evaluations', ARRAY['SELECT','INSERT']),
        ('document_screening_evidence',    ARRAY['SELECT','INSERT']),
        -- Revisão humana: trilha imutável.
        ('human_reviews',                  ARRAY['SELECT','INSERT']),
        -- Autenticação interna (AUTH_MODE=internal).
        ('auth_users',                     ARRAY['SELECT']),
        ('auth_permissions',               ARRAY['SELECT']),
        ('auth_user_permissions',          ARRAY['SELECT']),
        ('auth_sessions',                  ARRAY['SELECT','INSERT','UPDATE']),
        ('auth_login_attempts',            ARRAY['SELECT','INSERT','UPDATE','DELETE']),
        ('auth_audit_events',              ARRAY['SELECT','INSERT']),
        -- Allowlist Supabase: somente leitura.
        ('app_admins',                     ARRAY['SELECT']);

    SELECT string_agg(t.tablename, ', ' ORDER BY t.tablename) INTO missing
    FROM pg_tables t
    WHERE t.schemaname = 'public' AND t.tablename <> 'alembic_version'
      AND NOT EXISTS (SELECT 1 FROM runtime_grants g WHERE g.table_name = t.tablename);
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'runtime_role.sql desatualizado: tabelas sem mapeamento: %', missing;
    END IF;

    SELECT string_agg(g.table_name, ', ' ORDER BY g.table_name) INTO missing
    FROM runtime_grants g
    WHERE to_regclass(format('public.%I', g.table_name)) IS NULL;
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'runtime_role.sql referencia tabelas inexistentes: %', missing;
    END IF;

    FOR item IN SELECT * FROM runtime_grants ORDER BY table_name LOOP
        EXECUTE format('GRANT %s ON public.%I TO usiar_runtime',
                       array_to_string(item.privileges, ', '), item.table_name);
    END LOOP;
    FOR policy IN SELECT p.policyname, p.tablename FROM pg_policies p
                  WHERE p.schemaname = 'public' AND p.policyname LIKE 'usiar\_runtime\_%' LOOP
        EXECUTE format('DROP POLICY %I ON public.%I', policy.policyname, policy.tablename);
    END LOOP;

    -- Login interno: só os campos alterados pela autenticação (rehash de senha
    -- e último acesso); ativação, e-mail e desativação ficam com o admin.
    GRANT UPDATE (password_hash, password_version, last_login_at, updated_at)
        ON public.auth_users TO usiar_runtime;
    UPDATE runtime_grants SET privileges = privileges || 'UPDATE'::text WHERE table_name = 'auth_users';

    -- Lease da coleta: adquirir, renovar e liberar. Sem INSERT/DELETE (as linhas
    -- são da migration) e sem alterar `name`/`updated_at`; o trigger da 0013
    -- impede que o fencing_token diminua. SELECT ... FOR SHARE (fencing) exige
    -- UPDATE em ao menos uma coluna, coberto por este GRANT.
    GRANT UPDATE (owner_id, owner_kind, fencing_token, acquired_at, heartbeat_at, expires_at, released_at)
        ON public.collection_leases TO usiar_runtime;
    UPDATE runtime_grants SET privileges = privileges || 'UPDATE'::text WHERE table_name = 'collection_leases';

    -- O acesso por linha é total; o que restringe é o GRANT por operação.
    FOR item IN SELECT * FROM runtime_grants ORDER BY table_name LOOP
        FOREACH command IN ARRAY item.privileges LOOP
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR %s TO usiar_runtime %s',
                'usiar_runtime_' || lower(command), item.table_name, command,
                CASE command
                    WHEN 'INSERT' THEN 'WITH CHECK (true)'
                    WHEN 'UPDATE' THEN 'USING (true) WITH CHECK (true)'
                    ELSE 'USING (true)'
                END);
        END LOOP;
    END LOOP;
END $$;

-- Verificação final: falha (e desfaz tudo com --single-transaction) se a role
-- tiver poderes além do necessário.
DO $$
DECLARE
    role_row pg_roles%ROWTYPE;
    offending text;
BEGIN
    SELECT * INTO role_row FROM pg_roles WHERE rolname = 'usiar_runtime';
    IF role_row.rolsuper OR role_row.rolbypassrls OR role_row.rolreplication
       OR role_row.rolcreaterole OR role_row.rolcreatedb OR role_row.rolinherit THEN
        RAISE EXCEPTION 'usiar_runtime tem atributos privilegiados';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
               WHERE r.rolname = 'usiar_runtime') THEN
        RAISE EXCEPTION 'usiar_runtime não pode ser membro de outras roles';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner
               WHERE r.rolname = 'usiar_runtime')
       OR EXISTS (SELECT 1 FROM pg_namespace n JOIN pg_roles r ON r.oid = n.nspowner
                  WHERE r.rolname = 'usiar_runtime') THEN
        RAISE EXCEPTION 'usiar_runtime não pode ser dona de objetos';
    END IF;
    IF has_schema_privilege('usiar_runtime', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'usiar_runtime não pode criar objetos em public';
    END IF;
    SELECT string_agg(format('%I.%I', n.nspname, c.relname), ', ') INTO offending
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname IN ('auth', 'storage') AND c.relkind IN ('r', 'p', 'v', 'm')
      AND has_schema_privilege('usiar_runtime', n.oid, 'USAGE')
      AND has_table_privilege('usiar_runtime', c.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE');
    IF offending IS NOT NULL THEN
        RAISE EXCEPTION 'usiar_runtime acessa schemas internos do Supabase: %', offending;
    END IF;
END $$;
