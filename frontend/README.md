# Frontend USIAR — fundação do Commit 20

Next.js 16 App Router, React 19, TypeScript strict, Tailwind CSS 4 e componentes shadcn/ui sobre Radix. O servidor Next.js é o BFF. Nenhum ORM, conexão PostgreSQL, coletor ou regra USIAR foi adicionado ao frontend.

## Execução local

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

Sem provedor OIDC configurado, `/login` informa autenticação indisponível e todas as páginas operacionais permanecem protegidas. Não existe conta local, login fictício, token colado no navegador ou modo de bypass. Para visualizar o layout autenticado é necessário OIDC válido; a suíte de interface utiliza infraestrutura isolada exclusivamente de testes.

Inicie a API em outro terminal, conforme o README da raiz:

```powershell
cd collector
uvicorn collector.api.app:create_app --factory --reload
```

A API deve estar configurada com banco e OIDC próprios. Seu access token precisa ser JWT aceito pela API, com issuer/audience/algoritmo corretos e claim `scope` contendo `dashboard:read`. O BFF chama `/ready` em cada entrada de página para confirmar autorização na FastAPI. `reviews:write` sozinho não concede leitura. O frontend não precisa de CORS da API.

## Configuração

Todas as variáveis abaixo são exclusivas do servidor. Não há contrato `NEXT_PUBLIC_*`: valores nesse namespace são rejeitados para evitar publicação acidental de segredos.

| Variável | Uso |
| --- | --- |
| `APP_ORIGIN` | Origem canônica do frontend; sem caminho, query ou credenciais |
| `FASTAPI_BASE_URL` | Origem da API; caminhos `/api/v1/...` são fixos |
| `API_TIMEOUT_MS` | 100–30000 ms; padrão 10000 |
| `SESSION_IDLE_SECONDS` | Limite de inatividade; padrão 1800 |
| `SESSION_ABSOLUTE_SECONDS` | Limite absoluto; padrão 28800; também limitado por `expires_in` do access token |
| `API_PROFILE_ID` / `API_PROFILE_CODE` | Configuração do perfil para futuras páginas de consulta; no máximo um; consultas por perfil exigem exatamente um |
| `OIDC_ISSUER` | Issuer HTTPS aprovado; discovery com comparação exata |
| `OIDC_CLIENT_ID` | Cliente registrado pelo administrador |
| `OIDC_CLIENT_AUTH_METHOD` | `client_secret_basic`, `client_secret_post` ou `none`, conforme registro |
| `OIDC_CLIENT_SECRET` | Obrigatório nos métodos com segredo, proibido com `none` |
| `OIDC_SCOPES` | Padrão `openid dashboard:read`; `offline_access` proibido neste commit |
| `OIDC_RESOURCE` / `OIDC_AUDIENCE` | Somente se exigidos pelo provedor; formas distintas de indicar o recurso |
| `OIDC_ID_TOKEN_ALG` | Algoritmo assimétrico aprovado; padrão `RS256` |

Issuer/client ID/método/segredo reais não são fornecidos no repositório. Configuração OIDC parcial é inválida. Os endpoints de autorização/token/JWKS precisam ser HTTPS; o provedor deve anunciar PKCE S256 e retornar `expires_in` positivo. Cadastre exatamente `APP_ORIGIN/auth/callback`, Authorization Code, PKCE S256 e response mode `query`. O audience do ID token é o client ID; o audience do access token deve atender à FastAPI. Não envie o ID token à API.

## Autenticação, sessão e CSRF

`GET /auth/login` cria uma transação de pré-login e redireciona ao formulário. `POST /auth/login` valida Origin, Fetch Metadata e token CSRF, consome essa transação e cria state/nonce/verifier exclusivos por tentativa. O callback consome a transação antes da troca do código, valida state/nonce/PKCE e assinatura do ID token via JWKS (`enableNonRepudiationChecks`). Transações expiram em cinco minutos. Falhas não preservam uma transação reutilizável.

