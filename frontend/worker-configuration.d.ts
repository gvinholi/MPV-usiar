/// <reference types="@cloudflare/workers-types" />

interface CloudflareEnv {
  ASSETS: Fetcher;
  WORKER_SELF_REFERENCE: Fetcher;
  DATABASE_URL: string;
  SUPABASE_URL: string;
  SUPABASE_ANON_KEY: string;
  APP_ORIGIN: string;
  API_PROFILE_ID?: string;
  API_PROFILE_CODE?: string;
  COLLECTION_UF?: string;
  COLLECTION_PROFILE?: string;
  COLLECTION_WINDOW_DAYS?: string;
  COLLECTION_PAGE_SIZE?: string;
  COLLECTION_MAX_PAGES?: string;
  COLLECTION_MODALITIES?: string;
  COLLECTION_TIMEOUT_SECONDS?: string;
  COLLECTION_RETRY_ATTEMPTS?: string;
}
