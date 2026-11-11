# Block editor for step 3 (a reservoir and a farm)

A no-code version of `02_rationing_*.ipynb`: learners drag TaqSim blocks onto a canvas, connect them and move
sliders; every change is run through TaqSim v0.1.4 and the result comes back as scores, text and figures.
Eight guided steps follow the notebook's sections, and six more are the exercises at the end of the coursebook
(a bigger reservoir, another second goal, another river, a seasonal rule, a cautious operator, a late forecast).
A free sandbox with all seven kinds of block exists as a separate lesson and is not part of this page yet.

## Where it is

| What | Where |
|---|---|
| Browser page (no install) | `interactive/rationing-builder/` (`?lang=ru`, `?lang=uz`) |
| Colab notebooks | `02_rationing_visual_en.ipynb`, `_ru`, `_uz` |
| The editor | `src/zarafshan_taqsim/block_editor/` |
| Page source | `interactive/rationing-builder/notebook.py` (marimo) |

Inside `block_editor/`: `editor.js` and `editor.css` are the canvas; `widget.py` connects it to Python;
`compile.py` turns a drawing into a `WaterSystem`; `lessons.py` holds the guided steps; `exercises.py` the six
exercises and `rules.py` the two rules they add; `sandbox.py` the free sandbox; `i18n*.py` the words;
`precomputed.json` the score tables that need hundreds of runs.

## After a change

```
python scripts/precompute_rationing.py --all  # only if rationing_coursebook.py, rules.py or the standard numbers changed (15 minutes or more)
python scripts/check_block_editor.py        # the editor's numbers against the notebook's functions
python scripts/make_visual_notebooks.py     # the three Colab notebooks
uv run --with marimo==0.25.2 --with anywidget python scripts/export_rationing_builder.py   # the browser page
```

The check and the precompute need an environment with taqsim 0.1.4, anywidget, numpy, pandas, matplotlib and
the package on the path. The Colab notebooks read the code from the repository, so they need no export; the
browser page installs the wheel in `interactive/rationing-builder/wheels/`, so it does.

## What the steps hold fixed

One run of the model is always live. The plan grids (441 plans), the optimizer's result and the winter tables
(861 plans for each forecast skill) are read from `precomputed.json`. They were computed for the standard
reservoir (40 Mm³, 20 at the start), farm (45 and 5 Mm³) and river, so steps 4 to 8 lock those numbers; steps
1 to 3 leave them free. Each exercise frees the one thing it is about and has its own tables: plan grids for
reservoirs of 60 and 80 Mm³ and for a second series of 100 years, the optimizer's results for the goal "years
short" and for the two-ration rule, and winter tables for a forecast counted at 70 % and for one that arrives
in the last two winter months.

## The sandbox

`BlockEditor(lesson="sandbox")` shows the free sandbox on its own: any network of the seven kinds of block, a
water balance, save and open. It has no grids and no optimizer. It was the last step of this lesson at first and
was taken out to be used later; nothing links to it yet.

The sandbox's rules are general (`sandbox.py`): a Storage releases what the Demand blocks below it ask for,
with the lesson's trigger and ration; a Splitter gives a share to its first connection. With one farm behind
one reservoir this is exactly the lesson's rule, which the check confirms.

## To carry into the authoring repository

This course repository is generated from `zarafshan-taqsim`. Everything above is new files, which a republish
does not overwrite. Three existing, generated files were edited by hand and need the same change at the source:

- `README.md`: in the step 3 row of each language section, the link "Build it with blocks — no code" at the
  start of the last cell and the three "With blocks in Colab" links before the game link.
- `index.html`: the same two additions in the three step 3 rows.
- `LANGUAGE_COVERAGE.md`: the section "Block editor (step 3)".

`src/zarafshan_taqsim/block_editor/`, the four scripts in `scripts/` and this note should be copied there too
if the authoring repository is the source of `src/`.

## Open points

- The Russian and Uzbek texts were written from the English with the terms of the existing notebooks; they
  have not had a native-speaker review.
- Figures keep English labels in every language, as in the notebooks.
- The first load of the browser page takes about a minute, because Python is downloaded.
