import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { OPPORTUNITY_COLUMNS, OpportunitiesTable } from "../src/components/opportunities/opportunities-table";
import {
  configuredUsiarV2Profile,
  formatBrl,
  operationalStates,
  opportunitiesHref,
  parseOpportunitiesUrlQuery,
  publicationParts,
  safeOfficialUrl,
  USIAR_V2_PROFILE_ID,
} from "../src/lib/opportunities/query";
import type { OpportunityListItemResponse } from "../src/lib/server/api/contracts.generated";

const item: OpportunityListItemResponse = {
  process_id: "c7d2d8d1-6dc4-4d2e-9aa5-ce4359ff9ad4",
  source: "PNCP",
  official_id: "123/2026/1",
  rhs_id: null,
  description_preview: "Manutenção preventiva de climatização <script>não executar</script>",
  organization_name: "Universidade Pública",
  organization_cnpj: null,
  municipality_name: "Campinas",
  uf: "SP",
  modality: "Pregão Eletrônico",
  estimated_value: "1234.56",
  monthly_value: "0",
  publication_at: "2026-10-13T09:45:00-03:00",
  proposal_deadline_at: null,
  official_url: "https://pncp.gov.br/app/editais/exemplo?destino=consulta",
  notice_number: null,
  operational_resolution_id: null,
  operational_state: "CANDIDATE",
  operational_reason: "INCLUDED_MAINTENANCE",
  operational_resolved_at: null,
  human_review_status: "UNREVIEWED",
  human_decision: null,
  human_reason: null,
  reviewed_at: null,
  documents_count: 0,
  has_text: false,
  has_document_screening: false,
  latest_capture_at: null,
};

describe("opportunities URL and explicit profile", () => {
  it("defaults to the relevant states and resets pagination when filters change", () => {
    expect(parseOpportunitiesUrlQuery({}).data).toEqual({ state: "all", page: 1 });
    expect(operationalStates("all")).toEqual(["CANDIDATE", "PENDING"]);
    expect(operationalStates("candidate")).toEqual(["CANDIDATE"]);
    expect(opportunitiesHref("pending")).toBe("/opportunities?state=pending");
    expect(opportunitiesHref("pending", 2)).toBe("/opportunities?state=pending&page=2");
    expect(parseOpportunitiesUrlQuery({ state: ["candidate", "pending"] }).success).toBe(false);
    expect(parseOpportunitiesUrlQuery({ page: "0" }).success).toBe(false);
  });

  it("requires exactly the configured USIAR/v2 UUID", () => {
    expect(configuredUsiarV2Profile({ API_PROFILE_ID: USIAR_V2_PROFILE_ID })).toEqual({ profile_id: USIAR_V2_PROFILE_ID });
    expect(configuredUsiarV2Profile({ API_PROFILE_CODE: "USIAR" })).toBeUndefined();
    expect(configuredUsiarV2Profile({ API_PROFILE_ID: USIAR_V2_PROFILE_ID, API_PROFILE_CODE: "USIAR" })).toBeUndefined();
  });
});

describe("official timestamp, money and URL presentation", () => {
  it("preserves the official timestamp wall clock and refuses timestamps without offset", () => {
    expect(publicationParts("2026-10-13T09:45:00-03:00")).toEqual({ date: "13/10/2026", hour: "09" });
    expect(publicationParts("2026-10-13T12:45:00Z")).toEqual({ date: "13/10/2026", hour: "12" });
    expect(publicationParts("2026-10-13T09:45:00")).toEqual({ date: "—", hour: "—" });
    expect(publicationParts(null)).toEqual({ date: "—", hour: "—" });
  });

  it("distinguishes null, zero and exact decimal values in BRL", () => {
    expect(formatBrl(null)).toBe("—");
    expect(formatBrl("0")).toBe("R$ 0,00");
    expect(formatBrl("1234.56")).toBe("R$ 1.234,56");
    expect(formatBrl("999999999999999999.999")).toBe("R$ 1.000.000.000.000.000.000,00");
  });

  it("accepts only credential-free HTTP(S) links", () => {
    expect(safeOfficialUrl("https://pncp.gov.br/consulta?destino=edital")).toContain("https://pncp.gov.br/");
    expect(safeOfficialUrl("javascript:alert(1)")).toBeUndefined();
    expect(safeOfficialUrl("data:text/html,secret")).toBeUndefined();
    expect(safeOfficialUrl("https://user:password@example.test/edital")).toBeUndefined();
  });
});

describe("UsiAr opportunity table", () => {
  it("renders all 12 columns in order and maps real values, null and zero", () => {
    const html = renderToStaticMarkup(createElement(OpportunitiesTable, { items: [item] }));
    let previous = -1;
    for (const column of OPPORTUNITY_COLUMNS) {
      const position = html.indexOf(`>${column}<`);
      expect(position).toBeGreaterThan(previous);
      previous = position;
    }
    expect(html).toContain("13/10/2026");
    expect(html).toContain("R$ 0,00");
    expect(html).toContain("R$ 1.234,56");
    expect(html).toContain("INCLUDED_MAINTENANCE");
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain("&lt;script&gt;não executar&lt;/script&gt;");
  });

  it("does not render an unsafe official link and visually distinguishes pending", () => {
    const pending = { ...item, process_id: "4a193fa7-e326-48ea-989f-51b8f554a385", official_url: "javascript:alert(1)", operational_state: "PENDING" };
    const html = renderToStaticMarkup(createElement(OpportunitiesTable, { items: [pending] }));
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain('target="_blank"');
    expect(html).toContain("bg-amber-100");
  });
});
