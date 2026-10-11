import test from "node:test";
import assert from "node:assert/strict";
import {
  REGIONAL_GLOSSARY,
  PRESET_TICKETS,
  verifyZeroDataLeaks,
  applyGlossaryDropout,
  retrieveHybridRRF,
  computeChrFPlusPlus,
  mbrSelectConsensus,
  validateNormalizedTicket,
  runSupportDuel,
} from "./server.mjs";

test("1. verifyZeroDataLeaks y applyGlossaryDropout (85/15) protegen las particiones y fuerzan aprendizaje", () => {
  const trainSet = [
    { source: "El sistema me descontó el pisto dos veces.", target: "El sistema me descontó el saldo disponible dos veces." },
    { source: "Parce, necesitamos desbloquear el corte contable.", target: "Equipo de soporte, necesitamos desbloquear el corte contable." },
  ];
  const cleanTestSet = [
    { source: PRESET_TICKETS[0].ticketText, target: PRESET_TICKETS[0].humanReference },
  ];
  const cleanAudit = verifyZeroDataLeaks(trainSet, cleanTestSet);
  assert.equal(cleanAudit.passed, true);
  assert.equal(cleanAudit.leaks.length, 0);

  const leakyTestSet = [
    { source: "el sistema me desconto el pisto dos veces!", target: "otra frase" },
  ];
  const leakyAudit = verifyZeroDataLeaks(trainSet, leakyTestSet);
  assert.equal(leakyAudit.passed, false);
  assert.equal(leakyAudit.leaks.length, 1);

  const dropout = applyGlossaryDropout(REGIONAL_GLOSSARY, 0.15, "seed-determinista-42");
  assert.equal(dropout.keptEntries.length + dropout.droppedEntries.length, REGIONAL_GLOSSARY.length);
  assert.ok(dropout.effectiveKeepRatio >= 0.7 && dropout.effectiveKeepRatio <= 0.95);
});

test("2. retrieveHybridRRF combina BM25 + Dense Subword con RRF (k=60) y ordena con best_last", () => {
  const gtTicket = PRESET_TICKETS[0].ticketText;
  const rag = retrieveHybridRRF(gtTicket, { region: "GT", k: 60, topN: 5, order: "best_last" });

  assert.equal(rag.order, "best_last");
  assert.equal(rag.rrfK, 60);
  assert.ok(rag.detectedIdioms.length >= 4);

  const detectedNames = rag.detectedIdioms.map(h => h.idiom);
  assert.ok(detectedNames.includes("clavo"));
  assert.ok(detectedNames.includes("pisto"));
  assert.ok(detectedNames.includes("baras"));
  assert.ok(detectedNames.includes("chispudo"));

  // En best_last, el último elemento del arreglo tiene el mayor puntaje RRF
  const firstScore = rag.hits[0].rrfScore;
  const lastScore = rag.hits[rag.hits.length - 1].rrfScore;
  assert.ok(lastScore >= firstScore, `Se esperaba lastScore (${lastScore}) >= firstScore (${firstScore})`);
});

test("3. mbrSelectConsensus (MBR-3) elige el candidato que maximiza el consenso chrF++ promedio", () => {
  const candidates = [
    "Equipo de soporte, tuvimos un incidente técnico con el lote #804 por 450 quetzales (GTQ).",
    "Equipo de soporte, tuvimos un incidente técnico con el lote #804 por 450 quetzales (GTQ).",
    "Hola, hubo una falla rara sin monto verificado.",
  ];
  const mbr = mbrSelectConsensus(candidates);
  assert.equal(mbr.selected, candidates[0]);
  assert.ok(mbr.candidatesWithSupport[0].supportScore > mbr.candidatesWithSupport[2].supportScore);
});

test("4. validateNormalizedTicket verifica 0 modismos crudos y 100% de preservación numérica", () => {
  const gtTicket = PRESET_TICKETS[0].ticketText;
  const rag = retrieveHybridRRF(gtTicket, { region: "GT" });

  const goodCheck = validateNormalizedTicket(
    PRESET_TICKETS[0].humanReference,
    gtTicket,
    rag.detectedIdioms
  );
  assert.equal(goodCheck.passed, true);
  assert.equal(goodCheck.untranslatedIdioms.length, 0);
  assert.deepEqual(goodCheck.preservedNumbers, ["14:30", "804", "450"]);

  const badCheck = validateNormalizedTicket(
    "Hola soporte, tuvimos un gran clavo con el lote #804 por pisto.",
    gtTicket,
    rag.detectedIdioms
  );
  assert.equal(badCheck.passed, false);
  assert.ok(badCheck.untranslatedIdioms.includes("clavo"));
  assert.ok(badCheck.missingNumbers.includes("450"));
});

test("5. computeChrFPlusPlus y runSupportDuel demuestran ventaja del Especialista sobre Zero-Shot en GT, CO y MX", async () => {
  process.env.FORCE_INSTANT_MODE = "1";

  for (const preset of PRESET_TICKETS) {
    const result = await runSupportDuel({
      ticketText: preset.ticketText,
      region: preset.region,
      customerName: preset.customerName,
      humanReference: preset.humanReference,
    });

    assert.equal(result.duel.specialist.validation.passed, true);
    assert.equal(result.duel.zeroShot.validation.passed, false);
    assert.ok(
      result.duel.specialist.chrfPlusPlus > result.duel.zeroShot.chrfPlusPlus + 15,
      `En ${preset.region}, Especialista (${result.duel.specialist.chrfPlusPlus}) debe superar ampliamente a Zero-Shot (${result.duel.zeroShot.chrfPlusPlus})`
    );
    assert.ok(result.duel.specialist.chrfPlusPlus >= 85);
  }
});
