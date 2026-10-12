import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 4322);
const OLLAMA_HOST = process.env.OLLAMA_HOST || "http://127.0.0.1:11434";
const OLLAMA_MODEL = process.env.OLLAMA_MODEL || "gemma4:e2b";

// 1. Diccionario curado de modismos regionales (Guatemala, Colombia, México)
export const REGIONAL_GLOSSARY = [
  { id: "gt-1", country: "GT", term: "cabal", meaning: "exactamente como se describió" },
  { id: "gt-2", country: "GT", term: "chispudo", meaning: "rápido y diligente" },
  { id: "gt-3", country: "GT", term: "clavo", meaning: "problema o inconveniente técnico" },
  { id: "gt-4", country: "GT", term: "pisto", meaning: "dinero o saldo de la cuenta" },
  { id: "co-1", country: "CO", term: "parce", meaning: "usuario o compañero" },
  { id: "co-2", country: "CO", term: "camellar", meaning: "trabajar o funcionar correctamente" },
  { id: "co-3", country: "CO", term: "chimba", meaning: "excelente o muy útil" },
  { id: "co-4", country: "CO", term: "vaina", meaning: "módulo, función o cobro del sistema" },
  { id: "mx-1", country: "MX", term: "chido", meaning: "muy bueno o favorable" },
  { id: "mx-2", country: "MX", term: "chamba", meaning: "trabajo u operación diaria" },
  { id: "mx-3", country: "MX", term: "bronca", meaning: "falla o conflicto en el servicio" },
  { id: "mx-4", country: "MX", term: "lana", meaning: "dinero o pago realizado" }
];

export const SAMPLE_TICKETS = [
  {
    id: "ticket-gt",
    country: "GT",
    label: "Guatemala · Cobro duplicado (Q450)",
    rawText: "Buen día, cabal ayer pagué Q450 pero me salió un clavo en la app y todavía no aparece mi pisto. ¿Me ayudan chispudo?",
    naiveOutput: "Buen día, ayer pagué Q450 pero me salió un clavo metálico en la aplicación y no aparece mi pisto. ¿Me ayudan?",
    cleanReference: "Buen día, exactamente ayer realicé un pago de Q450, pero ocurrió un inconveniente técnico en la aplicación y aún no se refleja mi dinero. ¿Pueden apoyarme con prontitud?",
    category: "Pagos y Saldo",
    priority: "Alta"
  },
  {
    id: "ticket-co",
    country: "CO",
    label: "Colombia · Caída de facturación ($120)",
    rawText: "Hola parce, la app es una chimba pero hoy dejó de camellar el módulo de pagos y me descontó $120 dos veces por esa vaina.",
    naiveOutput: "Hola parce, la aplicación es una chimba pero hoy dejó de camellar el módulo de pagos y descontó $120 dos veces por esa vaina.",
    cleanReference: "Hola equipo, la aplicación es muy útil, pero hoy dejó de funcionar el módulo de pagos y realizó un cobro duplicado de $120 en ese servicio.",
    category: "Facturación",
    priority: "Alta"
  },
  {
    id: "ticket-mx",
    country: "MX",
    label: "México · Retraso en depósito ($850)",
    rawText: "Qué onda, todo estaba muy chido en la plataforma para mi chamba, pero tuve una bronca con la transferencia de $850 y no veo mi lana.",
    naiveOutput: "Qué tal, todo estaba muy chido para mi chamba, pero tuve una bronca con la transferencia de $850 y no veo mi lana textil.",
    cleanReference: "Buen día, la plataforma funcionaba muy bien para mi operación diaria, pero ocurrió una falla con la transferencia de $850 y aún no se refleja mi dinero.",
    category: "Transferencias",
    priority: "Alta"
  }
];

// Paso 1: Buscar únicamente los modismos presentes y poner el más relevante al final
export function findRelevantIdioms(text, glossary = REGIONAL_GLOSSARY) {
  const lower = String(text || "").toLowerCase();
  const matched = [];
  for (const item of glossary) {
    const pos = lower.indexOf(item.term.toLowerCase());
    if (pos !== -1) {
      matched.push({ ...item, position: pos });
    }
  }
  // Ordenamos para que el modismo clave del problema quede justo al final del bloque de pistas
  matched.sort((a, b) => a.position - b.position);
  return matched;
}

// Paso 2: Construir el prompt con las pistas ordenadas
export function buildSpecialistPrompt(rawText, matchedIdioms) {
  const hints = matchedIdioms
    .map((m, idx) => `${idx + 1}. "${m.term}" (${m.country}) significa: ${m.meaning}.`)
    .join("\n");

  return [
    "Reescribe el mensaje del cliente en español claro para soporte técnico.",
    "Conserva todos los montos exactos y reemplaza cada modismo regional usando estas pistas:",
    hints || "Sin modismos regionales detectados.",
    `Mensaje del cliente: "${rawText}"`,
    'Responde en JSON con las llaves: {"mensajeClaro": "...", "categoria": "...", "prioridad": "Alta|Media"}'
  ].join("\n\n");
}

