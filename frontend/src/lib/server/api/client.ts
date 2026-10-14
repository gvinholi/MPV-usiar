import "server-only";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import type { Environment } from "../env";
import * as c from "./contracts";
import { ApiError, httpError } from "./errors";
import { dashboardSummary, listOpportunities } from "./read-model";

type Primitive=string|number|boolean;type Query=Record<string,Primitive|readonly Primitive[]|undefined>;
export type BearerCredential={read():Promise<string|undefined>;invalidate():Promise<void>};
function validate<T extends z.ZodType>(schema:T,value:unknown):z.output<T>{const result=schema.safeParse(value);if(!result.success)throw new ApiError("VALIDATION_ERROR",422);return result.data;}
async function body(response:Response){try{return await response.json() as unknown;}catch{throw new ApiError("INVALID_RESPONSE",502);}}

export function createApiClient(env:Environment,credential:BearerCredential,legacyTransport?:typeof fetch){
  async function authorize(){if(!await credential.read())throw new ApiError("UNAUTHENTICATED",401);}
  async function legacyGet<T extends z.ZodType>(path:string,schema:T,query:Query={}):Promise<z.output<T>>{
    const token=await credential.read();if(!token)throw new ApiError("UNAUTHENTICATED",401);const url=new URL(path,env.FASTAPI_BASE_URL);if(url.origin!==env.FASTAPI_BASE_URL)throw new ApiError("INVALID_RESPONSE",502);
    for(const[name,value]of Object.entries(query)){if(value===undefined)continue;if(Array.isArray(value))value.forEach((item)=>url.searchParams.append(name,String(item)));else url.searchParams.set(name,String(value));}
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),env.API_TIMEOUT_MS);const requestId=randomUUID();
    try{const response=await legacyTransport!(url,{method:"GET",redirect:"error",cache:"no-store",credentials:"omit",headers:{Authorization:`Bearer ${token}`,Accept:"application/json","X-Request-ID":requestId},signal:controller.signal});if(!response.ok){if(response.status===401)await credential.invalidate();const parsed=response.status===409?await body(response).catch(()=>undefined):undefined;throw httpError(response.status,parsed,requestId);}if(!response.headers.get("content-type")?.includes("application/json"))throw new ApiError("INVALID_RESPONSE",502,requestId);const parsed=schema.safeParse(await body(response));if(!parsed.success)throw new ApiError("INVALID_RESPONSE",502,requestId);return parsed.data;}catch(error){if(error instanceof ApiError)throw error;throw new ApiError(controller.signal.aborted?"TIMEOUT":"NETWORK_ERROR",controller.signal.aborted?504:502,requestId);}finally{clearTimeout(timer);}
  }
  const authorized=<T>(operation:()=>Promise<T>)=>async()=>{await authorize();return operation();};
  const processPath=(id:string)=>`/api/v1/opportunities/${validate(z.uuid(),id)}`;
  if(legacyTransport)return{
    ready:()=>legacyGet("/ready",c.HealthResponseSchema),
    getDashboardSummary:(q:c.SummaryQuery)=>legacyGet("/api/v1/dashboard/summary",c.DashboardSummaryResponseSchema,validate(c.summaryQuery,q)),
    listOpportunities:(q:c.OpportunitiesQuery)=>legacyGet("/api/v1/opportunities",c.pageSchema(c.OpportunityListItemResponseSchema),validate(c.opportunitiesQuery,q)),
    getOpportunity:(id:string,p:c.Profile)=>legacyGet(processPath(id),c.OpportunityDetailResponseSchema,validate(c.profileSchema,p)),
    getOpportunityBySource:(source:"PNCP"|"RHS",officialId:string,p:c.Profile)=>legacyGet("/api/v1/opportunities/by-source",c.OpportunityDetailResponseSchema,{...validate(c.profileSchema,p),source:validate(z.enum(["PNCP","RHS"]),source),official_id:validate(z.string().trim().min(1),officialId)}),
    listDocuments:(id:string,p:c.Pagination={})=>legacyGet(`${processPath(id)}/documents`,c.pageSchema(c.OpportunityDocumentResponseSchema),validate(c.paginationSchema,p)),
    listEvidence:(id:string,p:c.Profile,page:c.Pagination={})=>legacyGet(`${processPath(id)}/document-evidence`,c.pageSchema(c.DocumentEvidenceResponseSchema),{...validate(c.profileSchema,p),...validate(c.paginationSchema,page)}),
    listTimeline:(id:string,p:c.Profile,page:c.Pagination={})=>legacyGet(`${processPath(id)}/timeline`,c.pageSchema(c.TimelineItemResponseSchema),{...validate(c.profileSchema,p),...validate(c.paginationSchema,page)}),
    listReviewQueue:(q:c.QueueQuery)=>legacyGet("/api/v1/review-queue",c.pageSchema(c.DashboardReviewQueueItemResponseSchema),validate(c.queueQuery,q)),
    listCollectionRounds:(q:c.RoundsQuery={})=>legacyGet("/api/v1/collection-rounds",c.pageSchema(c.CollectionRoundListItemResponseSchema),validate(c.roundsQuery,q)),
    getCollectionRound:(id:string)=>legacyGet(`/api/v1/collection-rounds/${validate(z.uuid(),id)}`,c.CollectionRoundDetailResponseSchema),
  };
  const unavailable=async()=>{await authorize();throw new ApiError("UNAVAILABLE",501);};
  return{
    ready:authorized(async()=>({status:"ok"})),
    getDashboardSummary:(q:c.SummaryQuery)=>{const parsed=validate(c.summaryQuery,q);return authorized(()=>dashboardSummary(parsed))();},
    listOpportunities:(q:c.OpportunitiesQuery)=>{const parsed=validate(c.opportunitiesQuery,q);return authorized(()=>listOpportunities(parsed))();},
    getOpportunity:(id:string,p:c.Profile)=>{void p;validate(z.uuid(),id);return unavailable();},
    getOpportunityBySource:(source:"PNCP"|"RHS",officialId:string,p:c.Profile)=>{void source;void officialId;void p;return unavailable();},
    listDocuments:(id:string,p:c.Pagination={})=>{void p;validate(z.uuid(),id);return unavailable();},
    listEvidence:(id:string,p:c.Profile,page:c.Pagination={})=>{void p;void page;validate(z.uuid(),id);return unavailable();},
    listTimeline:(id:string,p:c.Profile,page:c.Pagination={})=>{void p;void page;validate(z.uuid(),id);return unavailable();},
    listReviewQueue:(q:c.QueueQuery)=>{void q;return unavailable();},listCollectionRounds:(q:c.RoundsQuery={})=>{void q;return unavailable();},
    getCollectionRound:(id:string)=>{validate(z.uuid(),id);return unavailable();},
  };
}
