// ui/src/components/FamilyRail.tsx
/**
 * Navegacao familia -> subfamilia.
 *
 * Trilho horizontal rolavel no celular, coluna no monitor. A contagem fica
 * visivel porque saber que "Reaction" tem 1791 e "Hypnotic" tem 280 muda a
 * decisao de por onde comecar.
 */
import type { Family, Subfamily } from "../api";

interface Props {
  families: Family[];
  subfamilies: Subfamily[];
  selectedFamily: string | null;
  selectedSubfamily: string | null;
  onSelectFamily: (family: string | null) => void;
  onSelectSubfamily: (subfamily: string | null) => void;
}

function Chip({ label, count, active, onClick }: {
  label: string; count?: number; active: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      style={{
        padding: "0 calc(var(--step) * 1.5)",
        whiteSpace: "nowrap",
        color: active ? "var(--ground)" : "var(--ink-dim)",
        background: active ? "var(--accent)" : "transparent",
        borderBottom: active ? "none" : "1px solid var(--rule)",
        letterSpacing: "0.08em",
        fontSize: "11px",
        textTransform: "uppercase",
      }}
    >
      {label}
      {count !== undefined && (
        <span style={{ opacity: 0.55, marginLeft: "var(--step)" }}>{count}</span>
      )}
    </button>
  );
}

export function FamilyRail({
  families, subfamilies, selectedFamily, selectedSubfamily,
  onSelectFamily, onSelectSubfamily,
}: Props) {
  return (
    <nav style={{ borderBottom: "1px solid var(--rule)" }}>
      <div style={{
        display: "flex", gap: "var(--step)", overflowX: "auto",
        padding: "var(--step) var(--gutter)", scrollbarWidth: "none",
      }}>
        <Chip label="tudo" active={selectedFamily === null}
              onClick={() => { onSelectFamily(null); onSelectSubfamily(null); }} />
        {families.map((f) => (
          <Chip key={f.family} label={f.family} count={f.count}
                active={f.family === selectedFamily}
                onClick={() => { onSelectFamily(f.family); onSelectSubfamily(null); }} />
        ))}
      </div>

      {selectedFamily && subfamilies.length > 0 && (
        <div style={{
          display: "flex", gap: "var(--step)", overflowX: "auto",
          padding: "0 var(--gutter) var(--step)", scrollbarWidth: "none",
          borderTop: "1px solid var(--rule)",
        }}>
          <Chip label="toda a familia" active={selectedSubfamily === null}
                onClick={() => onSelectSubfamily(null)} />
          {subfamilies.filter((s) => s.subfamily !== "").map((s) => (
            <Chip key={s.subfamily} label={s.subfamily} count={s.count}
                  active={s.subfamily === selectedSubfamily}
                  onClick={() => onSelectSubfamily(s.subfamily)} />
          ))}
        </div>
      )}
    </nav>
  );
}