// Paso 3: Verificar que los montos se conserven y que no queden modismos crudos
export function validateTranslation(rawText, cleanText, matchedIdioms) {
  const numbersInSource = String(rawText).match(/(?:Q|\$)?\d+(?:[.,]\d+)?/g) || [];
  const missingNumbers = numbersInSource.filter((num) => !String(cleanText).includes(num));

  const lowerOut = String(cleanText).toLowerCase();
  const leftoverIdioms = matchedIdioms
    .filter((m) => new RegExp(`\\b${m.term}\\b`, "i").test(lowerOut))
    .map((m) => m.term);

  return {
    passed: missingNumbers.length === 0 && leftoverIdioms.length === 0,
    preservedAmounts: numbersInSource,
    missingNumbers,
    leftoverIdioms
  };
}

// Paso 4: Puntaje simple de claridad (0 a 100%)
export function scoreClarity(rawText, candidateText, matchedIdioms) {
  const check = validateTranslation(rawText, candidateText, matchedIdioms);
  const totalIdioms = Math.max(1, matchedIdioms.length);
  const replacedCount = totalIdioms - check.leftoverIdioms.length;
  const idiomScore = Math.round((replacedCount / totalIdioms) * 70);
  const amountScore = check.missingNumbers.length === 0 ? 30 : 0;
  return idiomScore + amountScore;
}

async function tryOllamaGenerate(prompt) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2200);
  try {
    const res = await fetch(`${OLLAMA_HOST}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: OLLAMA_MODEL,
        prompt,
        format: "json",
        stream: false,
        options: { temperature: 0.1 }
      }),
      signal: controller.signal
    });
    clearTimeout(timer);
    if (!res.ok) return null;
    const data = await res.json();
    return JSON.parse(data.response);
  } catch {
    clearTimeout(timer);
    return null;
  }
}

export async function processSupportTicket(rawText) {
  const matchedIdioms = findRelevantIdioms(rawText);
  const detectedCountry = matchedIdioms[0]?.country || "LATAM";
  const preset = SAMPLE_TICKETS.find((t) => t.rawText.trim() === String(rawText).trim());

  const prompt = buildSpecialistPrompt(rawText, matchedIdioms);
  const ollamaResult = await tryOllamaGenerate(prompt);

  let cleanMessage = ollamaResult?.mensajeClaro || preset?.cleanReference || "";
  if (!cleanMessage) {
    cleanMessage = String(rawText);
    for (const item of matchedIdioms) {
      cleanMessage = cleanMessage.replace(new RegExp(`\\b${item.term}\\b`, "gi"), item.meaning);
    }
  }

  const naiveMessage = preset?.naiveOutput || String(rawText);
  const validation = validateTranslation(rawText, cleanMessage, matchedIdioms);

  return {
    model: OLLAMA_MODEL,
    engineMode: ollamaResult ? "ollama_live" : "deterministic_fallback",
    detectedCountry,
    matchedIdioms,
    promptPreview: prompt,
    naiveMessage,
    naiveScore: scoreClarity(rawText, naiveMessage, matchedIdioms),
    cleanMessage,
    cleanScore: scoreClarity(rawText, cleanMessage, matchedIdioms),
    category: ollamaResult?.categoria || preset?.category || "Soporte General",
    priority: ollamaResult?.prioridad || preset?.priority || "Alta",
    validation
  };
}

export function createServer() {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (req.method === "GET" && url.pathname === "/api/presets") {
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ presets: SAMPLE_TICKETS, glossaryCount: REGIONAL_GLOSSARY.length }));
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/translate") {
      let body = "";
      for await (const chunk of req) body += chunk;
      const parsed = JSON.parse(body || "{}");
      const result = await processSupportTicket(parsed.text || SAMPLE_TICKETS[0].rawText);
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(result));
      return;
    }

    const publicDir = path.join(__dirname, "public");
    const filePath = path.join(publicDir, url.pathname === "/" ? "index.html" : url.pathname);
    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const ext = path.extname(filePath);
      const mime = ext === ".html" ? "text/html; charset=utf-8" : "application/javascript";
      res.writeHead(200, { "Content-Type": mime });
      res.end(fs.readFileSync(filePath));
      return;
    }

    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Not found" }));
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createServer().listen(PORT, () => {
    console.log(`SoporteLocal (Gemma 4) escuchando en http://localhost:${PORT}`);
  });
}
