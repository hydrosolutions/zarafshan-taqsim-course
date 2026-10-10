# Build your own small model with Gemini

[Русский](README_RU.md) · [Working rescue notebook](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue.ipynb) · [TaqSim API card](API_CARD.md)

**First watch a guided demonstration; then optionally try your own change.** The aim is to describe a water system clearly and check the generated model, not to become a Python programmer. Gemini writes a draft; you remain responsible for the connections, units, allocation rule and interpretation.

We extend the earlier reservoir-and-one-farm example to two farms, using deliberately small, invented numbers. This is not calibrated Zarafshan data or an exact replay of the earlier game.

## Start from a genuinely blank notebook

1. Open [Google Colab](https://colab.research.google.com/) and create a new notebook. Name it and save your own copy.
2. Open the Gemini assistant available in your account. The interface and availability can vary; if no assistant is available, work with the facilitator or use the rescue notebook. You can also paste generated code into Colab cells yourself.
3. Give Gemini the prompt below **and the full [API card](API_CARD.md)**. Work one cell at a time: read it, run it, inspect its output, then continue.
4. If you get stuck, open the rescue notebook in a separate tab and compare the failing cell. Do not replace the exercise with an unexplained wall of generated code.

A notebook mixes explanation and executable code. Python is the language in the code cells. A variable gives a value a name; a list holds a sequence of values; a function is a reusable instruction. Run cells from top to bottom. Editing a cell does not rerun it or the cells below it. A runtime restart clears stored Python values; rerun the setup and following cells. Red error text is a clue to inspect, not a result to ignore.

## Prompt 1 — agree on the system before coding

> Help me build a small TaqSim v0.1.4 model in a blank Google Colab notebook. I am a Python beginner. Follow the attached API card; do not invent classes or methods. First restate the system, draw its directed network and list assumptions. Wait before writing code.
>
> River → reservoir → allocation node → two farms A and B → downstream sink. Six monthly steps. All water values are volumes in million cubic metres (Mm³) per step, not rates in m³/s. River inflows are [8, 4, 2, 0, 10, 2]. Reservoir capacity 20, initial storage 6, dead storage 0. No evaporation, seepage or travel delays. A needs 4 each month, B needs 3. Release up to their combined need of 7, limited by available storage after inflow. Allocate 4/7 to A and 3/7 to B. Farms consume up to their need, with efficiency and consumption fraction both 1. Surplus goes downstream. Reservoir overflow also reaches the allocation node. Use a fresh model for each comparison. This is a teaching example, not a real operating model.

**Stop and check:** do the arrows match your drawing? Does “equal treatment” mean equal volumes or equal fractions of need? Here we chose equal fractions of need.

## Prompt 2 — build, run, show the accounting

> Now generate one short cell at a time, explaining it in plain language. Install the pinned version as shown on the API card. Keep inputs together and code visible. Build and validate the network. Show a monthly table of inflow, end storage, release, overflow, consumption and shortage for each farm, downstream outflow and water-balance error. Plot storage and shortages. Check each month: initial storage + inflow = final storage + consumption A + consumption B + downstream outflow. Check storage limits. Do not claim that a successful run proves that the assumptions are correct.

**Independent answer:** storage must end at [7, 4, 0, 0, 3, 0]; releases are [7, 7, 6, 0, 7, 5]. Month 1: 6 + 8 − 7 = 7 stored, A gets 4 and B gets 3. Month 3: only 6 is available, A gets 24/7 and B gets 18/7. Total water used is 32; total shortage is 10. Compare unrounded values with a small numerical tolerance, not exact floating-point equality.

## Prompt 3 — catch a deliberate mistake

> Make a separate comparison run with a 50/50 split, described as “equal treatment”. Keep all other inputs unchanged. Does it satisfy the original intention of equal fractions of each farm's need? Show each farm's fraction of need met and the water balance. Explain any difference. Do not change the original model yet.

This version runs and conserves water, but it implements a different decision. With 7 released, A gets 3.5 for a need of 4; B consumes 3 and sends 0.5 downstream. A correct water balance alone cannot detect the wrong meaning.

> Correct the allocation to equal fractions of need, using 4/7 and 3/7. Rerun from the original starting storage. Keep the balance and hand-calculation checks, and show that the correction works. If any check fails, explain why before changing code. Do not weaken checks to hide a failure.

## Optional challenge — change one thing

Choose drier inflows, a different initial storage, priority for one farm, or a minimum downstream flow. The last two require deciding the rule precisely; a downstream minimum needs a new allocation rule, not simply a new label. Predict the effect before asking Gemini to edit.

> I want to change [one thing]. Before coding, tell me which assumptions, connections and checks must change, and who I expect to benefit or lose water. Then make the smallest change, rerun from fresh initial conditions and compare against the baseline. Retain the water balance and calculate a new small hand-check where the original numeric reference no longer applies.

Finish by explaining your system, one result, one check and one remaining limitation to a neighbour. If time is short, a correct explanation of the prepared result is enough.

## Facilitator preparation

Test Colab access, package installation and the Gemini account before the session. Keep the rescue notebook available. Do not depend on Gemini producing the deliberate mistake spontaneously: request the 50/50 comparison explicitly. Generated answers vary; the numeric reference and checks are the stable teaching anchors. This exercise does not promise independent model maintenance or institutional transfer.
