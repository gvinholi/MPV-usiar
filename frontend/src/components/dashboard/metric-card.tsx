import { Card, CardContent } from "@/components/ui/card";

const integer = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

export function formatInteger(value: number) {
  return integer.format(value);
}

export function MetricCard({ label, value, description, emphasis = false }: {
  label: string;
  value: number;
  description: string;
  emphasis?: boolean;
}) {
  return <Card className={emphasis ? "border-primary/30 bg-primary/[0.035]" : undefined}>
    <CardContent className="pt-5 sm:pt-6">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight">{formatInteger(value)}</p>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">{description}</p>
    </CardContent>
  </Card>;
}

export function CompactMetric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg border bg-muted/20 p-4">
    <dt className="text-xs font-medium leading-5 text-muted-foreground">{label}</dt>
    <dd className="mt-1 text-xl font-semibold tabular-nums">{formatInteger(value)}</dd>
  </div>;
}
