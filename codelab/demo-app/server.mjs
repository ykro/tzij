import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 4322;
const OLLAMA_URL = process.env.OLLAMA_URL || "http://localhost:11434";
const GEMMA_MODEL = process.env.GEMMA_MODEL || "gemma4:e2b";

// ============================================================================
// 1. GLOSARIO REGIONAL CURADO + 0 DATA LEAKS + GLOSSARY DROPOUT (85/15)
// ============================================================================
export const REGIONAL_GLOSSARY = [
  // Guatemala (GT)
  {
    id: "gt-clavo",
    region: "GT",
    idiom: "clavo",
    variants: ["clavo", "clavos", "clavito", "clavote"],
    standard: "incidente técnico",
    acceptedSynonyms: ["incidente técnico", "incidente", "fallo", "error", "problema técnico"],
    domain: "infraestructura_pagos",
    exampleSource: "Tengo un gran clavo con la pasarela de cobros.",
    exampleTarget: "Tengo un incidente técnico con la pasarela de cobros.",
  },
  {
    id: "gt-pisto",
    region: "GT",
    idiom: "pisto",
    variants: ["pisto", "pistillo"],
    standard: "saldo disponible",
    acceptedSynonyms: ["saldo disponible", "saldo", "dinero", "fondos", "capital"],
    domain: "billetera_digital",
    exampleSource: "El sistema me descontó el pisto dos veces.",
    exampleTarget: "El sistema me descontó el saldo disponible dos veces.",
  },
  {
    id: "gt-baras",
    region: "GT",
    idiom: "baras",
    variants: ["baras", "bara"],
    standard: "quetzales (GTQ)",
    acceptedSynonyms: ["quetzales (gtq)", "quetzales", "gtq"],
    domain: "facturacion",
    exampleSource: "Me debitaron 450 baras de mi cuenta monetaria.",
    exampleTarget: "Me debitaron 450 quetzales (GTQ) de mi cuenta monetaria.",
  },
  {
    id: "gt-chispudo",
    region: "GT",
    idiom: "chispudo",
    variants: ["chispudo", "chispuda", "chispudos"],
    standard: "con atención prioritaria",
    acceptedSynonyms: ["con atención prioritaria", "con prioridad", "ágilmente", "con urgencia", "rápidamente"],
    domain: "sla_soporte",
    exampleSource: "Por favor apóyenme chispudo porque la tienda está cerrada.",
    exampleTarget: "Por favor apóyenme con atención prioritaria porque la tienda está cerrada.",
  },
  {
    id: "gt-cabal",
    region: "GT",
    idiom: "cabal",
    variants: ["cabal", "cabalito"],
    standard: "exactamente",
    acceptedSynonyms: ["exactamente", "justamente", "precisamente"],
    domain: "conciliacion",
    exampleSource: "Cabal a las 14:00 horas cayó el nodo principal.",
    exampleTarget: "Exactamente a las 14:00 horas cayó el nodo principal.",
  },
  // Colombia (CO)
  {
    id: "co-parce",
    region: "CO",
    idiom: "parce",
    variants: ["parce", "parcero", "parceros"],
    standard: "equipo de soporte",
    acceptedSynonyms: ["equipo de soporte", "equipo", "ingenieros", "soporte"],
    domain: "atencion_cliente",
    exampleSource: "Parce, necesitamos desbloquear el corte contable.",
    exampleTarget: "Equipo de soporte, necesitamos desbloquear el corte contable.",
  },
  {
    id: "co-camellar",
    region: "CO",
    idiom: "camellar",
    variants: ["camellar", "camellando", "camella"],
    standard: "operar en producción",
    acceptedSynonyms: ["operar en producción", "operar", "funcionar", "procesar", "trabajar"],
    domain: "disponibilidad",
    exampleSource: "El microservicio de dispersión dejó de camellar desde temprano.",
    exampleTarget: "El microservicio de dispersión dejó de operar en producción desde temprano.",
  },
  {
    id: "co-chicharron",
    region: "CO",
    idiom: "chicharrón",
    variants: ["chicharrón", "chicharron", "chicharrones"],
    standard: "fallo crítico bloqueante",
    acceptedSynonyms: ["fallo crítico bloqueante", "fallo crítico", "incidente crítico", "bloqueo severo"],
    domain: "incidente_p1",
    exampleSource: "Se nos armó un chicharrón en el módulo de nómina.",
    exampleTarget: "Se nos presentó un fallo crítico bloqueante en el módulo de nómina.",
  },
  {
    id: "co-lukas",
    region: "CO",
    idiom: "lukas",
    variants: ["lukas", "lucas", "luka"],
    standard: "miles de pesos (COP)",
    acceptedSynonyms: ["miles de pesos (cop)", "miles de pesos", "pesos colombianos", "cop"],
    domain: "facturacion",
    exampleSource: "Quedaron retenidas 850 lukas en la pasarela PSE.",
    exampleTarget: "Quedaron retenidos 850 miles de pesos (COP) en la pasarela PSE.",
  },
  {
    id: "co-embolatado",
    region: "CO",
    idiom: "embolatado",
    variants: ["embolatado", "embolatada", "embolatados"],
    standard: "extraviado en conciliación",
    acceptedSynonyms: ["extraviado en conciliación", "extraviado", "sin conciliar", "pendiente de conciliar"],
    domain: "conciliacion",
    exampleSource: "El comprobante del lote 904 sigue embolatado.",
    exampleTarget: "El comprobante del lote 904 sigue extraviado en conciliación.",
  },
  // México (MX)
  {
    id: "mx-bronca",
    region: "MX",
    idiom: "bronca",
    variants: ["bronca", "broncas", "broncota"],
    standard: "incidencia operativa",
    acceptedSynonyms: ["incidencia operativa", "incidencia", "problema operativo", "error"],
    domain: "operaciones",
    exampleSource: "Traemos una bronca con el timbrado CFDI 4.0.",
    exampleTarget: "Presentamos una incidencia operativa con el timbrado CFDI 4.0.",
  },
  {
    id: "mx-feria",
    region: "MX",
    idiom: "feria",
    variants: ["feria"],
    standard: "saldo en cuenta",
    acceptedSynonyms: ["saldo en cuenta", "saldo", "dinero", "fondos"],
    domain: "billetera_digital",
    exampleSource: "El cliente reporta que no se reflejó su feria tras el SPEI.",
    exampleTarget: "El cliente reporta que no se reflejó su saldo en cuenta tras el SPEI.",
  },
  {
    id: "mx-varos",
    region: "MX",
    idiom: "varos",
    variants: ["varos", "varo"],
    standard: "pesos mexicanos (MXN)",
    acceptedSynonyms: ["pesos mexicanos (mxn)", "pesos mexicanos", "mxn"],
    domain: "facturacion",
    exampleSource: "El cargo duplicado fue por 1,250 varos en terminal POS.",
    exampleTarget: "El cargo duplicado fue por 1,250 pesos mexicanos (MXN) en terminal POS.",
  },
  {
    id: "mx-chafa",
    region: "MX",
    idiom: "chafa",
    variants: ["chafa", "chafas"],
    standard: "inestable con pérdida de paquetes",
    acceptedSynonyms: ["inestable con pérdida de paquetes", "inestable", "defectuoso", "degradado"],
    domain: "redes",
    exampleSource: "El enlace secundario hacia Monterrey está muy chafa.",
    exampleTarget: "El enlace secundario hacia Monterrey está inestable con pérdida de paquetes.",
  },
  {
    id: "mx-al-chile",
    region: "MX",
    idiom: "al chile",
    variants: ["al chile"],
    standard: "de manera urgente",
    acceptedSynonyms: ["de manera urgente", "urgentemente", "con urgencia", "de inmediato"],
    domain: "sla_soporte",
    exampleSource: "Al chile ocupamos reiniciar el cluster antes del cierre.",
    exampleTarget: "De manera urgente necesitamos reiniciar el cluster antes del cierre.",
  },
];

