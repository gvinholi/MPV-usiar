import { ExternalLink } from "lucide-react";
import type { OpportunityListItemResponse } from "@/lib/server/api/contracts.generated";
import { formatBrl, publicationParts, safeOfficialUrl } from "@/lib/opportunities/query";

export const OPPORTUNITY_COLUMNS = [
  "ID RHS", "DATA", "Hr", "ORGÃO", "CIDADE", "TIPO", "SITE", "N EDITAL",
  "TIPO DO SERVIÇO", "VALOR MENSAL", "VALOR ESTIMADO", "OBSERVAÇÃO",
] as const;

function CellValue({ children }: { children: React.ReactNode }) {
  return children === null || children === undefined || children === "" ? <>—</> : <>{children}</>;
}

function ServiceType({ item }: { item: OpportunityListItemResponse }) {
  if (!item.operational_state) return <>—</>;
  const pending = item.operational_state === "PENDING";
  return <div className="min-w-40 space-y-2">
    <span className={pending
      ? "inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-900"
      : "inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-900"}>
      {item.operational_state}
    </span>
    {item.operational_reason && <code className="block whitespace-normal text-xs text-muted-foreground">{item.operational_reason}</code>}
  </div>;
}

function Description({ value }: { value: string | null }) {
  if (!value) return <>—</>;
  const short = value.length > 110 ? `${value.slice(0, 107)}…` : value;
  return <details className="min-w-64 max-w-80">
    <summary className="cursor-pointer whitespace-normal text-sm leading-5 marker:text-primary">{short}</summary>
    <p className="mt-2 whitespace-normal border-l-2 border-primary/30 pl-3 text-sm leading-5 text-muted-foreground">{value}</p>
  </details>;
}

export function OpportunitiesTable({ items }: { items: OpportunityListItemResponse[] }) {
  return <div className="overflow-x-auto rounded-xl border bg-background shadow-sm">
    <table className="min-w-[1480px] border-collapse text-sm" aria-label="Oportunidades relevantes no formato da planilha UsiAr">
      <thead className="bg-muted/80">
        <tr>{OPPORTUNITY_COLUMNS.map(column => <th key={column} scope="col" className="whitespace-nowrap border-b px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">{column}</th>)}</tr>
      </thead>
      <tbody>
        {items.map(item => {
          const publication = publicationParts(item.publication_at);
          const officialUrl = safeOfficialUrl(item.official_url);
          return <tr key={item.process_id} className="align-top transition-colors hover:bg-muted/40">
            <td className="border-b px-4 py-4"><CellValue>{item.rhs_id}</CellValue></td>
            <td className="whitespace-nowrap border-b px-4 py-4 tabular-nums">{publication.date}</td>
            <td className="whitespace-nowrap border-b px-4 py-4 tabular-nums">{publication.hour}</td>
            <td className="min-w-56 whitespace-normal border-b px-4 py-4 font-medium"><CellValue>{item.organization_name}</CellValue></td>
            <td className="min-w-40 whitespace-normal border-b px-4 py-4"><CellValue>{item.municipality_name}</CellValue></td>
            <td className="min-w-44 whitespace-normal border-b px-4 py-4"><CellValue>{item.modality}</CellValue></td>
            <td className="border-b px-4 py-4">{officialUrl ? <a href={officialUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 font-medium text-primary underline-offset-4 hover:underline">Abrir edital<ExternalLink className="size-3.5" aria-hidden="true" /></a> : "—"}</td>
            <td className="min-w-36 whitespace-normal border-b px-4 py-4"><CellValue>{item.notice_number}</CellValue></td>
            <td className="border-b px-4 py-4"><ServiceType item={item} /></td>
            <td className="whitespace-nowrap border-b px-4 py-4 text-right tabular-nums">{formatBrl(item.monthly_value)}</td>
            <td className="whitespace-nowrap border-b px-4 py-4 text-right tabular-nums">{formatBrl(item.estimated_value)}</td>
            <td className="border-b px-4 py-4"><Description value={item.description_preview} /></td>
          </tr>;
        })}
      </tbody>
    </table>
  </div>;
}
