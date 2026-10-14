# Frontend USIAR

Next.js 16 App Router, React 19 e TypeScript strict sobre Cloudflare Workers/OpenNext. O servidor Next.js consulta o PostgreSQL internamente; o mesmo Worker executa o coletor PNCP TypeScript por Cloudflare Cron. A interface e as 12 colunas UsiAr foram preservadas.

## Runtime Cloudflare + Supabase (Commit 31)

- Supabase Auth fornece login por e-mail/senha, recuperação e cookies `HttpOnly`; signup público não existe.
- `app_admins` é uma allowlist explícita. Criar um usuário no Supabase Auth não concede acesso ao sistema.
- `DATABASE_URL` usa conexão direta ou o **Session Pooler** do Supabase. Hyperdrive e Transaction Pooler não podem ser usados pelo coletor porque não preservam o advisory lock de sessão.
- `custom-worker.ts` reutiliza o handler OpenNext e adiciona Cron às 09:00, 15:00 e 21:00 UTC (06:00, 12:00 e 18:00 em Brasília no regime atual).
- O coletor persiste cada observação em transação própria, preserva snapshots e triagens existentes, e reporta teto/timeout como `PARTIAL`, nunca `SUCCESS` silencioso.
- O Python permanece no repositório como rollback/referência e continua sendo a fonte das migrations Alembic 0001–0011.

Não coloque segredos em `.env.example`, `wrangler.jsonc` ou no Git. Configure `DATABASE_URL`, `SUPABASE_URL` e `SUPABASE_ANON_KEY` no ambiente do Worker. A service role é usada somente na estação administrativa para conceder a allowlist e nunca é configurada no Worker.

```powershell
cd frontend
npm.cmd ci
Copy-Item .env.example .env.local
# preencha .env.local fora do Git
npm.cmd run dev

# build/preview no runtime Workers
npm.cmd run build:worker
npm.cmd run preview:worker
```

Após criar manualmente a única conta piloto no painel Supabase Auth, aplique a migration 0011 e conceda acesso sem conhecer ou transportar a senha:

```powershell
$env:SUPABASE_SERVICE_ROLE_KEY = "<secret somente nesta sessão>"
npm.cmd run admin:grant -- admin@empresa.example
Remove-Item Env:SUPABASE_SERVICE_ROLE_KEY
```

O deploy é deliberadamente manual: `npm.cmd run deploy:worker`. Antes de habilitá-lo, valide uma coleta real controlada; o tempo total de paginação sob o limite de 15 minutos do Cron ainda depende do volume real do PNCP.

O bundle OpenNext deve ser validado em Linux/CI. No Windows, o próprio adaptador alerta sobre compatibilidade incompleta e pode falhar ao criar os links simbólicos do bundle; isso não deve ser interpretado como validação do runtime Cloudflare.

`npm audit --omit=dev` não encontrou vulnerabilidades na árvore de produção em 14/10/2026. O audit completo ainda reporta 9 ocorrências altas somente nas cadeias de desenvolvimento: `braces` via ESLint e `glob` via OpenNext/@node-minify. As correções automáticas propostas são mudanças incompatíveis (downgrade do `eslint-config-next` ou troca forçada do adaptador), portanto não foram aplicadas sem validação upstream.

### Custo e limites do piloto

O coletor não é compatível com os 10 ms de CPU e 50 subrequests externos por invocação do Workers Free. O piloto requer **Workers Paid**, atualmente com mínimo de US$ 5/mês, para obter o teto de Cron e subrequests compatíveis; ainda assim cada Cron tem 15 minutos de wall time e a medição real da coleta continua obrigatória. Supabase Free pode atender ao piloto inicial se o banco permanecer abaixo de 500 MB e das demais cotas do plano. Não há dependência de Hyperdrive, Durable Objects ou outro serviço pago adicional neste desenho.

## Referência do runtime anterior

> As seções abaixo documentam o runtime Python/FastAPI e os modos `internal`/OIDC preservados exclusivamente para rollback. Eles não ficam ativos junto com Supabase Auth em produção. Para executar o Commit 31, use somente a seção **Runtime Cloudflare + Supabase** acima.

## Execução local do rollback

Requer Node.js **24.x** e npm. Use o checkout existente; não execute `git init`.

```powershell
cd frontend
node --version
npm.cmd --version
npm.cmd ci
Copy-Item .env.example .env.local
npm.cmd run dev
```

