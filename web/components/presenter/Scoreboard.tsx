import { VerdictIcon } from "@/components/Verdict";
import { formatCost } from "@/lib/kiche";
import type { ContenderName, PresenterState, VerdictName } from "@/lib/types";

const VERDICTS: VerdictName[] = ["correcta", "aceptable", "incorrecta"];
const NAMES: ContenderName[] = ["david", "goliath"];

export function Scoreboard({ state }: { state: PresenterState }) {
  return (
    <div className="scoreboard" role="table" aria-label="Marcador: chrF++ medio en rondas de evaluación, veredictos en rondas en vivo, costo acumulado">
      {NAMES.map((name) => {
        const line = state.scoreboard[name];
        return (
          <div key={name} role="row" style={{ display: "contents" }}>
            <span role="cell" className={`scoreboard__name scoreboard__name--${name}`}>{name === "david" ? "David" : "Goliath"}</span>
            <span role="cell" className="scoreboard__chrf">
              <span className="scoreboard__label">chrF++</span>
              {line.chrf_mean == null ? "—" : line.chrf_mean.toLocaleString("es-GT", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
            </span>
            <span role="cell" className="scoreboard__verdicts">
              {VERDICTS.map((v) => (
                <span key={v} className={`v-${v}`} title={v}>
                  <VerdictIcon verdict={v} />
                  <span className="visually-hidden">{v}:</span>
                  {line.verdicts[v]}
                </span>
              ))}
            </span>
            <span role="cell" className="scoreboard__cost"><span className="scoreboard__label">costo</span>{formatCost(line.cost_usd)}</span>
          </div>
        );
      })}
    </div>
  );
}
