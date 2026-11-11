# Multilingual course coverage

Coursebooks are available in English, Russian and Uzbek (Latin script), through one language-switching entry page per book. Notebooks retain separate language files.

| Step | Russian reading | Russian runnable notebook |
|---|---|---|
| 1 | Notebook narrative | 00_starter_ru.ipynb |
| 2 | taqsim_blocks_coursebook_ru.html | 01_blocks_ru.ipynb |
| 3 | Existing multilingual reservoir_and_farm_coursebook.html | Existing 02_rationing_ru.ipynb |
| 4 | river_for_nature_coursebook_ru.html | 05_eflow_ru.ipynb |
| 5 | sixteen_blocks_read_first_ru.html and handout PDF | Game-based step; no notebook in either language |
| 6 | simulation_coursebook_ru.html | 03_simulation_ru.ipynb |
| 7 | optimization_coursebook_ru.html | 04_optimization_ru.ipynb |
| 8 | gemini/README_RU.md and API_CARD_RU.md | 06_gemini_rescue_ru.ipynb |

Translation sources and review records are maintained in the authoring repository, zarafshan-taqsim/scripts/course_assets/translations/.

Participant-facing prose is translated, including instructions and scientific explanations. Python identifiers and APIs stay unchanged. Original simulation and optimization raster figures retain embedded English labels, with Russian captions/explanations; ecological-flow figures and block diagrams have Russian labels. All five additional coursebooks have full Uzbek prose and captions; the reservoir-and-farm book already supported all three languages. Some original figures retain English labels with translated captions and glossaries. The optional interactive block explorer and supplementary simulation PDF remain explicitly marked English. This update adds Uzbek coursebooks, not new Uzbek notebooks.

Checks preserve executable calculations, equations, numerical tables, links and notebook structure. Models were not rerun for translation. The English optimization coursebook lacks some later computed result figures; the Russian edition discloses this inherited limitation. Simulation source inconsistencies are documented in the authoring review notes. These source limitations are not corrected silently during translation.

## Block editor (step 3)

The block editor (`interactive/rationing-builder/`, `02_rationing_visual_*.ipynb`) has its prose in English, Russian and Uzbek, switchable inside the page; `?lang=ru` or `?lang=uz` opens it in that language. Block kinds, block ids in the sandbox and the Python code stay English, and figures keep their English labels, as in the notebooks. Its texts live in this repository, in `src/zarafshan_taqsim/block_editor/i18n*.py`. The Russian and Uzbek texts were machine-written from the English with the terms of `02_rationing_ru.ipynb` and `02_rationing_uz.ipynb` and have not had a native-speaker review yet.

## Language navigation

Canonical coursebook URLs now open a compact language-switching page. Each loads the selected full book from `_en.html`, `_ru.html` or `_uz.html`. This keeps the long simulation book from downloading three copies at once. The switcher preserves section anchors and remembers the selected language. Direct language-file links return to the canonical page with that language selected; the full content is also readable with JavaScript disabled. The existing reservoir-and-farm book retains its original inline switcher.
