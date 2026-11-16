# Night log, body-join (WO44, chunk joining)

- Rules pushed first (`docs/JOIN_RULES.md`, 8f72ba2); test 2 wording simplified before any result (methods unchanged).
- Methods A0 raw, A1 blocks (E1 decoder path), B overlap (Hann, 20-token hop), C offset ramp (raw chunks). Materials H, HJ, RT, RN, M; 37 songs; realised simulation. Run on cores 14-19, 37 songs in ~12 min, no errors.
- Checks: A1 == E1 stored model rows (assert), A0 rebuild == stored E1 controls (assert), E1 statistics reproduced (retrieval 2.03, random 2.5, model 1.37 per-joint). 5 tests pass.
- Result: re-joined human reaches human level (A1 and B); raw controls reach it with C; decoded controls and model stay at 2.4-3.4x at the lamp. See `docs/JOIN_REPORT.md`.
- FOR USER: interval choice (P10-P90, mean), lamp vs per-joint statistic difference for the model, no join analogue on model tokens.

JOIN READY 995f9d0
