import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { mapPublication } from "../src/lib/server/collector/pncp";
import { usiarV1, usiarV2, USIAR_V2_ID } from "../src/lib/server/collector/profiles";
import { evaluate } from "../src/lib/server/collector/screening";
import { publicUrl } from "../src/lib/server/api/read-model";

type CorpusCase={case_id:string;description:string;expected_v2:string};
const corpus=JSON.parse(readFileSync(resolve(process.cwd(),"../collector/tests/application/screening/usiar_v2_corpus.json"),"utf8")) as CorpusCase[];

describe("TypeScript parity with the versioned Python screening corpus",()=>{
  it("keeps the official deterministic USIAR/v2 identity",()=>expect(USIAR_V2_ID).toBe("42227c23-f6ea-5a43-b640-56ed6eb6981c"));
  for(const entry of corpus)it(entry.case_id,()=>expect(evaluate(entry.description,usiarV2).state).toBe(entry.expected_v2));
  it("preserves the v1 cross-scope behavior",()=>expect(evaluate("Manutenção predial e aquisição de aparelhos de ar-condicionado",usiarV1)).toMatchObject({state:"PENDING",reason:"MIXED_MAINTENANCE_SUPPLY"}));
  it("keeps distant v2 terms out of maintenance evidence",()=>expect(evaluate("Manutenção predial e aquisição de aparelhos de ar-condicionado",usiarV2)).toMatchObject({state:"DISCARDED",reason:"ISOLATED_EQUIPMENT_PURCHASE"}));
});

describe("PNCP mapping parity",()=>{
  it("maps official fields without promoting numeroCompra to notice number",()=>expect(mapPublication({numeroControlePNCP:"123",numeroCompra:"45",objetoCompra:"Manutenção",dataPublicacaoPncp:"2026-10-13T10:00:00",valorTotalEstimado:0,orgaoEntidade:{razaoSocial:"Órgão"},unidadeOrgao:{ufSigla:"SP",municipioNome:"São Paulo"},linkSistemaOrigem:"https://pncp.gov.br/app/editais/123"})).toMatchObject({officialId:"123",noticeNumber:null,estimatedValue:"0",state:"SP",locality:"São Paulo"}));
  it("rejects missing identity and unsafe source links",()=>{expect(()=>mapPublication({objetoCompra:"x"})).toThrow("MISSING_OFFICIAL_ID");expect(mapPublication({numeroControlePNCP:"1",linkSistemaOrigem:"javascript:alert(1)"}).officialUrl).toBeNull();});
  it("preserves operational query parameters but suppresses sensitive or private links",()=>{
    expect(publicUrl("https://compras.gov.br/consulta?destino=quadro&compra=123")).toBe("https://compras.gov.br/consulta?destino=quadro&compra=123");
    expect(publicUrl("https://compras.gov.br/consulta?access_token=secret")).toBeNull();
    expect(publicUrl("http://127.0.0.1/private")).toBeNull();
  });
});
