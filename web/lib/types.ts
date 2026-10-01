// Shapes returned by the duel service (duel/tzij_duel/main.py).

export type Direction = "es-quc" | "quc-es";
export type RoundKind = "evaluacion" | "en_vivo";
export type VerdictName = "correcta" | "aceptable" | "incorrecta";
export type ContenderName = "david" | "goliath";

export interface ContenderResult {
  name: ContenderName;
  model: string;
  status: "ok" | "offline" | "error";
  text: string;
  latency_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  chrf: number | null;
  error: string | null;
}

export interface Round {
  id: string;
  number: number;
  kind: RoundKind;
  direction: Direction;
  source_text: string;
  reference: string | null;
  reference_meta: { source_name: string; url: string; license: string; status: string } | null;
  status: "translating" | "done";
  results: Partial<Record<ContenderName, ContenderResult>>;
  blind_order: ContenderName[];
  tallies: Record<ContenderName, Record<VerdictName, number>>;
  created_at: number;
}

export interface ScoreLine {
  cost_usd: number;
  chrf_mean: number | null;
  evaluation_rounds: number;
  verdicts: Record<VerdictName, number>;
}

export interface ModelCard {
  david_model: string | null;
  goliath_model: string | null;
  sources: number | null;
  source_names?: string[];
  train_sources?: string[];
  test_sources?: string[];
  pairs: number | null;
  test_pairs: number | null;
  data_date: string | null;
  dataset_version: string | null;
  index_entries: number | null;
  embedding_model?: string | null;
  finetune_threshold_met?: boolean;
}

export interface PresenterState {
  round: Round | null;
  scoreboard: Record<ContenderName, ScoreLine> & { evaluation_wins: Record<string, number> };
  online: boolean;
  force_offline: boolean;
  contenders: Record<ContenderName, { label: string; model: string; retrieval: boolean; local: boolean }>;
  model_card: ModelCard;
  validator_url: string;
  deck_size: number;
  mock: boolean;
  index_warning: string | null;
}

export interface BlindRound {
  id: string;
  number: number;
  kind: RoundKind;
  direction: Direction;
  source_text: string;
  status: "translating" | "done";
  translations: { slot: number; status: "ok" | "offline" | "error" | "translating"; text: string }[];
}
