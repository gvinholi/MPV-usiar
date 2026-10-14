import { createHash, randomUUID } from "node:crypto";
import { Client } from "pg";
import { evaluate, type Evaluation } from "./screening";
import { fetchPage, mapPublication, type Publication } from "./pncp";
import { usiarV2, type Profile } from "./profiles";
import { acquireLease, fenced, LeaseLostError, recoverOrphanRounds, releaseLease, startHeartbeat, type Lease } from "./lease";
import { endQuietly, isWorkersRuntime, postgresConfig } from "../database-config";

type RuntimeEnv = Partial<CloudflareEnv>;
export type CollectionTrigger = "scheduled" | "manual";
export type CollectionOptions = { trigger?: CollectionTrigger; leaseTtlSeconds?: number; heartbeatMs?: number };
const LEASE_TTL_SECONDS = 120; const HEARTBEAT_MS = 30_000;
export type Outcome={modality:number;complete:boolean;expectedPages:number;pages:number;records:number;mapped:number;failedPage:number|null;reason:string|null;mappingErrors:{item_index:number;message:string}[]};
const log=(event:string,fields:Record<string,unknown>={})=>console.log(JSON.stringify({event,...fields}));
const sha=(value:string)=>createHash("sha256").update(value,"utf8").digest("hex");
function configuration(profile:Profile){return{context_terms:profile.terms.context,ambiguous_context_terms:profile.terms.ambiguous_context,excluded_context_terms:profile.terms.excluded_context,maintenance_terms:profile.terms.maintenance,sanitization_terms:profile.terms.sanitization,installation_terms:profile.terms.installation,purchase_terms:profile.terms.purchase,parts_terms:profile.terms.parts,association_window_tokens:profile.associationWindow??null};}
export function serializeJsonb(value:unknown){const serialized=JSON.stringify(value);if(serialized===undefined)throw new Error("JSONB_SERIALIZATION_FAILED");return serialized;}
export async function persistModalityOutcome(db:Pick<Client,"query">,roundId:string,outcome:Outcome,createdAt:string){
  await db.query(`INSERT INTO collection_modality_outcomes(id,round_id,modality_code,complete,pages_processed,records_received,processes_mapped,failed_page,failure_reason,mapping_errors,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`,[randomUUID(),roundId,outcome.modality,outcome.complete,outcome.pages,outcome.records,outcome.mapped,outcome.failedPage,outcome.reason,serializeJsonb(outcome.mappingErrors),createdAt]);
}
// No Worker só o binding HYPERDRIVE é aceito; DATABASE_URL vale apenas para Node local e testes.
function databaseConfig(env:RuntimeEnv){return postgresConfig({HYPERDRIVE:env.HYPERDRIVE,DATABASE_URL:env.DATABASE_URL},{applicationName:"usiar-collector-worker",requireHyperdrive:isWorkersRuntime()});}
const rethrowLeaseLoss=(error:unknown)=>{if(error instanceof LeaseLostError)throw error;};

