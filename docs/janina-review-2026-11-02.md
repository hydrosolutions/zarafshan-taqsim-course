# Janina's course review: implementation record

Reviewed issues #2–#51 in hydrosolutions/zarafshan-taqsim-course. The four implementation batches are recorded below. Publication uses GitHub Pages from `main`; issues #2–#51 are intentionally left open for Janina to verify and close.

## Batch 1: access and notebook onboarding

- #2: Gemini action alternatives in EN/RU/UZ, retaining manual copy/paste.
- #3, #23: text/code-cell guidance and setup explanation before the first block-notebook code cell.
- #4: documentation download defaults to off in both starter notebooks.
- #24: remove clipping on the table itself; retain a keyboard-focusable scrolling wrapper.
- #40–42: expose editable cells, explain ranges before the exercise, compare custom and baseline plans in a labelled table.
- #25–28: larger network labels, inflow chart with month selection, edge details on mouse/focus/tap, mobile card scrolling.

## Batch 2: water-accounting explanations and figures

- #11–13: monthly medians, second-year plots, optional rule-card explanations, early Strategy definition.
- #14–17: net demand versus gross withdrawal, upstream allocation, application loss versus return flow, turbine analogy and explicit spill boundary.
- #18–20: month-name display selector separate from model parameters; zero canyon loss is an assumption; seven types versus ten blocks; valve explanation.
- #21–22: distinct storage colours and signed storage labels; explain how the balance adds up. Updated the model plotting helper, retained static chart and the wheel used by the interactive export.
- #39: correct reversed Figure 6 caption and identify the right-hand reservoir panels.

## Batch 3: step 3 teaching sequence

- #30–31, #33–38: early goals and knob definitions, generated-river settings and finite-sample explanation, reservoir comparison introduced before the result, ration denominator and water-availability qualification.
- #43–45, #47–48: symbol table, exact dominance definition and Pareto-front reminder, separate chart/table explanations, Objective provenance.
- #49: explain objective/search/comparison sequence, population/generations, budget and additional scoring runs, distinct score pairs versus distinct parameter settings. The HTML explicitly identifies its retained 32-pair output as a saved run; a fresh run in the verification environment produced 38 pairs from 40 returned plans.
- #51: winter-user roadmap, changed objectives, fixed summer plan, explicit zero-request policy, forecast introduced as unused until the next section, rounding explanation.

## Batch 4: navigation and terminology

- #5–10: concise language coverage, course-menu jumps, group divider rows, short action descriptions, TaqSim introduction and v0.1.4 documentation link.
- #29, #46: aligned reservoir/farm title and visible course-step numbers; existing filenames/URLs retained.
- #32: cross-links to steps 4–6.
- #50: basin-place glossary distinguishes reservoir from irrigation district and the 40 Mm³ teaching model from the 667 Mm³ reservoir example.

Optional redesigns were not required to address the findings: separate language landing pages, a new geographic map, another canyon-loss slider, renamed notebook files, and splitting the paired reservoir comparison figure. The current changes use clearer guidance, existing language navigation, and the retained comparison layout.

## Verification

- Phone-width browser check (360px): all three tables exceed their wrappers and scroll; none clips the link column.
- Blocks game: inflow-chart selection changes the displayed month; tapping a block brings its heading to the top of the mobile viewport; no browser errors observed.
- Interactive WASM coursebook loads and computes the final water-balance table; new dropdown and expandable explanations are present; no browser errors observed.
- The complete English step 3 executable sequence passes through the final forecast sections (setup/install cell excluded; temporary pinned TaqSim v0.1.4 environment).
- All notebook code cells pass syntax parsing after accounting for Colab magics; landing-page fragment links resolve.
- Marimo source passes `marimo check` after formatting fixes.
- Default custom plan: average shortage 1.99125 Mm³/year, worst month 45%, 24 short years.
- Winter comparison: farm shortage 6.9149459448 → 2.6625; winter-field shortage 0.3635423030 → 5.325. Differences round to 4.3 and 5.0; displayed one-decimal endpoints do not preserve their exact differences.
- Blocks balance: river 4218.1 = sinks 3459.1380504 + consumption 179.809 + losses 367.5529496 + turbine spill 211.6 + storage change 0, within floating-point precision.

The browser checks use a desktop browser at phone width, not Janina's physical Android devices. Colab's signed-in Gemini interface was not exercised. Translation wording should receive Janina's language review.

## Maintaining the interactive export

The editable source is `interactive/taqsim-blocks/notebook.py`. Run `python scripts/sync_blocks_export.py` after changing it or `src/zarafshan_taqsim/blocks_demo.py`; this synchronizes both source copies in the retained export and the referenced helper wheel, including its RECORD hashes. Runtime assets are retained. Recheck with Marimo and a browser after changes.
