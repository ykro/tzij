import { formatCount, modelName } from "@/lib/kiche";
import type { ModelCard } from "@/lib/types";

export function ModelCardStrip({ card, onToggle, open }: { card: ModelCard; onToggle: () => void; open: boolean }) {
  return (
    <button type="button" className="card-strip" onClick={onToggle} aria-expanded={open} aria-controls="model-card">
      <span className="card-strip__item"><span>Fuentes</span><b className="num">{card.sources ?? "—"}</b></span>
      <span className="card-strip__item"><span>Pares</span><b className="num">{formatCount(card.pairs)}</b></span>
      <span className="card-strip__item"><span>Datos</span><b>{card.data_date ?? "sin datos"}</b></span>
    </button>
  );
}

export function ModelCardPanel({ card }: { card: ModelCard }) {
  return (
    <aside id="model-card" className="model-card fade-in" aria-label="Ficha del modelo">
      <h2>Ficha de David</h2>
      <dl>
        <dt>Modelo</dt>
        <dd>{modelName(card.david_model)} (Gemma), en Ollama, sin internet</dd>
        <dt>Conocimiento</dt>
        <dd>
          Índice de recuperación: {formatCount(card.index_entries)} entradas ({card.embedding_model ?? "EmbeddingGemma"})
        </dd>
        <dt>Datos</dt>
        <dd>
          {formatCount(card.pairs)} pares español–Kʼicheʼ de la web con licencia · versión {card.dataset_version ?? "—"}
        </dd>
        <dt>Fuentes de David</dt>
        <dd>
          <ul className="model-card__sources">{(card.train_sources ?? []).map((s) => <li key={s}>{s}</li>)}</ul>
        </dd>
        <dt>Prueba</dt>
        <dd>
          {formatCount(card.test_pairs)} pares de fuentes que David nunca vio: {(card.test_sources ?? []).join(" y ")}
        </dd>
        <dt>Goliath</dt>
        <dd>{modelName(card.goliath_model)}, en la nube, sin datos extra</dd>
      </dl>
      <p className="model-card__note">Sin datos sintéticos: nada de Kʼicheʼ generado por IA. Detalle en data/SOURCES.md y MODEL_CARD.md.</p>
    </aside>
  );
}