async function persistPublication(db:Client,lease:Lease,roundId:string,capturedAt:string,item:Publication,profile:Profile){
  return fenced(db,lease,async()=>{
    const identity=await db.query("SELECT process_id FROM source_identities WHERE source='PNCP' AND official_id=$1",[item.officialId]);let processId:string;
    if(identity.rowCount){processId=String(identity.rows[0].process_id);await db.query("UPDATE processes SET updated_at=$2 WHERE id=$1",[processId,capturedAt]);}
    else{processId=randomUUID();await db.query("INSERT INTO processes(id,created_at,updated_at) VALUES($1,$2,$2)",[processId,capturedAt]);await db.query("INSERT INTO source_identities(id,process_id,source,official_id,created_at) VALUES($1,$2,'PNCP',$3,$4)",[randomUUID(),processId,item.officialId,capturedAt]);}
    const observationId=randomUUID();const observation=await db.query(`INSERT INTO process_observations(id,process_id,round_id,source,captured_at,organization_name,organization_cnpj,description,modality,published_at,closes_at,state,locality,estimated_value,official_url,notice_number,created_at)
      VALUES($1,$2,$3,'PNCP',$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$4) ON CONFLICT(round_id,process_id) DO NOTHING RETURNING id`,[observationId,processId,roundId,capturedAt,item.organizationName,item.organizationCnpj,item.description,item.modality,item.publishedAt,item.closesAt,item.state,item.locality,item.estimatedValue,item.officialUrl,item.noticeNumber]);
    if(!observation.rowCount)return false;
    const result=evaluate(item.description,profile);await persistEvaluation(db,{roundId,processId,observationId,capturedAt,profile,result});return true;
  });
}
async function persistEvaluation(db:Client,input:{roundId:string;processId:string;observationId:string;capturedAt:string;profile:Profile;result:Evaluation}){
  const {processId,observationId,capturedAt,profile,result}=input;const evaluationId=randomUUID();
  const inserted=await db.query(`INSERT INTO screening_evaluations(id,process_id,observation_id,profile_id,state,reason_code,reason_text,evaluated_at,engine_version,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,'1',$8) ON CONFLICT(observation_id,profile_id,engine_version) DO NOTHING RETURNING id`,[evaluationId,processId,observationId,profile.id,result.state,result.reason,result.reasonText,capturedAt]);
  let storedId:string=evaluationId;if(!inserted.rowCount){const existing=await db.query("SELECT id FROM screening_evaluations WHERE observation_id=$1 AND profile_id=$2 AND engine_version='1'",[observationId,profile.id]);storedId=String(existing.rows[0].id);}else for(const evidence of result.evidence)await db.query("INSERT INTO screening_evidence(id,evaluation_id,category,configured_term,field,matched_text,created_at) VALUES($1,$2,$3,$4,'description',$5,$6)",[randomUUID(),evaluationId,evidence.category,evidence.configuredTerm,evidence.matchedText,capturedAt]);
  const lines=[`${profile.code}/${profile.version}`,"1","description",result.state,result.reason,...result.evidence.toSorted((a,b)=>`${a.category}\t${a.configuredTerm}\t${a.matchedText}`.localeCompare(`${b.category}\t${b.configuredTerm}\t${b.matchedText}`)).map((x)=>`${x.category}\t${x.configuredTerm}\tdescription\t${x.matchedText}`)];
  const fingerprint=sha(`${profile.code}/${profile.version}\n1\ninitial:${sha(lines.join("\n"))}\ndocument:NONE`);
  await db.query(`INSERT INTO operational_resolutions(id,process_id,profile_id,initial_evaluation_id,document_evaluation_id,resolver_engine_version,resolution_fingerprint,state,reason_code,reason_text,rule_code,coverage_complete,state_diverged,reason_diverged,initial_state,document_state,resolved_at,created_at)
    VALUES($1,$2,$3,$4,NULL,'1',$5,$6,'INITIAL_SCREENING_ONLY','Ainda não há triagem documental. O estado operacional replica a triagem da description PNCP.','R_INITIAL_ONLY',false,NULL,NULL,$6,NULL,$7,$7) ON CONFLICT(process_id,profile_id,resolver_engine_version,resolution_fingerprint) DO NOTHING`,[randomUUID(),processId,profile.id,storedId,fingerprint,result.state,capturedAt]);
}
function dateInSaoPaulo(now:Date){const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"America/Sao_Paulo",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(now);return `${parts.find(x=>x.type==="year")!.value}-${parts.find(x=>x.type==="month")!.value}-${parts.find(x=>x.type==="day")!.value}`;}
function plusDays(value:string,delta:number){const date=new Date(`${value}T12:00:00Z`);date.setUTCDate(date.getUTCDate()+delta);return date.toISOString().slice(0,10);}

