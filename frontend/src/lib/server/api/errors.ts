import "server-only";

export type ApiErrorCode = "UNAUTHENTICATED" | "FORBIDDEN" | "NOT_FOUND" | "CONFLICT" |
  "AMBIGUOUS_PROFILE" | "IDEMPOTENCY_CONFLICT" | "STALE_OPERATIONAL_RESOLUTION" |
  "VALIDATION_ERROR" | "INTERNAL_ERROR" | "UNAVAILABLE" | "TIMEOUT" | "NETWORK_ERROR" | "INVALID_RESPONSE";
const messages: Record<ApiErrorCode, string> = {
  UNAUTHENTICATED: "Sua sessão expirou. Entre novamente.", FORBIDDEN: "Você não tem permissão para acessar esta área.",
  NOT_FOUND: "Recurso não encontrado.", CONFLICT: "A solicitação conflita com o estado atual.",
  AMBIGUOUS_PROFILE: "O perfil possui mais de uma versão. Configure seu identificador.",
  IDEMPOTENCY_CONFLICT: "Esta solicitação já foi utilizada com outro conteúdo.",
  STALE_OPERATIONAL_RESOLUTION: "A resolução operacional foi atualizada.", VALIDATION_ERROR: "Parâmetros inválidos.",
  INTERNAL_ERROR: "Não foi possível concluir a consulta.", UNAVAILABLE: "Serviço temporariamente indisponível.",
  TIMEOUT: "O serviço demorou para responder.", NETWORK_ERROR: "Não foi possível conectar ao serviço.",
  INVALID_RESPONSE: "O serviço retornou uma resposta incompatível.",
};
export class ApiError extends Error {
  constructor(public readonly code: ApiErrorCode, public readonly status: number, public readonly requestId?: string) {
    super(messages[code]);
  }
}
export function httpError(status: number, body: unknown, requestId: string): ApiError {
  let code: ApiErrorCode = ({401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT",
    422: "VALIDATION_ERROR", 500: "INTERNAL_ERROR", 503: "UNAVAILABLE"} as Record<number, ApiErrorCode>)[status] ?? "INVALID_RESPONSE";
  if (status === 409 && body && typeof body === "object" && "error" in body) {
    const error = body.error;
    if (error && typeof error === "object" && "code" in error &&
      ["AMBIGUOUS_PROFILE", "IDEMPOTENCY_CONFLICT", "STALE_OPERATIONAL_RESOLUTION"].includes(String(error.code))) code = error.code as ApiErrorCode;
  }
  return new ApiError(code, status, requestId);
}