Abra **http://127.0.0.1:3000**. Use esse host de forma consistente; `localhost` é outra origem para cookies/CSRF. No Windows, `npm.cmd` evita dependência da política de execução de scripts PowerShell. Se acabou de instalar Node, abra um novo terminal para atualizar o PATH. Em outros sistemas, use `npm`.

`AUTH_MODE` seleciona explicitamente `internal` ou `oidc`. No modo interno, crie a conta Admin/Dev pelo bootstrap interativo da raiz; não existe conta automática, senha padrão, login fictício ou bypass. No modo OIDC, configure um provedor válido. Configuração ausente ou incompatível mantém todas as páginas operacionais protegidas.

Inicie a API em outro terminal, conforme o README da raiz:

```powershell
cd collector
uvicorn collector.api.app:create_app --factory --reload
```

A API e o frontend devem usar o mesmo `AUTH_MODE`. Em `internal`, a conta e as permissões vêm do PostgreSQL. Em `oidc`, o access token precisa ser JWT aceito pela API, com issuer/audience/algoritmo corretos e `scope` contendo `dashboard:read`. O dashboard usa sua consulta real sem chamada redundante a `/ready`; páginas ainda em preparação usam `/ready`. `reviews:write` sozinho não concede leitura. O frontend não precisa de CORS da API.

Para o primeiro acesso interno, aplique as migrations e execute uma vez o bootstrap interativo, que lê a senha com `getpass`:

```powershell
docker compose up -d
cd collector
$env:DATABASE_URL = "postgresql+psycopg://usiar:usiar@localhost:5433/usiar"
alembic upgrade head
python -m collector.cli.auth bootstrap-admin
```