export async function runScheduledCollection(env:RuntimeEnv,transport:typeof fetch=fetch,now=new Date(),options:CollectionOptions={}){
  const config=databaseConfig(env);const ttlSeconds=options.leaseTtlSeconds??LEASE_TTL_SECONDS;const ownerKind=`worker:${options.trigger??"scheduled"}`;
  const db=new Client(config);const endDb=endQuietly(db);await db.connect().catch(async(error)=>{await endDb();throw error;});let lease:Lease|null=null;let heartbeat:ReturnType<typeof startHeartbeat>|undefined;const roundId=randomUUID();const startedAt=now.toISOString();
  try{
    lease=await acquireLease(db,{ownerKind,ttlSeconds});if(!lease){log("collection_skipped",{reason:"already_running"});return{status:"SKIPPED"};}
    const held:Lease=lease;log("collection_lease_acquired",{lease:held.name,owner_id:held.ownerId,owner_kind:ownerKind,fencing_token:held.token});
    heartbeat=startHeartbeat(async()=>{const client=new Client(config);const end=endQuietly(client);try{await client.connect();}catch(error){await end();throw error;}return Object.assign(client,{end});},held,{intervalMs:options.heartbeatMs??HEARTBEAT_MS,ttlSeconds,log});
    const ensureHeld=()=>{if(held.lost)throw new LeaseLostError();};
    const orphans=await recoverOrphanRounds(db,held);if(orphans.length)log("collection_orphan_rounds_failed",{rounds:orphans});
    const profile=usiarV2;
    await fenced(db,held,async()=>{await db.query("INSERT INTO screening_profiles(id,code,name,version,active,configuration,created_at) VALUES($1,$2,$3,$4,true,$5,$6) ON CONFLICT(code,version) DO NOTHING",[profile.id,profile.code,profile.name,profile.version,serializeJsonb(configuration(profile)),startedAt]);
      await db.query(`INSERT INTO collection_rounds(id,source,started_at,status,pages_expected,pages_processed,pages_with_error,records_collected,unique_processes,candidates,selected,pending,discarded,documents_found,errors,created_at) VALUES($1,'PNCP',$2,'RUNNING',0,0,0,0,0,0,0,0,0,0,0,$2)`,[roundId,startedAt]);});
    const endDate=dateInSaoPaulo(now);const days=Math.max(1,Math.min(31,Number(env.COLLECTION_WINDOW_DAYS??2)));const startDate=plusDays(endDate,1-days);const modalities=(env.COLLECTION_MODALITIES??"").split(",").map(Number).filter((x)=>Number.isInteger(x)&&x>0);if(!modalities.length)throw new Error("COLLECTION_MODALITIES_REQUIRED");
    const pageSize=Math.max(10,Math.min(500,Number(env.COLLECTION_PAGE_SIZE??50)));const maxPages=Math.max(2,Math.min(10000,Number(env.COLLECTION_MAX_PAGES??200)));const timeoutMs=Math.max(1000,Math.min(300000,Number(env.COLLECTION_TIMEOUT_SECONDS??30)*1000));const attempts=Math.max(1,Math.min(10,Number(env.COLLECTION_RETRY_ATTEMPTS??3)));const deadline=Date.now()+14*60*1000;const outcomes:Outcome[]=[];
    log("collection_started",{round_id:roundId,start_date:startDate,end_date:endDate,modalities,profile:"USIAR/v2"});
    for(const modality of modalities){const outcome:Outcome={modality,complete:false,expectedPages:0,pages:0,records:0,mapped:0,failedPage:null,reason:null,mappingErrors:[]};
      for(let page=1;page<=maxPages;page++){ensureHeld();const remaining=deadline-Date.now()-5000;if(remaining<1000){outcome.failedPage=page;outcome.reason="worker_deadline";break;}try{const response=await fetchPage({startDate,endDate,modality,page,uf:env.COLLECTION_UF??"SP",pageSize,timeoutMs:Math.min(timeoutMs,remaining),attempts},transport);outcome.expectedPages=Math.max(outcome.expectedPages,response.totalPaginas);if(response.numeroPagina!==page||(response.totalPaginas>0&&response.paginasRestantes!==response.totalPaginas-response.numeroPagina)){outcome.failedPage=page;outcome.reason="inconsistent_pagination";break;}if(page>1&&response.empty&&response.totalPaginas===0){outcome.failedPage=page;outcome.reason="unexpected_empty_page";break;}outcome.pages++;outcome.records+=response.data.length;for(let index=0;index<response.data.length;index++){if(Date.now()>=deadline-5000){outcome.failedPage=page;outcome.reason="worker_deadline";break;}ensureHeld();try{const mapped=mapPublication(response.data[index]!);await persistPublication(db,held,roundId,startedAt,mapped,profile);outcome.mapped++;}catch(error){rethrowLeaseLoss(error);outcome.mappingErrors.push({item_index:index,message:error instanceof Error?error.message:"MAPPING_ERROR"});}}
          if(outcome.reason==="worker_deadline")break;
          if(response.paginasRestantes===0){outcome.complete=outcome.mappingErrors.length===0;break;}if(page===maxPages)outcome.reason=`max_pages=${maxPages}`;
        }catch(error){rethrowLeaseLoss(error);outcome.failedPage=page;outcome.reason=error instanceof Error?error.message:"FETCH_ERROR";break;}}
      outcomes.push(outcome);await fenced(db,held,()=>persistModalityOutcome(db,roundId,outcome,new Date().toISOString()));
    }
    const useful=outcomes.some((x)=>x.complete||x.records>0||x.mapped>0);const status=outcomes.every((x)=>x.complete)?"SUCCESS":useful?"PARTIAL":"FAILED";const errors=outcomes.reduce((n,x)=>n+(x.reason?1:0)+x.mappingErrors.length,0);
    await fenced(db,held,async()=>{const counts=await db.query(`SELECT count(DISTINCT o.process_id)::int unique_processes,count(*) FILTER(WHERE e.state='CANDIDATE')::int candidates,count(*) FILTER(WHERE e.state='PENDING')::int pending,count(*) FILTER(WHERE e.state='DISCARDED')::int discarded FROM process_observations o LEFT JOIN screening_evaluations e ON e.observation_id=o.id AND e.profile_id=$2 WHERE o.round_id=$1`,[roundId,profile.id]);
    await db.query(`UPDATE collection_rounds SET finished_at=$2,status=$3,pages_expected=$4,pages_processed=$5,pages_with_error=$6,records_collected=$7,unique_processes=$8,candidates=$9,pending=$10,discarded=$11,errors=$12 WHERE id=$1`,[roundId,new Date().toISOString(),status,outcomes.reduce((n,x)=>n+x.expectedPages,0),outcomes.reduce((n,x)=>n+x.pages,0),outcomes.filter((x)=>x.reason).length,outcomes.reduce((n,x)=>n+x.records,0),counts.rows[0].unique_processes,counts.rows[0].candidates,counts.rows[0].pending,counts.rows[0].discarded,errors]);});
    const summary={round_id:roundId,status,outcomes,errors};log("collection_finished",summary);return summary;
  }catch(error){log("collection_failed",{round_id:roundId,error_code:error instanceof Error?error.message:"RUN_FAILED"});
    // Também fenced: sem o lease, quem assumiu fecha esta rodada como órfã.
    if(lease)try{const owned=lease;await fenced(db,owned,()=>db.query("UPDATE collection_rounds SET finished_at=clock_timestamp(),status='FAILED',errors=errors+1 WHERE id=$1 AND status='RUNNING'",[roundId]));}catch{}throw error;
  }finally{await heartbeat?.stop();if(lease)try{const released=await releaseLease(db,lease);log(released?"collection_lease_released":"collection_lease_release_skipped",{lease:lease.name,owner_id:lease.ownerId,fencing_token:lease.token});}catch{log("collection_lease_release_failed",{lease:lease.name});}await endDb();}
}
