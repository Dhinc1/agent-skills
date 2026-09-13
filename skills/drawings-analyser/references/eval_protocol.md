# Eval protocol — prove (don't assert) that structure beats images

Blind A/B/C test. Use to validate the skill on a new set.

1. **Ground truth from the NEUTRAL source.** Author ~12-20 questions whose answers come from the vector text layer / verbatim schedules (independent of any one representation). Span: lookup, aggregation/compute, connectivity, multi-hop/navigation, material, and 2+ NEGATIVE/trap questions (answer = "not determinable" or "no"). Negatives are the discriminators — they catch fabrication.
2. **Three arms, each a fresh sub-agent given ONLY its representation, identical instruction** ("answer only from your source; if not determinable say so; don't guess"):
   - A = sheet PNGs (images), B = prose/ markdown, C = project.sqlite (DB).
   Each writes a JSON array {id, answer, confidence, citation}.
3. **Blind judge.** Shuffle the three answers per question into resp_x/y/z (keep a secret key); a separate judge agent grades each correct/partial/incorrect + hallucinated flag against ground truth, not knowing which system is which. Then un-shuffle and tally.
4. **Report:** score/accuracy, hallucination count, and tool-call cost per arm; per-category breakdown; and which questions discriminated.

Expected pattern (replicated twice): structured arms 96-100% / 0 hallucinations / ~4-15 calls; images 86-92% / hallucinations on connectivity+counts / ~95 calls. If the DB underperforms prose, inspect for silent extraction errors (run provenance validation) and entity-count edge cases.