Inicie FastAPI e Next.js em terminais separados, ambos com `AUTH_MODE=internal`. Gere chaves somente em memória e nunca inclua seus valores em comandos versionados ou logs:

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$env:INTERNAL_AUTH_RATE_LIMIT_KEY = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
$env:AUTH_MODE = "internal"
uvicorn collector.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$env:AUTH_COOKIE_KEY = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
$env:AUTH_MODE = "internal"
$env:APP_ORIGIN = "http://127.0.0.1:3000"
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
$env:API_PROFILE_ID = "42227c23-f6ea-5a43-b640-56ed6eb6981c"
$env:API_PROFILE_CODE = ""
npm.cmd run dev
```

## Configuração

Todas as variáveis abaixo são exclusivas do servidor. Não há contrato `NEXT_PUBLIC_*`: valores nesse namespace são rejeitados para evitar publicação acidental de segredos.

| Variável | Uso |
| --- | --- |
| `AUTH_MODE` | Obrigatória; exatamente `internal` ou `oidc`, sem fallback |
| `AUTH_COOKIE_KEY` | Em `internal`, chave AES-256-GCM: 32 bytes aleatórios em base64url canônico |
| `APP_ORIGIN` | Origem canônica do frontend; sem caminho, query ou credenciais |
| `FASTAPI_BASE_URL` | Origem da API; caminhos `/api/v1/...` são fixos |
| `API_TIMEOUT_MS` | 100–30000 ms; padrão 10000 |
| `SESSION_IDLE_SECONDS` | Limite de inatividade; padrão 1800 |
| `SESSION_ABSOLUTE_SECONDS` | Limite absoluto; padrão 28800; também limitado por `expires_in` do access token |
| `API_PROFILE_ID` / `API_PROFILE_CODE` | Perfil das consultas; `/opportunities` exige o UUID de USIAR/v2 em `API_PROFILE_ID` e `API_PROFILE_CODE` vazio |
| `OIDC_ISSUER` | Issuer HTTPS aprovado; discovery com comparação exata |
| `OIDC_CLIENT_ID` | Cliente registrado pelo administrador |
| `OIDC_CLIENT_AUTH_METHOD` | `client_secret_basic`, `client_secret_post` ou `none`, conforme registro |
| `OIDC_CLIENT_SECRET` | Obrigatório nos métodos com segredo, proibido com `none` |
| `OIDC_SCOPES` | Padrão `openid dashboard:read`; `offline_access` proibido neste commit |
| `OIDC_RESOURCE` / `OIDC_AUDIENCE` | Somente se exigidos pelo provedor; formas distintas de indicar o recurso |
| `OIDC_ID_TOKEN_ALG` | Algoritmo assimétrico aprovado; padrão `RS256` |

Issuer/client ID/método/segredo reais não são fornecidos no repositório. Configuração OIDC parcial é inválida. Os endpoints de autorização/token/JWKS precisam ser HTTPS; o provedor deve anunciar PKCE S256 e retornar `expires_in` positivo. Cadastre exatamente `APP_ORIGIN/auth/callback`, Authorization Code, PKCE S256 e response mode `query`. O audience do ID token é o client ID; o audience do access token deve atender à FastAPI. Não envie o ID token à API.

## Autenticação, sessão e CSRF

No modo `internal`, `GET /login` prepara automaticamente um CSRF de pré-login. O formulário envia e-mail e senha somente ao `POST /auth/login` do BFF. O BFF valida origem, Fetch Metadata, tipo e tamanho do corpo, campos exatos e CSRF; então chama `POST /api/v1/auth/session` server-side. A resposta da FastAPI é validada e guardada em envelope AES-256-GCM no cookie `usiar-internal-session`. O envelope contém somente versão, modo, token opaco, CSRF da API, CSRF independente do navegador e expiração absoluta. IV de 96 bits é novo a cada cifragem e a tag GCM é verificada antes do uso.

O cookie interno é HttpOnly, SameSite=Lax, Path=/, sem Domain e Secure em HTTPS/produção; em produção recebe prefixo `__Host-`. Token e CSRF da FastAPI nunca aparecem em HTML, URL, JavaScript, Web Storage ou resposta do BFF. O PostgreSQL permanece a autoridade: inatividade, expiração absoluta, revogação, usuário, versão da senha e permissões são revalidados pela FastAPI. O Next.js não cria sessão interna paralela em memória.

`AUTH_COOKIE_KEY` deve permanecer secreta e estável entre reinicializações e réplicas. Trocar a chave encerra localmente todos os cookies internos existentes. Use um gerenciador de segredos em produção e não reutilize a chave entre ambientes.

`POST /auth/logout` valida o CSRF do navegador e chama `DELETE /api/v1/auth/session` com Bearer e CSRF da API somente no canal Next.js→FastAPI. Em 204 ou 401, limpa o cookie. Se revogação falhar por 403, 500, 503, timeout ou rede, mantém a sessão local e retorna erro sanitizado para permitir nova tentativa. `GET /auth/logout` não existe.

No modo `oidc`, o fluxo existente permanece:

`GET /auth/login` cria uma transação de pré-login e redireciona ao formulário. `POST /auth/login` valida Origin, Fetch Metadata e token CSRF, consome essa transação e cria state/nonce/verifier exclusivos por tentativa. O callback consome a transação antes da troca do código, valida state/nonce/PKCE e assinatura do ID token via JWKS (`enableNonRepudiationChecks`). Transações expiram em cinco minutos. Falhas não preservam uma transação reutilizável.

O cookie contém apenas um identificador aleatório de 256 bits; no store sua chave é SHA-256. Access token fica exclusivamente no servidor. ID token e refresh token não são persistidos. O cookie é HttpOnly, SameSite=Lax, Path=/, sem Domain; Secure em HTTPS/produção e nome `__Host-usiar-session` em produção. Em HTTP local usa `usiar-session`.

Cada acesso verifica expiração absoluta, limite do token e inatividade. Nova autenticação substitui a sessão anterior. `POST /auth/logout` valida CSRF e invalida a sessão no servidor antes de apagar o cookie. GET não encerra sessão. Token expirado exige novo login; não há refresh. Logout é local, não promete encerrar SSO no provedor nem revogar imediatamente um access token já emitido.

`SessionStore` em memória funciona **somente em desenvolvimento/testes, em processo único**. Reinício perde sessões; HMR usa singleton do processo. Produção recusa esse store mesmo com OIDC configurado: páginas protegidas vão ao login indisponível e endpoints de autenticação retornam erro controlado. `npm run build` pode passar, mas isso não habilita autenticação de produção. `npm run start` é apenas smoke de bloqueio seguro até existir implementação compartilhada aprovada.

## Integração HTTP e contratos

`lib/server/api/client.ts` expõe apenas operações GET nomeadas para summary, oportunidades, detalhe, lookup por fonte, documentos, evidências, timeline, fila e rodadas. Não há rota pública BFF de consulta, proxy genérico ou escrita de reviews. O layout não consulta listas nem exibe métricas fictícias.

O cliente obtém Bearer da credencial server-only selecionada, valida query/UUID, restringe o destino à origem configurada, proíbe redirects, omite cookies, aplica timeout e `no-store`, limita respostas a 4 MiB e valida JSON por schemas Zod. Erros 401/403/404/409/422/500/503, timeout, rede e contrato inválido viram mensagens locais controladas. 401 invalida a sessão OIDC ou faz o fluxo interno voltar ao login; 403 não inicia loop. Apenas códigos conhecidos de conflito são preservados; mensagens internas não são repassadas. `X-Request-ID` é gerado no BFF para correlação com os logs da API.

UUIDs e timestamps permanecem strings; datas incluem offset. Valores monetários permanecem strings decimais. Nulos não viram zeros. Paginação mantém o envelope e limites existentes. Intervalos são fechados no início/abertos no fim; ordenação é allowlist, filtros desconhecidos são rejeitados e `include_operational_discarded` não é aceito como parâmetro HTTP.

Os schemas HTTP são gerados de `schemas.py` e `auth_schemas.py` lendo AST Python, sem importar o coletor, conectar banco ou iniciar FastAPI. `StrictStr`, limites por pontos de código Unicode, campos obrigatórios, datetimes e `extra="forbid"` são preservados. O script falha se encontrar anotações que não conhece. A fonte de verdade continua sendo a API; constraints adicionais de comandos de revisão permanecem na FastAPI, e o cliente não oferece escrita operacional.

```powershell
# A partir da raiz, usando o Python existente:
python frontend/scripts/generate-contracts.py --check
# Somente após mudança aprovada no contrato HTTP:
python frontend/scripts/generate-contracts.py
```

## Dashboard operacional

`/dashboard` consome exclusivamente `GET /api/v1/dashboard/summary` em um Server
Component. A página lê a sessão selecionada, obtém o Bearer somente no servidor e chama a
operação nomeada `getDashboardSummary`; não consulta `/ready` antes, não oferece proxy
ao navegador e não envia tokens, credenciais ou configuração de perfil para componentes
cliente. A resposta permanece `no-store` e é validada pelo contrato Zod gerado.

O perfil vem somente de `API_PROFILE_ID` ou `API_PROFILE_CODE`. Exatamente um valor
válido é exigido antes da consulta. Parâmetros `profile_id` e `profile_code` na URL são
rejeitados. Código ambíguo apresenta uma orientação para configurar o UUID, sem tentar
escolher uma versão. A API retorna apenas o UUID resolvido; nome e versão não são
inventados pela interface.

O filtro aceita `from_datetime` e `to_datetime` opcionais em `datetime-local`, converte
o instante local para ISO 8601 UTC e o preserva na URL. O intervalo é fechado no início
e aberto no fim. A página rejeita valores repetidos, chaves desconhecidas, timestamps
sem fuso e intervalo invertido antes da chamada à API. Sem limites, todo o histórico é
consultado; não existe período padrão implícito.

O dashboard distingue três bases:

- **estado atual da coorte:** estado vigente dos processos cujo primeiro registro está
  no período selecionado;
- **atividade do perfil:** avaliações documentais, resoluções operacionais e revisões
  humanas ocorridas no período para o perfil consultado;
- **coleta geral:** rodadas, registros, processos e documentos descobertos, além da
  cobertura por fonte, sem restrição ao perfil.

O funil exibe somente contagens absolutas fornecidas pela API. A interface não calcula
taxas, perdas, tendências, percentuais ou rodadas em andamento. Fontes são tratadas
como strings abertas. Resumo realmente zerado tem estado vazio próprio; falhas 401,
403, 404, 409, 422, 500, 503, rede e timeout continuam sendo erros, nunca listas vazias.

## Tela de oportunidades

`/opportunities` é um Server Component protegido e usa somente a operação nomeada
`listOpportunities` do BFF. O Bearer permanece no servidor. A consulta envia
explicitamente `profile_id=42227c23-f6ea-5a43-b640-56ed6eb6981c` e repete
`operational_state` para `CANDIDATE` e `PENDING`; `DISCARDED` não participa da
listagem padrão.

Os filtros “Todas as relevantes”, “Somente candidatas” e “Somente pendentes” alteram
a URL e sempre reiniciam na página 1. Anterior/Próxima solicitam uma nova página de
25 itens à API; nenhuma paginação ou filtragem global é simulada no navegador.

A tabela preserva as 12 colunas da aba UsiAr e usa rolagem horizontal em telas
estreitas. Timestamp com offset é apresentado pela data e hora oficiais codificadas,
sem conversão implícita de fuso. Valores decimais são formatados em BRL; `null` vira
“—” e zero permanece `R$ 0,00`. Links são renderizados apenas para HTTP(S) sem
credenciais. Cidade identifica a unidade compradora, não o local inferido de execução.

Antes da primeira coleta, a tela mostra um estado vazio específico. Falhas da API
mantêm estado de erro e ação de nova tentativa; 401 segue o fluxo existente de sessão
expirada. `rhs_id`, `notice_number` e `monthly_value` podem aparecer vazios porque o
PNCP não fornece esses conceitos de forma segura em todos os registros.

## Verificações

```powershell
cd frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:ui
npm.cmd run test:ui:internal
```

Vitest usa transportes de teste e assinaturas RSA reais para validar PKCE, state, nonce, issuer/audience, expiração, assinatura, replay, sessão, cookies, CSRF e o cliente HTTP. O alias `server-only` é substituído apenas na configuração do Vitest.

Playwright cobre OIDC com provedor HTTPS de teste na porta 4443, API de teste na 8100, Next dev na 3100 e o build de produção na 3200. A suíte interna separada usa Next na 3300 e a API isolada de teste. Execute o build antes da suíte OIDC; as portas devem estar livres. Chaves são efêmeras; apenas o certificado público de teste é escrito em `.test-tls/`, ignorado no Git. `NODE_EXTRA_CA_CERTS` é definido somente para o processo de teste, sem desativar validação TLS do BFF. Nenhum endpoint de fixture existe na aplicação. Traces ficam desabilitados para evitar capturar credenciais ou cookies.

Testes de navegador exercitam desktop/mobile, navegação, modal, retorno de foco, proteção das quatro rotas, logout, CSRF, falta de permissão e ausência de tokens em HTML/storage/cookies acessíveis por JavaScript. A integração com provedor e API reais requer configuração externa e não é substituída por esses testes.

## Antes de produção

- Aprovar e implementar store compartilhado, com TTL, consumo atômico de transações, revogação e proteção dos tokens em repouso; nenhuma dependência desse tipo está instalada.
- Configurar provedor, audience do access token, escopos mínimos, registro do cliente, callback e identidade compatível com os limites da FastAPI.
- Provisionar HTTPS, gestão/rotação de segredos, proteção de rede e limites de acesso. Não confiar em Host/forwarded headers para construir callbacks.
- Configurar proxy/observabilidade para nunca registrar cookies, Authorization, corpo do token endpoint ou query do callback. O logging de requisições do Next dev está desabilitado para não registrar códigos/state.
- Definir política de sessão/SSO, revogação no provedor, CSP e rate limiting de login. O store local tem limite de capacidade, mas não é solução de disponibilidade/abuso para produção.

**Dependências de desenvolvimento:** o advisory GHSA-vfj7-8cjw-p6xm / CVE-2026-93687 afeta `braces@3.0.3` na cadeia do lint (`eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces`). Em 2026-10-08 não havia versão corrigida publicada. A aceitação temporária cobre somente desenvolvimento: não passe padrões glob não confiáveis a esse tooling e não o exponha como serviço público. Continue executando e reportando o `npm audit` completo; reavalie a exceção quando houver correção upstream. `npm audit --omit=dev` verifica separadamente a árvore de produção. Consulte a seção 40 de `docs/ARCHITECTURE.md` para impacto, evidências e limites da decisão.

ESLint 9 é mantido temporariamente com a configuração oficial do Next.js 16, sem desabilitar regras, enquanto o suporte completo a ESLint 10 no Next e nos plugins permanece pendente. Seu fim de suporte é um risco residual conhecido. Não foi feito downgrade de Next, fork de `braces` nem `audit fix --force`.

## Fora do Commit 20

Gráficos, tabelas completas, filtros visuais, formulários de decisão, escrita de reviews, refresh token, exportações, implantação e alterações de regras USIAR. As quatro páginas apresentam somente a estrutura inicial e o estado de acesso/integração.