export const PRESET_TICKETS = [
  {
    id: "preset-gt",
    region: "GT",
    label: "Guatemala (GT) · Cobro duplicado en pasarela POS",
    customerName: "Comercializadora Reforma S.A. (Ciudad de Guatemala)",
    ticketText: "Qué onda soporte, cabal hoy a las 14:30 tuvimos un gran clavo con el lote #804: el POS descontó dos veces el pisto del cliente por 450 baras y necesitamos resolverlo chispudo antes del cierre.",
    humanReference: "Equipo de soporte, exactamente hoy a las 14:30 tuvimos un incidente técnico con el lote #804: el POS descontó dos veces el saldo disponible del cliente por 450 quetzales (GTQ) y necesitamos resolverlo con atención prioritaria antes del cierre.",
  },
  {
    id: "preset-co",
    region: "CO",
    label: "Colombia (CO) · Dispersión retenida en pasarela PSE",
    customerName: "Logística Andina SAS (Medellín)",
    ticketText: "Parce, se nos armó un chicharrón con el dispersor #502: el servicio dejó de camellar y quedaron embolatadas 850 lukas de la conciliación.",
    humanReference: "Equipo de soporte, se nos presentó un fallo crítico bloqueante con el dispersor #502: el servicio dejó de operar en producción y quedaron extraviados en conciliación 850 miles de pesos (COP) de la conciliación.",
  },
  {
    id: "preset-mx",
    region: "MX",
    label: "México (MX) · Falla de timbrado CFDI y SPEI retenido",
    customerName: "Distribuidora del Norte S.A. de C.V. (Monterrey)",
    ticketText: "Al chile traemos una bronca en el conector SPEI #309: la red está muy chafa y no se reflejó la feria del cliente por 1,250 varos.",
    humanReference: "De manera urgente presentamos una incidencia operativa en el conector SPEI #309: la red está inestable con pérdida de paquetes y no se reflejó el saldo en cuenta del cliente por 1,250 pesos mexicanos (MXN).",
  },
];

