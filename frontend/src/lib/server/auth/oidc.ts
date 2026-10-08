import "server-only";
import * as oidc from "openid-client";
import type { Environment } from "../env";
import type { LoginTransaction } from "./session-store";

export class AuthenticationError extends Error {
  constructor() { super("Não foi possível concluir a autenticação."); }
}
export function createOidcClient(env: Environment) {
  let configuration: Promise<oidc.Configuration> | undefined;
  async function discover() {
    if (!env.configured || !env.OIDC_ISSUER || !env.OIDC_CLIENT_ID) throw new AuthenticationError();
    if (!configuration) {
      const auth = env.OIDC_CLIENT_AUTH_METHOD === "none" ? oidc.None() :
        env.OIDC_CLIENT_AUTH_METHOD === "client_secret_post" ? oidc.ClientSecretPost(env.OIDC_CLIENT_SECRET!) : oidc.ClientSecretBasic(env.OIDC_CLIENT_SECRET!);
      configuration = oidc.discovery(new URL(env.OIDC_ISSUER), env.OIDC_CLIENT_ID,
        { id_token_signed_response_alg: env.OIDC_ID_TOKEN_ALG }, auth, { timeout: 10,
          [oidc.customFetch]: (input, init) => fetch(input, { ...init,
            body: init.body instanceof Uint8Array ? new Uint8Array(init.body).buffer : init.body,
            redirect: "error", cache: "no-store" }),
          execute: [oidc.enableNonRepudiationChecks],
        }).then(config => {
          const metadata = config.serverMetadata();
          for (const address of [metadata.authorization_endpoint, metadata.token_endpoint, metadata.jwks_uri]) {
            if (!address) throw new AuthenticationError();
            const url = new URL(address);
            if (url.protocol !== "https:" || url.username || url.password || url.hash) throw new AuthenticationError();
          }
          if (!metadata.code_challenge_methods_supported?.includes("S256")) throw new AuthenticationError();
          return config;
        }).catch(() => { configuration = undefined; throw new AuthenticationError(); });
    }
    return configuration;
  }
  return {
    async authorize(tx: LoginTransaction) {
      const config = await discover();
      const parameters: Record<string, string> = {
        redirect_uri: `${env.APP_ORIGIN}/auth/callback`, response_type: "code", response_mode: "query",
        scope: env.OIDC_SCOPES, state: tx.state!, nonce: tx.nonce!,
        code_challenge: await oidc.calculatePKCECodeChallenge(tx.verifier!), code_challenge_method: "S256",
      };
      if (env.OIDC_RESOURCE) parameters.resource = env.OIDC_RESOURCE;
      if (env.OIDC_AUDIENCE) parameters.audience = env.OIDC_AUDIENCE;
      return oidc.buildAuthorizationUrl(config, parameters);
    },
    async exchange(url: URL, tx: LoginTransaction) {
      try {
        const config = await discover();
        const tokens = await oidc.authorizationCodeGrant(config, url, {
          pkceCodeVerifier: tx.verifier!, expectedState: tx.state!, expectedNonce: tx.nonce!, idTokenExpected: true,
        });
        const claims = tokens.claims();
        if (!claims?.sub || tokens.token_type.toLowerCase() !== "bearer" || !tokens.access_token ||
          !tokens.expires_in || !Number.isFinite(tokens.expires_in) || tokens.expires_in <= 0) throw new AuthenticationError();
        // Refresh and ID tokens deliberately never enter the session store.
        return { accessToken: tokens.access_token, subject: claims.sub, expiresIn: tokens.expires_in };
      } catch { throw new AuthenticationError(); }
    },
  };
}
