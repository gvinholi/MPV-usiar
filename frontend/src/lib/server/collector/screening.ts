import type { Category, Profile } from "./profiles";

export type State = "CANDIDATE" | "PENDING" | "DISCARDED";
export type Evidence = { category: Category; configuredTerm: string; field: "description"; matchedText: string };
export type Evaluation = { state: State; reason: string; reasonText: string; evidence: Evidence[] };
type Match = { category: Category; term: string; start: number; end: number };
const fillers = new Set(["a","as","com","da","das","de","do","dos","e","em","linear","lineares","metro","metros","na","nas","no","nos","o","os","para","por"]);
export function tokenize(text: string) { return text.toLocaleLowerCase("pt-BR").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[-/]/g, " ").replace(/[^0-9a-z]+/g, " ").trim().split(/\s+/).filter(Boolean); }
function matches(tokens: string[], profile: Profile) {
  const found: Match[] = [];
  for (const [category, terms] of Object.entries(profile.terms) as [Category, readonly string[]][]) for (const term of terms) {
    const needle = tokenize(term); for (let i=0; i<=tokens.length-needle.length; i++) if (needle.every((token,j) => tokens[i+j] === token)) found.push({ category, term, start:i, end:i+needle.length });
  }
  return found;
}
function gap(a: Match,b: Match,tokens:string[]) { const between = a.end<=b.start ? tokens.slice(a.end,b.start) : b.end<=a.start ? tokens.slice(b.end,a.start) : []; return between.filter((token) => !fillers.has(token) && !/^\d+$/.test(token)).length; }
function evidence(description:string, profile:Profile) {
  const output: Evidence[] = [];
  for (const clause of profile.associationWindow === undefined ? [description] : description.split(/[.;:\n]+/)) {
    const tokens=tokenize(clause); const all=matches(tokens,profile); let selected=all;
    if (profile.associationWindow !== undefined) {
      const contexts=all.filter((m)=>m.category==="context"||m.category==="ambiguous_context"); const associated=new Set(all.filter((m)=>contexts.includes(m)||contexts.some((c)=>gap(m,c,tokens)<=profile.associationWindow!)));
      const exclusions=all.filter((m)=>["installation","purchase","parts"].includes(m.category)); const services=all.filter((m)=>["maintenance","sanitization"].includes(m.category));
      for (const service of services) if (exclusions.some((x)=>associated.has(x)&&gap(service,x,tokens)===0)) associated.add(service);
      if (services.some((s)=>associated.has(s))&&contexts.length) exclusions.forEach((x)=>associated.add(x)); selected=all.filter((m)=>associated.has(m));
    }
    output.push(...selected.map((m)=>({category:m.category,configuredTerm:m.term,field:"description" as const,matchedText:tokens.slice(m.start,m.end).join(" ")})));
  }
  return output;
}
function decision(items: Evidence[]): [State,string] {
  const has=(category:Category)=>items.some((item)=>item.category===category); const relevant=has("context")&&(has("maintenance")||has("sanitization"));
  if(has("excluded_context"))return["DISCARDED","EXCLUDED_CONTEXT"];
  if(relevant&&has("installation"))return["PENDING","MIXED_MAINTENANCE_INSTALLATION"];
  if(relevant&&(has("purchase")||has("parts")))return["PENDING","MIXED_MAINTENANCE_SUPPLY"];
  if(relevant&&has("maintenance"))return["CANDIDATE","RELEVANT_MAINTENANCE"];
  if(relevant&&has("sanitization"))return["CANDIDATE","RELEVANT_SANITIZATION"];
  if(has("context")&&has("installation"))return["DISCARDED","ISOLATED_INSTALLATION"];
  if(has("context")&&has("parts"))return["DISCARDED","ISOLATED_PARTS_SUPPLY"];
  if(has("context")&&has("purchase"))return["DISCARDED","ISOLATED_EQUIPMENT_PURCHASE"];
  if(has("context")||has("ambiguous_context")||((has("maintenance")||has("sanitization"))&&(has("installation")||has("purchase")||has("parts"))))return["PENDING","AMBIGUOUS_RELEVANT_CONTEXT"];
  return["DISCARDED","NO_RELEVANT_SCOPE"];
}
export function evaluate(description:string|null, profile:Profile):Evaluation {
  if(!description?.trim())return{state:"PENDING",reason:"EMPTY_DESCRIPTION",reasonText:"A observação não possui descrição para avaliar.",evidence:[]};
  const found=evidence(description,profile); const [state,reason]=decision(found); const terms=[...new Set(found.map((x)=>x.configuredTerm))].sort().join(", ");
  return{state,reason,reasonText:`${reason.replaceAll("_"," ")}.${terms?` Termos: ${terms}.`:""}`,evidence:found};
}
