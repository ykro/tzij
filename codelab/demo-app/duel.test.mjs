import test from "node:test";
import assert from "node:assert/strict";
import {
  SAMPLE_TICKETS,
  findRelevantIdioms,
  buildSpecialistPrompt,
  validateTranslation,
  processSupportTicket
} from "./server.mjs";

test("1. findRelevantIdioms extrae únicamente los modismos presentes en el ticket en orden de aparición", () => {
  const hits = findRelevantIdioms(SAMPLE_TICKETS[0].rawText);
  const terms = hits.map((h) => h.term);
  assert.deepEqual(terms, ["cabal", "clavo", "pisto", "chispudo"]);
});

test("2. buildSpecialistPrompt incluye las pistas regionales y coloca la última pista justo antes del mensaje", () => {
  const hits = findRelevantIdioms(SAMPLE_TICKETS[1].rawText);
  const prompt = buildSpecialistPrompt(SAMPLE_TICKETS[1].rawText, hits);
  assert.match(prompt, /"vaina" \(CO\) significa:/);
  assert.match(prompt, /Mensaje del cliente:/);
});

test("3. validateTranslation confirma que los montos se conserven y que no queden modismos sin traducir", () => {
  const ticket = SAMPLE_TICKETS[0];
  const hits = findRelevantIdioms(ticket.rawText);
  const check = validateTranslation(ticket.rawText, ticket.cleanReference, hits);
  assert.equal(check.passed, true);
  assert.deepEqual(check.preservedAmounts, ["Q450"]);
  assert.equal(check.leftoverIdioms.length, 0);
});

test("4. processSupportTicket logra 100% de claridad frente a la salida sin diccionario en los 3 países", async () => {
  for (const sample of SAMPLE_TICKETS) {
    const res = await processSupportTicket(sample.rawText);
    assert.equal(res.validation.passed, true);
    assert.equal(res.cleanScore, 100);
    assert.ok(res.cleanScore > res.naiveScore);
  }
});