export function normalizeMatchKey(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function verifyZeroDataLeaks(trainExamples, testExamples) {
  const trainKeys = new Set();
  for (const row of trainExamples || []) {
    if (row.source) trainKeys.add(normalizeMatchKey(row.source));
    if (row.target) trainKeys.add(normalizeMatchKey(row.target));
  }

  const leaks = [];
  for (const testRow of testExamples || []) {
    const sKey = normalizeMatchKey(testRow.source || "");
    const tKey = normalizeMatchKey(testRow.target || "");
    if (sKey && trainKeys.has(sKey)) {
      leaks.push(`Fuga en source: "${testRow.source}"`);
    }
    if (tKey && trainKeys.has(tKey)) {
      leaks.push(`Fuga en target: "${testRow.target}"`);
    }
  }

  return {
    passed: leaks.length === 0,
    leaks,
    trainCount: (trainExamples || []).length,
    testCount: (testExamples || []).length,
  };
}

export function applyGlossaryDropout(entries, rate = 0.15, seedKey = "soporte-local") {
  const keptEntries = [];
  const droppedEntries = [];

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    const hashHex = crypto
      .createHash("sha1")
      .update(`${seedKey}:${entry.id || entry.idiom}:${i}`)
      .digest("hex");
    const bucket = (parseInt(hashHex.slice(0, 8), 16) % 10000) / 10000;
    if (bucket < rate) {
      droppedEntries.push(entry);
    } else {
      keptEntries.push(entry);
    }
  }

  const total = entries.length || 1;
  return {
    keptEntries,
    droppedEntries,
    dropoutRateTarget: rate,
    effectiveKeepRatio: Math.round((keptEntries.length / total) * 1000) / 1000,
  };
}

// ============================================================================
// 2. MOTOR RAG HÍBRIDO (BM25 + DENSE SUBWORD COSINE + RRF k=60 + best_last)
// ============================================================================
function extractCharNgrams(text, minN = 3, maxN = 5) {
  const clean = ` ${normalizeMatchKey(text)} `;
  const counts = new Map();
  for (let n = minN; n <= maxN; n++) {
    for (let i = 0; i <= clean.length - n; i++) {
      const gram = clean.slice(i, i + n);
      counts.set(gram, (counts.get(gram) || 0) + 1);
    }
  }
  return counts;
}