O cookie contém apenas um identificador aleatório de 256 bits; no store sua chave é SHA-256. Access token fica exclusivamente no servidor. ID token e refresh token não são persistidos. O cookie é HttpOnly, SameSite=Lax, Path=/, sem Domain; Secure em HTTPS/produção e nome `__Host-usiar-session` em produção. Em HTTP local usa `usiar-session`.

Cada acesso verifica expiração absoluta, limite do token e inatividade. Nova autenticação substitui a sessão anterior. `POST /auth/logout` valida CSRF e invalida a sessão no servidor antes de apagar o cookie. GET não encerra sessão. Token expirado exige novo login; não há refresh. Logout é local, não promete encerrar SSO no provedor nem revogar imediatamente um access token já emitido.

`SessionStore` em memória funciona **somente em desenvolvimento/testes, em processo único**. Reinício perde sessões; HMR usa singleton do processo. Produção recusa esse store mesmo com OIDC configurado: páginas protegidas vão ao login indisponível e endpoints de autenticação retornam erro controlado. `npm run build` pode passar, mas isso não habilita autenticação de produção. `npm run start` é apenas smoke de bloqueio seguro até existir implementação compartilhada aprovada.

## Integração HTTP e contratos

`lib/server/api/client.ts` expõe apenas operações GET nomeadas para summary, oportunidades, detalhe, lookup por fonte, documentos, evidências, timeline, fila e rodadas. Não há rota pública BFF de consulta, proxy genérico ou escrita de reviews. O layout não consulta listas nem exibe métricas fictícias.

O cliente obtém Bearer do store, valida query/UUID, restringe o destino à origem configurada, proíbe redirects, omite cookies, aplica timeout e `no-store`, limita respostas a 4 MiB e valida JSON por schemas Zod. Erros 401/403/404/409/422/500/503, timeout, rede e contrato inválido viram mensagens locais controladas. 401 invalida sessão; 403 não inicia loop de login. Apenas códigos conhecidos de conflito são preservados; mensagens internas não são repassadas. `X-Request-ID` é gerado no BFF para correlação com os logs da API.

UUIDs e timestamps permanecem strings; datas incluem offset. Valores monetários permanecem strings decimais. Nulos não viram zeros. Paginação mantém o envelope e limites existentes. Intervalos são fechados no início/abertos no fim; ordenação é allowlist, filtros desconhecidos são rejeitados e `include_operational_discarded` não é aceito como parâmetro HTTP.

Os schemas HTTP de resposta são gerados lendo AST Python, sem importar o coletor, conectar banco ou iniciar FastAPI. O script falha se encontrar anotações que não conhece. A fonte de verdade continua sendo a API; constraints adicionais de comandos de revisão permanecem na FastAPI, e o cliente não oferece escrita.

```powershell
# A partir da raiz, usando o Python existente:
python frontend/scripts/generate-contracts.py --check
# Somente após mudança aprovada no contrato HTTP:
python frontend/scripts/generate-contracts.py
```

## Verificações

```powershell
cd frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:ui
```

Vitest usa transportes de teste e assinaturas RSA reais para validar PKCE, state, nonce, issuer/audience, expiração, assinatura, replay, sessão, cookies, CSRF e o cliente HTTP. O alias `server-only` é substituído apenas na configuração do Vitest.

Playwright inicia um provedor HTTPS de teste na porta 4443, API de teste na 8100, Next dev na 3100 e o build de produção na 3200 para verificar o bloqueio seguro. Execute o build antes da suíte; as portas devem estar livres. Chaves são efêmeras; apenas o certificado público de teste é escrito em `.test-tls/`, ignorado no Git. `NODE_EXTRA_CA_CERTS` é definido somente para o processo de teste, sem desativar validação TLS do BFF. O navegador aceita o certificado local nesse teste. Nenhum endpoint de fixture existe na aplicação. Traces ficam desabilitados para evitar capturar códigos/cookies de autenticação.

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
