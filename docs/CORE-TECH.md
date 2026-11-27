# TOKEN ZOMBIE core technology (by Rishav Mishra)

Original ideas and designs (candidates for the Sutra intelligence core):
1. Measured-vs-estimated labelling: every number carries its evidence level (MEASURED / EST / UNKNOWN).
2. Offline replay benchmark (`tz bench replay`): input-eq = input + 0.1 x cache read + 1.25 x cache write, no tokens spent.
3. Recoverable trimming (`tzout` + `tz recall`): output is cut but never lost; ids bring it back.
4. Handoff and resume (`tzhandoff`, `tzmem`): save where you stopped, resume in a fresh chat, read only what the note names.
5. Chat-size and loop early warning (`tzbudget`, guard hooks).
6. Tool pruning (`tztoolprune`): leave out unused tool schemas, give back on demand.
7. Gate and policy layer (`tzgate`, `tzpolicy`): advice-not-block approval policy for publish, push, paid work.
8. Skill-pack on/off budget model (skillpack) and the 69-capability map.
9. A/B proof harness (`tz ab`, smoke S1-S4 with a fake claude) for honest savings.
10. The TZ bar guard (bar must never go missing).

Not original; keep their own licences (see NOTICE): cc-safety-net, aider, planning-with-files, Headroom, lean-ctx, RTK, beads, karpathy-skills.