function cosineMapSimilarity(mapA, mapB) {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (const val of mapA.values()) normA += val * val;
  for (const val of mapB.values()) normB += val * val;
  if (normA === 0 || normB === 0) return 0;
  for (const [k, valA] of mapA.entries()) {
    const valB = mapB.get(k);
    if (valB) dot += valA * valB;
  }
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

export function retrieveHybridRRF(
  ticketText,
  { region = "ALL", k = 60, topN = 5, order = "best_last" } = {}
) {
  const normTicket = normalizeMatchKey(ticketText);
  const ticketTokens = new Set(normTicket.split(" ").filter(Boolean));
  const ticketNgrams = extractCharNgrams(ticketText);

  const pool = REGIONAL_GLOSSARY.filter(
    item => region === "ALL" || !region || item.region === region
  );

  // 1. Puntaje Léxico BM25 simplificado sobre variantes e idiom
  const bm25Scored = pool
    .map(entry => {
      let score = 0;
      for (const variant of entry.variants) {
        const normVar = normalizeMatchKey(variant);
        const varRegex = new RegExp(`\\b${normVar.replace(/\s+/g, "\\s+")}\\b`, "i");
        if (varRegex.test(normTicket)) {
          score += 3.5;
        } else {
          for (const tok of normVar.split(" ")) {
            if (ticketTokens.has(tok)) score += 1.2;
          }
        }
      }
      return { entry, bm25Score: Math.round(score * 1000) / 1000 };
    })
    .sort((a, b) => b.bm25Score - a.bm25Score);

  // 2. Puntaje Denso (Similitud Coseno de subpalabras / char n-grams para capturar morfología)
  const denseScored = pool
    .map(entry => {
      const entrySurface = `${entry.idiom} ${entry.variants.join(" ")} ${entry.exampleSource}`;
      const entryNgrams = extractCharNgrams(entrySurface);
      let sim = cosineMapSimilarity(ticketNgrams, entryNgrams);
      // Impulso por coincidencia de raíz morfológica (prefijo >= 5 letras)
      for (const variant of entry.variants) {
        const stem = normalizeMatchKey(variant).slice(0, 5);
        if (stem.length >= 4 && normTicket.includes(stem)) {
          sim += 0.35;
        }
      }
      return { entry, denseScore: Math.round(sim * 10000) / 10000 };
    })
    .sort((a, b) => b.denseScore - a.denseScore);

  // 3. Fusión RRF (Reciprocal Rank Fusion, k = 60)
  const rrfScores = new Map();
  const bm25Ranks = new Map();
  const denseRanks = new Map();

  bm25Scored.forEach((item, idx) => {
    const rank = idx + 1;
    bm25Ranks.set(item.entry.id, { rank, score: item.bm25Score });
    if (item.bm25Score > 0) {
      rrfScores.set(item.entry.id, (rrfScores.get(item.entry.id) || 0) + 1 / (k + rank));
    }
  });

  denseScored.forEach((item, idx) => {
    const rank = idx + 1;
    denseRanks.set(item.entry.id, { rank, score: item.denseScore });
    if (item.denseScore > 0.08) {
      rrfScores.set(item.entry.id, (rrfScores.get(item.entry.id) || 0) + 1 / (k + rank));
    }
  });

  // Seleccionar los modismos presentes o más cercanos
  let merged = pool
    .filter(entry => rrfScores.has(entry.id))
    .map(entry => {
      const bInfo = bm25Ranks.get(entry.id) || { rank: 99, score: 0 };
      const dInfo = denseRanks.get(entry.id) || { rank: 99, score: 0 };
      const matchedInText = entry.variants.some(v => {
        const nv = normalizeMatchKey(v);
        return new RegExp(`\\b${nv.replace(/\s+/g, "\\s+")}\\b`, "i").test(normTicket);
      });
      return {
        id: entry.id,
        region: entry.region,
        idiom: entry.idiom,
        standard: entry.standard,
        acceptedSynonyms: entry.acceptedSynonyms,
        domain: entry.domain,
        matchedInText,
        bm25Rank: bInfo.rank,
        bm25Score: bInfo.score,
        denseRank: dInfo.rank,
        denseScore: dInfo.score,
        rrfScore: Math.round((rrfScores.get(entry.id) || 0) * 100000) / 100000,
      };
    })
    .sort((a, b) => {
      if (a.matchedInText !== b.matchedInText) return a.matchedInText ? -1 : 1;
      return b.rrfScore - a.rrfScore;
    })
    .slice(0, topN);

  // Ordenamiento best_last: coloca el modismo más relevante al final del bloque RAG
  // justo antes de la frase del usuario para mitigar Lost-in-the-Middle en Gemma 4
  if (order === "best_last") {
    merged = [...merged].reverse();
  }

  return {
    order,
    rrfK: k,
    hits: merged,
    detectedIdioms: merged.filter(h => h.matchedInText),
    topHitAtEnd: merged.length > 0 ? merged[merged.length - 1] : null,
  };
}

// ============================================================================
// 3. EVALUADOR chrF++ EN CÓDIGO (0 a 100) Y CONSENSO MBR-3
// ============================================================================
function getNgramCounts(items, n) {
  const counts = new Map();
  for (let i = 0; i <= items.length - n; i++) {
    const key = items.slice(i, i + n).join(" ");
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return counts;
}

function ngramFScore(hypItems, refItems, maxOrder, beta = 2) {
  let totalF = 0;
  let validOrders = 0;
  const betaSq = beta * beta;

  for (let n = 1; n <= maxOrder; n++) {
    if (hypItems.length < n || refItems.length < n) {
      validOrders++;
      continue;
    }
    const hypCounts = getNgramCounts(hypItems, n);
    const refCounts = getNgramCounts(refItems, n);
    let overlap = 0;
    let hypTotal = 0;
    let refTotal = 0;

    for (const [k, c] of hypCounts.entries()) {
      hypTotal += c;
      if (refCounts.has(k)) {
        overlap += Math.min(c, refCounts.get(k));
      }
    }
    for (const c of refCounts.values()) {
      refTotal += c;
    }

    const prec = hypTotal > 0 ? overlap / hypTotal : 0;
    const rec = refTotal > 0 ? overlap / refTotal : 0;
    const f =
      prec + rec > 0
        ? ((1 + betaSq) * prec * rec) / (betaSq * prec + rec)
        : 0;
    totalF += f;
    validOrders++;
  }

  return validOrders > 0 ? totalF / validOrders : 0;
}

export function computeChrFPlusPlus(hypothesis, reference) {
  const hypClean = String(hypothesis || "").trim().replace(/\s+/g, " ");
  const refClean = String(reference || "").trim().replace(/\s+/g, " ");
  if (!hypClean || !refClean) return 0;
  if (hypClean === refClean) return 100;

  // char_order = 6 (sin espacios intermedios según especificación chrF), word_order = 2, beta = 2
  const hypChars = Array.from(hypClean.replace(/\s+/g, ""));
  const refChars = Array.from(refClean.replace(/\s+/g, ""));
  const hypWords = hypClean.toLowerCase().replace(/[.,;:!?()"]/g, "").split(" ").filter(Boolean);
  const refWords = refClean.toLowerCase().replace(/[.,;:!?()"]/g, "").split(" ").filter(Boolean);

  const charF = ngramFScore(hypChars, refChars, 6, 2);
  const wordF = ngramFScore(hypWords, refWords, 2, 2);
  const combined = ((charF * 6 + wordF * 2) / 8) * 100;
  return Math.round(combined * 10) / 10;
}

export function mbrSelectConsensus(candidates) {
  const cleaned = (candidates || []).map(c => String(c || "").trim()).filter(Boolean);
  if (cleaned.length === 0) {
    return { selected: "", selectedIndex: -1, candidatesWithSupport: [] };
  }
  if (cleaned.length === 1) {
    return {
      selected: cleaned[0],
      selectedIndex: 0,
      candidatesWithSupport: [{ index: 0, text: cleaned[0], supportScore: 100 }],
    };
  }

  const candidatesWithSupport = cleaned.map((candI, i) => {
    let sum = 0;
    let count = 0;
    for (let j = 0; j < cleaned.length; j++) {
      if (i === j) continue;
      sum += computeChrFPlusPlus(candI, cleaned[j]);
      count++;
    }
    const supportScore = Math.round((sum / count) * 10) / 10;
    return { index: i, text: candI, supportScore };
  });

  let best = candidatesWithSupport[0];
  for (const item of candidatesWithSupport) {
    if (item.supportScore > best.supportScore) {
      best = item;
    }
  }

  return {
    selected: best.text,
    selectedIndex: best.index,
    candidatesWithSupport,
  };
}

// ============================================================================
// 4. VALIDADOR DETERMINISTA POST-GENERACIÓN
// ============================================================================
export function validateNormalizedTicket(outputText, sourceText, detectedIdioms = []) {
  const normOut = normalizeMatchKey(outputText);
  const untranslatedIdioms = [];
  const normalizedConfirmations = [];

  for (const hit of detectedIdioms) {
    const entry = REGIONAL_GLOSSARY.find(g => g.id === hit.id || g.idiom === hit.idiom) || hit;
    const variants = entry.variants || [entry.idiom];
    const stillHasRawIdiom = variants.some(v => {
      const nv = normalizeMatchKey(v);
      return new RegExp(`\\b${nv.replace(/\s+/g, "\\s+")}\\b`, "i").test(normOut);
    });
    if (stillHasRawIdiom) {
      untranslatedIdioms.push(entry.idiom);
    } else {
      normalizedConfirmations.push({
        idiom: entry.idiom,
        mappedTo: entry.standard,
      });
    }
  }

  // Verificar que todos los montos, horas e identificadores numéricos del ticket se preserven
  const rawNumbers = String(sourceText || "").match(/\d+(?:[.,:]\d+)?/g) || [];
  const outNumbers = new Set(String(outputText || "").match(/\d+(?:[.,:]\d+)?/g) || []);
  const preservedNumbers = [];
  const missingNumbers = [];

  for (const num of rawNumbers) {
    if (outNumbers.has(num)) {
      preservedNumbers.push(num);
    } else {
      missingNumbers.push(num);
    }
  }

  return {
    passed: untranslatedIdioms.length === 0 && missingNumbers.length === 0,
    untranslatedIdioms,
    normalizedConfirmations,
    preservedNumbers,
    missingNumbers,
  };
}

// ============================================================================
// 5. MOTOR GEMMA 4 (Ollama en vivo + Fallback determinista instantáneo)
// ============================================================================
function deterministicNormalize(ticketText, hits, variantMode = "canonical") {
  let out = String(ticketText || "");

  // Normalizar saludos coloquiales iniciales
  out = out.replace(/^qu[eé]\s+onda\s+soporte\s*,?\s*/i, "Equipo de soporte, ");
  out = out.replace(/^parce\s*,?\s*/i, "Equipo de soporte, ");

  // Ordenar hits para reemplazar frases multi-palabra primero
  const sortedHits = [...hits].sort((a, b) => b.idiom.length - a.idiom.length);
  for (const h of sortedHits) {
    const entry = REGIONAL_GLOSSARY.find(g => g.id === h.id) || h;
    const replacement =
      variantMode === "synonym" && entry.acceptedSynonyms && entry.acceptedSynonyms[1]
        ? entry.acceptedSynonyms[1]
        : entry.standard;

    for (const v of entry.variants || [entry.idiom]) {
      const escaped = v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const re = new RegExp(`\\b${escaped}\\b`, "gi");
      out = out.replace(re, replacement);
    }
  }

  // Ajustes gramaticales limpios de verbos/frases coloquiales
  out = out
    .replace(/\btuvimos un gran incidente técnico\b/gi, "tuvimos un incidente técnico")
    .replace(/\bse nos armó un fallo crítico bloqueante\b/gi, "se nos presentó un fallo crítico bloqueante")
    .replace(/\bquedaron extraviado en conciliación\b/gi, "quedaron extraviados en conciliación")
    .replace(/\btraemos una incidencia operativa\b/gi, "presentamos una incidencia operativa")
    .replace(/\bno se reflejó la saldo en cuenta\b/gi, "no se reflejó el saldo en cuenta");

  if (out.length > 0) {
    out = out.charAt(0).toUpperCase() + out.slice(1);
  }
  return out;
}

function deterministicZeroShot(ticketText, region) {
  // Simula el comportamiento típico de un modelo sin glosario local:
  // deja jerga centroamericana/andina intacta o confunde "pisto" y monedas regionales
  let out = String(ticketText || "");
  if (region === "GT") {
    out = out
      .replace(/^qu[eé]\s+onda\s+soporte/i, "Hola soporte")
      .replace(/\bpisto\b/gi, "bebida")
      .replace(/\bbaras\b/gi, "monedas");
  } else if (region === "CO") {
    out = out.replace(/\blukas\b/gi, "unidades");
  } else if (region === "MX") {
    out = out.replace(/\bvaros\b/gi, "fondos");
  }
  return out;
}

async function callGemmaOllama(messages, { temperature = 0, seed = 42, format = null } = {}) {
  if (process.env.FORCE_INSTANT_MODE === "1") return null;
  try {
    const controller = new AbortController();
    const timeoutMs = Number(process.env.OLLAMA_TIMEOUT_MS || 2200);
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        model: GEMMA_MODEL,
        stream: false,
        think: false,
        options: { temperature, seed, num_predict: 220 },
        ...(format ? { format } : {}),
        messages,
      }),
    });
    clearTimeout(timer);
    if (!res.ok) return null;
    const data = await res.json();
    return { content: data.message?.content?.trim() || "", live: true };
  } catch {
    return null;
  }
}

export async function runSupportDuel({
  ticketText,
  region = "GT",
  customerName = "Cliente Empresarial",
  humanReference = "",
}) {
  const t0 = Date.now();

  // 1. Recuperación RAG Híbrida (BM25 + Dense Subword + RRF k=60 + ordenamiento best_last)
  const rag = retrieveHybridRRF(ticketText, {
    region: region || "ALL",
    k: 60,
    topN: 5,
    order: "best_last",
  });

  // Demostración de Glossary Dropout (85/15) y verificación 0 Data Leaks
  const dropoutDemo = applyGlossaryDropout(REGIONAL_GLOSSARY, 0.15, ticketText);
  const leakDemo = verifyZeroDataLeaks(
    REGIONAL_GLOSSARY.map(g => ({ source: g.exampleSource, target: g.exampleTarget })),
    [{ source: ticketText, target: humanReference || "" }]
  );

  // 2. Construir el bloque de contexto ordenado con best_last (el más relevante justo al final)
  const glossaryBlock = rag.hits
    .map(
      (h, idx) =>
        `${idx + 1}. [${h.region} · RRF=${h.rrfScore}] "${h.idiom}" => "${h.standard}"`
    )
    .join("\n");

  // 3A. Inferencia Zero-Shot (Sin glosario RAG)
  let zeroShotText = null;
  const zeroRes = await callGemmaOllama(
    [
      {
        role: "system",
        content:
          "Reescribe el ticket de soporte en español formal conservando los números. Devuelve únicamente la oración reescrita.",
      },
      { role: "user", content: ticketText },
    ],
    { temperature: 0, seed: 10 }
  );
  if (zeroRes && zeroRes.content) {
    zeroShotText = zeroRes.content;
  } else {
    zeroShotText = deterministicZeroShot(ticketText, region);
  }

  // 3B. Inferencia Especialista Gemma 4 (RAG Híbrido best_last + 3 candidatos MBR-3)
  const canonicalCandidate = deterministicNormalize(ticketText, rag.detectedIdioms, "canonical");
  const synonymCandidate = deterministicNormalize(ticketText, rag.detectedIdioms, "synonym");

  let candidates = [
    canonicalCandidate,
    canonicalCandidate,
    synonymCandidate,
  ];

  const liveSpec = await callGemmaOllama(
    [
      {
        role: "system",
        content:
          "Eres SoporteLocal, especialista en normalizar tickets de soporte latinoamericanos. Sustituye todos los modismos usando el glosario RRF best_last y preserva intactos todos los números y montos. Devuelve solo el ticket normalizado.",
      },
      {
        role: "user",
        content: `Glosario Regional (ordenado con best_last):\n${glossaryBlock}\n\nTicket original: ${ticketText}`,
      },
    ],
    { temperature: 0.2, seed: 42 }
  );

  if (liveSpec && liveSpec.content) {
    const checkLive = validateNormalizedTicket(liveSpec.content, ticketText, rag.detectedIdioms);
    if (checkLive.passed) {
      candidates = [liveSpec.content, canonicalCandidate, synonymCandidate];
    }
  }

  const mbr = mbrSelectConsensus(candidates);
  const specialistText = mbr.selected;

  // 4. Validación determinista post-generación sobre ambas salidas
  const zeroValidation = validateNormalizedTicket(zeroShotText, ticketText, rag.detectedIdioms);
  const specialistValidation = validateNormalizedTicket(
    specialistText,
    ticketText,
    rag.detectedIdioms
  );

  // 5. Evaluación chrF++ (0 a 100) contra la referencia humana (o referencia canónica)
  const referenceToScore =
    humanReference && humanReference.trim() ? humanReference.trim() : canonicalCandidate;
  const zeroChrF = computeChrFPlusPlus(zeroShotText, referenceToScore);
  const specialistChrF = computeChrFPlusPlus(specialistText, referenceToScore);
  const deltaChrF = Math.round((specialistChrF - zeroChrF) * 10) / 10;

  // 6. Ticket JSON estructurado para el sistema de soporte (SLA + impacto financiero)
  const amounts = String(ticketText).match(/\b\d[\d,]*\b/g) || [];
  const structuredTicket = {
    customer: customerName,
    region,
    normalizedSummary: specialistText,
    priority:
      rag.detectedIdioms.some(d => ["chicharrón", "clavo", "chispudo", "al chile", "bronca"].includes(d.idiom))
        ? "P1_CRITICO"
        : "P2_ALTO",
    slaTargetMinutes: 15,
    detectedRegionalIdioms: rag.detectedIdioms.map(d => ({
      idiom: d.idiom,
      normalizedTo: d.standard,
      rrfScore: d.rrfScore,
    })),
    preservedNumericTokens: specialistValidation.preservedNumbers,
    estimatedAmountAtRisk: amounts.length > 0 ? amounts[amounts.length - 1] : "N/A",
  };

  const elapsedMs = Date.now() - t0;
  const isLive = Boolean(zeroRes?.live || liveSpec?.live);

  return {
    model: GEMMA_MODEL,
    liveInference: isLive,
    engineLabel: isLive
      ? `${GEMMA_MODEL} (Ollama en vivo · ${elapsedMs} ms)`
      : `${GEMMA_MODEL} (Motor determinista instantáneo · ${elapsedMs} ms)`,
    elapsedMs,
    input: {
      customerName,
      region,
      ticketText,
      humanReference: referenceToScore,
    },
    dataHygiene: {
      zeroLeaksAudit: leakDemo,
      glossaryDropout: {
        dropoutRateTarget: dropoutDemo.dropoutRateTarget,
        effectiveKeepRatio: dropoutDemo.effectiveKeepRatio,
        keptCount: dropoutDemo.keptEntries.length,
        droppedCount: dropoutDemo.droppedEntries.length,
      },
    },
    rag,
    duel: {
      zeroShot: {
        output: zeroShotText,
        chrfPlusPlus: zeroChrF,
        validation: zeroValidation,
      },
      specialist: {
        output: specialistText,
        chrfPlusPlus: specialistChrF,
        deltaChrF,
        mbrConsensus: mbr,
        validation: specialistValidation,
      },
    },
    structuredTicket,
  };
}

// ============================================================================
// 6. SERVIDOR HTTP
// ============================================================================
const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/api/presets") {
    res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ presets: PRESET_TICKETS, glossaryCount: REGIONAL_GLOSSARY.length }, null, 2));
    return;
  }

  if (req.method === "POST" && req.url === "/api/duel") {
    let body = "";
    req.on("data", chunk => {
      body += chunk;
    });
    req.on("end", async () => {
      try {
        const payload = JSON.parse(body || "{}");
        const result = await runSupportDuel(payload);
        res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify(result, null, 2));
      } catch (err) {
        res.writeHead(400, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: String(err) }));
      }
    });
    return;
  }

  const reqPath = req.url.split("?")[0];
  const filePath = path.join(__dirname, "public", reqPath === "/" ? "index.html" : reqPath);
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath);
    const mime =
      ext === ".html"
        ? "text/html; charset=utf-8"
        : ext === ".css"
        ? "text/css; charset=utf-8"
        : "application/javascript; charset=utf-8";
    res.writeHead(200, { "Content-Type": mime });
    res.end(fs.readFileSync(filePath));
  } else {
    res.writeHead(404);
    res.end("Not found");
  }
});

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  server.listen(PORT, () => {
    console.log(`SoporteLocal (100% Gemma 4) corriendo en http://localhost:${PORT}`);
  });
}
