<p align="right"><a href="#english">English</a> · <a href="#russian">Русский</a> · <a href="#uzbek">Oʻzbekcha</a> &nbsp;|&nbsp; <a href="https://hydrosolutions.github.io/zarafshan-taqsim-course/">Course page</a> (links open in new tabs)</p>

<a id="english"></a>
# TaqSim course: water allocation in the Zarafshan basin

Welcome. This folder holds everything you need for the hands-on part of the course. You run the exercises in your
web browser, on Google's free Colab service. Nothing has to be installed on your computer.

## Before the course: three things to do (15 minutes)

**1. Get a Google account.** If you already have a Gmail address, you can use it. If not, create one at
[accounts.google.com](https://accounts.google.com/signup). Google may ask for a phone number to confirm it is you.

**2. Open the first notebook.** Click this button:

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb)

A page with text and grey boxes of code opens. This is a *notebook*. Each grey box is a step you can run.

**3. Run it.** In the menu at the top, choose **Runtime → Run all**. The first box installs the model software, which
takes about a minute. Then a drawing of a small river system appears, a table, and a chart. If you see those, you
are ready for the course.

If Colab asks "Run anyway?" because the notebook was not written by Google, click **Run anyway**. That is normal.

## Trying the AI helper (10 minutes, optional but recommended)

Colab has a built-in AI assistant called Gemini. In the course you will use it to change water models by describing
what you want in plain words. To try it:

1. Click the blue **Gemini** button at the bottom of the page.
2. Copy this sentence into the chat and send it:

   > Find the smallest canal share, in steps of 1 percent, for which the farm has no shortage in any of the three
   > years. Use the run() function.

3. Gemini answers with code. Click **Insert** (or copy the code into a new box with **+ Code**) and run the box.
   The right answer is **9 percent**.

If that worked, you have done everything the course needs. More tasks for Gemini are in the notebook itself.

## Three kinds of material

Every step offers up to three things. The table below always names them the same way:

- **Read: coursebook.** A complete text with learning objectives, the background of the Zarafshan basin, the data and
  where they come from, the model, worked results and a reference list, as a web page with every figure in place.
  Nothing to run, no account needed.
- **Run: notebook.** The same text in Colab, with the code behind it, folded until you want to see it. Change a number,
  run again, see what happens. Needs a Google account.
- **Play: game.** An interactive web page: you move the levers, the results were computed in advance. No code, no
  account. There are four games: TaqSim block by block (step 2), the reservoir game (step 3), the river for nature (step 4) and the Zarafshan in
  sixteen blocks (step 5).

After each link, the languages it comes in: EN English, RU Russian, UZ Uzbek. The data the coursebooks use are in
the folder `data/` of this package.

## The course, step by step

Each step adds one thing to the step before. Start at the top, even if you know water models already: the tools are
new to everyone.

**The workshop runs over two half-days, 14–15 October 2026.** We work through the sequence below with demonstrations, games and hands-on exercises; the pace is flexible. The aim is to run and modify prepared examples and explain their results. We finish with a Gemini demonstration and an optional challenge. Anything unfinished can be continued afterwards; all materials stay online.

| Step | What | New in this step | Open |
|---|---|---|---|
| | **Introduction** | | |
| 1 | **Starter notebook** | The tools: Colab, a notebook, a tiny river system, and Gemini changing it for you | Run: [notebook](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb) (EN) |
| 2 | **TaqSim block by block** | The seven kinds of block TaqSim is made of, each with an everyday picture, the smallest system that shows what it does, and its rule card: the few lines of code that tell it what to do each month. Then all seven in one small river, and the check that every drop is accounted for | **[Interactive coursebook — try it](https://hydrosolutions.github.io/zarafshan-taqsim-course/interactive/taqsim-blocks/) (EN)** · Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/taqsim_blocks_coursebook.html) (EN) · Run: [notebook](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_blocks.ipynb) (EN) · Play: [game](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/taqsim_blocks_game.html) (EN · RU) |
| | **Toy examples** | | |
| 3 | **A reservoir and a farm** | Your first water plan: two levers, a few results, and the set of plans no other plan beats. That is the Pareto idea, before the word. Then a winter water user and a seasonal forecast of the summer, first perfect, then one that can be wrong: what a forecast is worth | Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/reservoir_and_farm_coursebook.html) (EN · RU · UZ) · Run: notebook in [English](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_en.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_ru.ipynb) · [Oʻzbekcha](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_uz.ipynb) · Play: [game](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/rationing_explorer.html) (EN · RU) |
| 4 | **River for nature, game and notebook** | A different kind of trade-off: water for the crops against a river that still behaves like a river | Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/river_for_nature_coursebook.html) (EN) · Run: [notebook](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/05_eflow.ipynb) (EN) · Play: [game](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/eflow_game.html) (EN · RU) |
| 5 | **The Zarafshan in sixteen blocks** | A first model of the whole oasis, as a game: three levers, four results, and the question "can any other plan beat mine?". Five worlds to play in: a dry, a mean and a wet year, and the mean year as the climate models project it for 2041–2070 and 2071–2099. No code | Read: [what the model shows](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/sixteen_blocks_read_first.html) (EN) · [one-page handout, PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/sixteen_blocks_handout.pdf) (EN) · Play: [game](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/zarafshan_warmup_game.html) (EN · RU) |
| | **Real World application** | | |
| 6 | **The Zarafshan model** | The real basin as TaqSim sees it: the river from the Ravatkhoza headworks to Navoi, the two reservoirs (Kattakurgan and Akdarya), six irrigation districts, the thermal power plant and the canals with their losses: 61 blocks, run day by day over 2017–2022. Three allocation rules at the headworks are compared: equal shares, shares fixed to each branch's six-year demand, and shares that follow the month. Every run is read as a water balance: who got what, who went short, where the water was lost | Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/simulation_coursebook.html) · [PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/zrb_water_system_simulation_coursebook.pdf) (EN) · Run: [notebook](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_simulation.ipynb) (EN) |
| 7 | **Optimising the Zarafshan** | The same model with its 124 knobs exposed: the river-reserve share at four headworks and the two reservoirs' month-by-month release rules. Four goals that pull against each other: the farms' total deficit, the power plant's cooling water, fairness between districts, and releases an operator can actually run. NSGA-II, the search method, tries tens of thousands of plans and returns the unbeaten ones; the coursebook shows how to read a Pareto front in four dimensions and what the optimizer learned about running the reservoirs | Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/optimization_coursebook.html) (EN) · Run: [notebook](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_optimization.ipynb) (EN) |
| | **Build your own model with Gemini** | | |
| 8 | **Build your own model with Gemini** | Start from a blank Colab notebook and describe a reservoir and two farms in everyday language. Follow the demonstration, check the connections and water balance, correct a mistake, then optionally modify the model for your own challenge | Read: [prompt guide and checks](gemini/README.md) (EN) · [Русский](gemini/README_RU.md) · Start: [blank notebook](https://colab.research.google.com/#create=true) · Run: [rescue notebook](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue.ipynb) (EN · RU) |

Every notebook starts with a setup box that takes about a minute. Always run that box first.
The games are single web pages: click the link and play, nothing to install. For a room without internet, open
the `games` folder on GitHub, click the file, click the download button (an arrow pointing down, top right), and open
the downloaded file in any browser.

## If something goes wrong

- **A box shows red text and stops.** Read the last line of the red text. Then paste the whole red text into Gemini
  and ask "what went wrong?". This is also how you will work during the course.
- **"Runtime disconnected".** Colab stops a notebook after a while without use. Choose **Runtime → Run all** again.
- **The setup box takes very long.** Wait two minutes. If nothing happens, choose **Runtime → Disconnect and delete
  runtime**, then **Runtime → Run all**.
- **Gemini does not appear.** It needs a personal Google account and is not available in every country. Use the free
  [Gemini app](https://gemini.google.com) or [ChatGPT](https://chat.openai.com) in another browser tab instead: paste
  the cheat sheet from the starter notebook and your question there, and copy the code back into Colab.

## For people who have Python on their computer

Everything also runs locally with Python 3.12 or newer and `git`:

```
git clone https://github.com/hydrosolutions/zarafshan-taqsim-course.git
cd zarafshan-taqsim-course
pip install deap ctrl-freak pymoo polars jupyter
pip install --no-deps "git+https://github.com/hydrosolutions/taqsim.git@v0.1.4"
pip install "git+https://github.com/hydrosolutions/fishy.git@881660e8901987d63d89caf61ef0d30991000301"
jupyter lab
```

The setup box at the top of each notebook notices that the software is already installed and only sets the paths.

## What is in the folder

- `00_starter.ipynb` to `06_gemini_rescue.ipynb`: the course notebooks. Follow the table above; filenames retain their original numbering.
- `gemini/`: the blank-notebook demonstration guide, checks and optional challenge.
- `src/zarafshan_taqsim/`: the Zarafshan model code the notebooks use.
- `data/ZRB_baseline/`: the inflow, demand, reservoir and canal data, 2010 to 2023.
- `eflow_game/`: the model behind the river-for-nature notebook and game, with its precomputed results.
- `coursebooks/`: the five coursebooks as web pages, to read without running anything.
- `games/`: the four games.
- `_cache/`: results of long computer runs, so the optimisation notebook opens in seconds.

The model software is [TaqSim](https://github.com/hydrosolutions/taqsim), by hydrosolutions GmbH. The course material
was prepared for the TaqSim training in Tashkent, 14 to 15 October 2026.


---

<a id="russian"></a>

# Курс TaqSim: распределение воды в бассейне Зарафшана

Добро пожаловать. В этой папке есть всё, что нужно для практической части курса. Упражнения выполняются в
браузере, в бесплатном сервисе Google Colab. На компьютер ничего устанавливать не нужно.

## Перед курсом: три шага (15 минут)

**1. Заведите аккаунт Google.** Если у вас уже есть адрес Gmail, можно пользоваться им. Если нет, создайте аккаунт на
[accounts.google.com](https://accounts.google.com/signup). Google может попросить номер телефона для подтверждения.

**2. Откройте первую тетрадь.** Нажмите на кнопку:

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb)

Откроется страница с текстом и серыми блоками кода. Это *тетрадь* (notebook). Каждый серый блок — шаг, который можно
запустить.

**3. Запустите её.** В меню сверху выберите **Среда выполнения → Выполнить все** (Runtime → Run all). Первый блок
устанавливает программу модели, это занимает около минуты. Затем появятся схема небольшой речной системы, таблица и
график. Если вы их видите, вы готовы к курсу.

Если Colab спросит «Всё равно запустить?» (Run anyway), потому что тетрадь написана не Google, нажмите **Всё равно
запустить**. Это нормально.

## Пробуем ИИ-помощника (10 минут, по желанию, но рекомендуется)

В Colab встроен ИИ-помощник Gemini. На курсе вы будете с его помощью менять водные модели, описывая словами, что
нужно. Чтобы попробовать:

1. Нажмите синюю кнопку **Gemini** внизу страницы.
2. Скопируйте это предложение в чат и отправьте (можно по-английски, Gemini понимает и русский):

   > Find the smallest canal share, in steps of 1 percent, for which the farm has no shortage in any of the three
   > years. Use the run() function.

3. Gemini ответит кодом. Нажмите **Вставить** (Insert) или скопируйте код в новый блок через **+ Код** и запустите
   его. Правильный ответ — **9 процентов**.

Если это получилось, вы сделали всё, что нужно для курса. Другие задания для Gemini есть в самой тетради.

## Три вида материалов

Каждый шаг предлагает до трёх вещей. В таблице ниже они всегда названы одинаково:

- **Читать: учебник.** Цельный текст с целями обучения, сведениями о бассейне Зарафшана, данными и их источниками,
  моделью, разобранными результатами и списком литературы — в виде веб-страницы со всеми рисунками. Ничего запускать
  не нужно, аккаунт не нужен.
- **Запустить: тетрадь.** Тот же текст в Colab, вместе со стоящим за ним кодом, свёрнутым, пока он вам не нужен.
  Измените число, запустите заново, посмотрите, что изменилось. Нужен аккаунт Google.
- **Играть: игра.** Интерактивная веб-страница: вы двигаете рычаги, результаты рассчитаны заранее. Без кода, без
  аккаунта. Игр четыре: TaqSim блок за блоком (шаг 2), игра с водохранилищем (шаг 3), вода для реки (шаг 4) и Зарафшан в шестнадцати блоках
  (шаг 5).

После каждой ссылки указаны языки: EN английский, RU русский, UZ узбекский. Данные, которые используют учебники,
лежат в папке `data/` этого пакета.

## Курс шаг за шагом

Каждый шаг добавляет одну вещь к предыдущему. Начинайте сверху, даже если водные модели вам знакомы: инструменты новы
для всех.

**Семинар проходит в течение двух полудней, 14–15 октября 2026 года.** Мы следуем приведённой ниже последовательности: демонстрации, игры и практические упражнения; темп гибкий. Цель — запускать и изменять готовые примеры и объяснять результаты. В конце — демонстрация Gemini и необязательное самостоятельное задание. Незавершённые упражнения можно продолжить после курса; все материалы останутся онлайн.

| Шаг | Что | Что нового на этом шаге | Открыть |
|---|---|---|---|
| | **Введение** | | |
| 1 | **Стартовая тетрадь** | Инструменты: Colab, тетрадь, крошечная речная система и Gemini, который меняет её за вас | Запустить: [тетрадь](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb) (EN) |
| 2 | **TaqSim блок за блоком** | Семь видов блоков, из которых состоит TaqSim: у каждого бытовая картинка, самая маленькая система, показывающая, что он делает, и его «карточка правила» — несколько строк кода, которые говорят ему, что делать каждый месяц. Затем все семь в одной маленькой реке и проверка, что учтена каждая капля | **[Интерактивный учебник — попробовать](https://hydrosolutions.github.io/zarafshan-taqsim-course/interactive/taqsim-blocks/) (EN)** · Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/taqsim_blocks_coursebook.html) (EN) · Запустить: [тетрадь](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_blocks.ipynb) (EN) · Играть: [игра](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/taqsim_blocks_game.html) (EN · RU) |
| | **Учебные примеры** | | |
| 3 | **Водохранилище и поле** | Ваш первый план водопользования: два рычага, несколько результатов и набор планов, которые не побить никаким другим. Это идея Парето, пока без самого слова | Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/reservoir_and_farm_coursebook.html) (EN · RU · UZ) · Запустить: тетрадь на [English](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_en.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_ru.ipynb) · [Oʻzbekcha](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_uz.ipynb) · Играть: [игра](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/rationing_explorer.html) (EN · RU) |
| 4 | **Вода для реки: игра и тетрадь** | Компромисс другого рода: вода для полей против реки, которая всё ещё ведёт себя как река | Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/river_for_nature_coursebook.html) (EN) · Запустить: [тетрадь](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/05_eflow.ipynb) (EN) · Играть: [игра](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/eflow_game.html) (EN · RU) |
| 5 | **Зарафшан в шестнадцати блоках** | Первая модель всего оазиса в виде игры: три рычага, четыре результата и вопрос «может ли другой план побить мой?». Пять «миров»: сухой, средний и влажный год, а также средний год, каким его проецируют климатические модели на 2041–2070 и 2071–2099. Без кода | Читать: [что показывает модель](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/sixteen_blocks_read_first.html) (EN) · [памятка на одной странице, PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/sixteen_blocks_handout.pdf) (EN) · Играть: [игра](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/zarafshan_warmup_game.html) (EN · RU) |
| | **Применение к реальному бассейну** | | |
| 6 | **Модель Зарафшана** | Настоящий бассейн глазами TaqSim: река от Раватхузского гидроузла до Навои, два водохранилища (Каттакурганское и Акдарьинское), шесть ирригационных районов, тепловая электростанция и каналы с их потерями: 61 блок, расчёт день за днём за 2017–2022 годы. Сравниваются три правила распределения на гидроузлах: равные доли, доли по шестилетней потребности каждой ветви и доли, меняющиеся по месяцам. Каждый расчёт читается как водный баланс: кто сколько получил, кому не хватило, где вода потерялась | Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/simulation_coursebook.html) · [PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/zrb_water_system_simulation_coursebook.pdf) (EN) · Запустить: [тетрадь](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_simulation.ipynb) (EN) |
| 7 | **Оптимизация Зарафшана** | Та же модель со 124 открытыми «ручками»: доля воды, оставляемой реке на четырёх гидроузлах, и помесячные правила сброса двух водохранилищ. Четыре цели, которые тянут в разные стороны: суммарный дефицит хозяйств, охлаждающая вода электростанции, справедливость между районами и сбросы, которые оператор действительно может выполнять. NSGA-II, метод поиска, перебирает десятки тысяч планов и возвращает непревзойдённые; учебник показывает, как читать фронт Парето в четырёх измерениях и чему оптимизатор «научился» в управлении водохранилищами | Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/optimization_coursebook.html) (EN) · Запустить: [тетрадь](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_optimization.ipynb) (EN) |
| | **Создайте свою модель с Gemini** | | |
| 8 | **Создайте свою модель с Gemini** | Начните с пустой тетради Colab и опишите водохранилище и два хозяйства обычными словами. Следуйте демонстрации, проверьте связи и водный баланс, исправьте ошибку, затем при желании измените модель для своей задачи | Читать: [подсказки и проверки](gemini/README_RU.md) (RU) · [English](gemini/README.md) · Начать: [пустая тетрадь](https://colab.research.google.com/#create=true) · Запустить: [готовая запасная тетрадь](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue.ipynb) (EN · RU) |

Каждая тетрадь начинается с блока настройки, который занимает около минуты. Всегда запускайте этот блок первым.
Игры — это отдельные веб-страницы: нажмите на ссылку и играйте, устанавливать ничего не нужно. Для зала без
интернета откройте папку `games` на GitHub, нажмите на файл, затем на кнопку скачивания (стрелка вниз, справа вверху)
и откройте скачанный файл в любом браузере.

## Если что-то пошло не так

- **В блоке появился красный текст, и он остановился.** Прочитайте последнюю строку красного текста. Затем вставьте
  весь красный текст в Gemini и спросите «что пошло не так?». Так же вы будете работать и во время курса.
- **«Среда выполнения отключена» (Runtime disconnected).** Colab останавливает тетрадь, если ею долго не пользуются.
  Снова выберите **Среда выполнения → Выполнить все**.
- **Блок настройки работает очень долго.** Подождите две минуты. Если ничего не происходит, выберите **Среда
  выполнения → Отключить и удалить среду выполнения**, затем **Выполнить все**.
- **Gemini не появляется.** Ему нужен личный аккаунт Google, и он доступен не во всех странах. Вместо него откройте в
  другой вкладке бесплатное [приложение Gemini](https://gemini.google.com) или [ChatGPT](https://chat.openai.com):
  вставьте туда шпаргалку из стартовой тетради и свой вопрос, а полученный код скопируйте обратно в Colab.

## Для тех, у кого на компьютере есть Python

Всё работает и локально, с Python 3.12 или новее и `git`:

```
git clone https://github.com/hydrosolutions/zarafshan-taqsim-course.git
cd zarafshan-taqsim-course
pip install deap ctrl-freak pymoo polars jupyter
pip install --no-deps "git+https://github.com/hydrosolutions/taqsim.git@v0.1.4"
pip install "git+https://github.com/hydrosolutions/fishy.git@881660e8901987d63d89caf61ef0d30991000301"
jupyter lab
```

Блок настройки в начале каждой тетради заметит, что программа уже установлена, и только задаст пути.

## Что в папке

- `00_starter.ipynb` … `06_gemini_rescue.ipynb`: тетради курса. Следуйте таблице выше; исходная нумерация файлов сохранена.
- `gemini/`: руководство для демонстрации с пустой тетради, проверки и необязательное задание.
- `src/zarafshan_taqsim/`: код модели Зарафшана, который используют тетради.
- `data/ZRB_baseline/`: данные о притоке, водопотреблении, водохранилищах и каналах, 2010–2023.
- `eflow_game/`: модель, стоящая за тетрадью и игрой «вода для реки», с заранее рассчитанными результатами.
- `coursebooks/`: пять учебников в виде веб-страниц, для чтения без запуска.
- `games/`: четыре игры.
- `_cache/`: результаты долгих расчётов, чтобы тетрадь по оптимизации открывалась за секунды.

Программа модели — [TaqSim](https://github.com/hydrosolutions/taqsim), разработка hydrosolutions GmbH. Материалы
подготовлены для обучения TaqSim в Ташкенте, 14–15 октября 2026 года.


---

<a id="uzbek"></a>

# TaqSim kursi: Zarafshon havzasida suv taqsimoti

Xush kelibsiz. Bu papkada kursning amaliy qismi uchun kerak boʻlgan hamma narsa bor. Mashqlar brauzerda, Googlening
bepul Colab xizmatida bajariladi. Kompyuteringizga hech narsa oʻrnatish shart emas.

## Kursdan oldin: uchta ish (15 daqiqa)

**1. Google hisobini oching.** Gmail manzilingiz boʻlsa, undan foydalanishingiz mumkin. Boʻlmasa,
[accounts.google.com](https://accounts.google.com/signup) sahifasida yarating. Google tasdiqlash uchun telefon raqamini
soʻrashi mumkin.

**2. Birinchi daftarni oching.** Shu tugmani bosing:

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb)

Matn va kulrang kod bloklari boʻlgan sahifa ochiladi. Bu *daftar* (notebook). Har bir kulrang blok ishga tushirish
mumkin boʻlgan bitta qadam.

**3. Ishga tushiring.** Yuqoridagi menyudan **Runtime → Run all** ni tanlang. Birinchi blok model dasturini oʻrnatadi,
bu bir daqiqacha vaqt oladi. Soʻng kichik daryo tizimining chizmasi, jadval va grafik paydo boʻladi. Ularni koʻrsangiz,
kursga tayyorsiz.

Agar Colab daftar Google tomonidan yozilmagani uchun «Run anyway?» deb soʻrasa, **Run anyway** ni bosing. Bu odatiy hol.

## Sunʼiy intellekt yordamchisini sinab koʻrish (10 daqiqa, ixtiyoriy, lekin tavsiya etiladi)

Colab ichida Gemini nomli yordamchi bor. Kursda siz u orqali suv modellarini oddiy soʻzlar bilan tasvirlab
oʻzgartirasiz. Sinab koʻrish uchun:

1. Sahifaning pastidagi koʻk **Gemini** tugmasini bosing.
2. Shu jumlani chatga nusxalab yuboring (inglizcha boʻlsa ham boʻladi):

   > Find the smallest canal share, in steps of 1 percent, for which the farm has no shortage in any of the three
   > years. Use the run() function.

3. Gemini kod bilan javob beradi. **Insert** ni bosing (yoki kodni **+ Code** orqali yangi blokka nusxalang) va blokni
   ishga tushiring. Toʻgʻri javob — **9 foiz**.

Shu ishlagan boʻlsa, kurs uchun kerak boʻlgan hamma narsani qildingiz. Gemini uchun boshqa topshiriqlar daftarning
oʻzida bor.

## Uch xil material

Har bir qadam uchtagacha narsa taklif qiladi. Quyidagi jadvalda ular doim bir xil nomlanadi:

- **Oʻqish: darslik.** Oʻquv maqsadlari, Zarafshon havzasi haqidagi maʼlumot, maʼlumotlar va ularning manbalari,
  model, tahlil qilingan natijalar va adabiyotlar roʻyxati bilan toʻliq matn, barcha rasmlari bilan veb-sahifa
  sifatida. Hech narsa ishga tushirish shart emas, hisob kerak emas.
- **Ishga tushirish: daftar.** Oʻsha matn Colab da, orqasidagi kod bilan, siz koʻrmoqchi boʻlguncha yigʻilgan holda.
  Raqamni oʻzgartiring, qayta ishga tushiring, nima oʻzgarganini koʻring. Google hisobi kerak.
- **Oʻynash: oʻyin.** Interaktiv veb-sahifa: richaglarni siz surasiz, natijalar oldindan hisoblangan. Kodsiz, hisobsiz.
  Oʻyinlar toʻrtta: TaqSim blokma-blok (2-qadam), suv ombori oʻyini (3-qadam), daryo uchun suv (4-qadam)
  va oʻn olti blokdagi Zarafshon (5-qadam).

Har bir havoladan keyin uning tillari koʻrsatilgan: EN inglizcha, RU ruscha, UZ oʻzbekcha. Darsliklar ishlatadigan
maʼlumotlar ushbu paketning `data/` papkasida.

## Kurs qadam-baqadam

Har bir qadam oldingisiga bitta narsa qoʻshadi. Suv modellarini bilsangiz ham yuqoridan boshlang: vositalar hamma uchun
yangi.

**Seminar 2026-yil 14–15-oktabr kunlari, ikki yarim kun davom etadi.** Quyidagi ketma-ketlikda namoyishlar, oʻyinlar va amaliy mashqlar bilan ishlaymiz; surʼat moslashuvchan. Maqsad — tayyor misollarni ishga tushirish, oʻzgartirish va natijalarini tushuntirish. Yakunda Gemini namoyishi va ixtiyoriy mustaqil topshiriq boʻladi. Tugallanmagan mashqlarni keyin davom ettirish mumkin; barcha materiallar onlayn qoladi.

| Qadam | Nima | Bu qadamda nima yangi | Ochish |
|---|---|---|---|
| | **Kirish** | | |
| 1 | **Boshlanish daftari** | Vositalar: Colab, daftar, kichkina daryo tizimi va uni siz uchun oʻzgartiradigan Gemini | Ishga tushirish: [daftar](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb) (EN) |
| 2 | **TaqSim blokma-blok** | TaqSim tashkil topgan yetti xil blok: har birining kundalik hayotdan olingan tasviri, nima qilishini koʻrsatadigan eng kichik tizim va uning «qoida kartasi» — har oy nima qilishni aytadigan bir necha qator kod. Soʻng yettalasi bitta kichik daryoda va har bir tomchi hisobga olinganini tekshirish | **[Interaktiv darslik — sinab koʻring](https://hydrosolutions.github.io/zarafshan-taqsim-course/interactive/taqsim-blocks/) (EN)** · Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/taqsim_blocks_coursebook.html) (EN) · Ishga tushirish: [daftar](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_blocks.ipynb) (EN) · Oʻynash: [oʻyin](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/taqsim_blocks_game.html) (EN · RU) |
| | **Sodda oʻquv misollari** | | |
| 3 | **Suv ombori va dala** | Birinchi suv rejangiz: ikkita richag, bir nechta natija va boshqa hech qaysi reja yenga olmaydigan rejalar toʻplami. Bu Pareto gʻoyasi, hozircha soʻzsiz | Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/reservoir_and_farm_coursebook.html) (EN · RU · UZ) · Ishga tushirish: daftar [English](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_en.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_ru.ipynb) · [Oʻzbekcha](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_uz.ipynb) tilida · Oʻynash: [oʻyin](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/rationing_explorer.html) (EN · RU) |
| 4 | **Daryo uchun suv: oʻyin va daftar** | Boshqa turdagi murosa: ekinlar uchun suv va hali ham daryodek oqadigan daryo | Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/river_for_nature_coursebook.html) (EN) · Ishga tushirish: [daftar](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/05_eflow.ipynb) (EN) · Oʻynash: [oʻyin](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/eflow_game.html) (EN · RU) |
| 5 | **Oʻn olti blokdagi Zarafshon** | Butun vohaning oʻyin shaklidagi birinchi modeli: uchta richag, toʻrtta natija va «boshqa biror reja menikini yenga oladimi?» degan savol. Beshta «dunyo»: qurgʻoqchil, oʻrtacha va seryogʻin yil, hamda iqlim modellari 2041–2070 va 2071–2099 uchun bashorat qilgan oʻrtacha yil. Kodsiz | Oʻqish: [model nimani koʻrsatadi](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/sixteen_blocks_read_first.html) (EN) · [bir sahifali eslatma, PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/sixteen_blocks_handout.pdf) (EN) · Oʻynash: [oʻyin](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/zarafshan_warmup_game.html) (EN · RU) |
| | **Haqiqiy havzaga tatbiq** | | |
| 6 | **Zarafshon modeli** | Haqiqiy havza TaqSim koʻzi bilan: Ravatxoʻja gidrouzelidan Navoiygacha daryo, ikkita suv ombori (Kattaqoʻrgʻon va Oqdaryo), oltita sugʻorish tumani, issiqlik elektr stansiyasi va yoʻqotishlari bilan kanallar: 61 blok, 2017–2022 yillar davomida kun-bakun hisob. Gidrouzellarda uchta taqsimlash qoidasi taqqoslanadi: teng ulushlar, har bir tarmoqning olti yillik ehtiyojiga qarab belgilangan ulushlar va oyma-oy oʻzgaradigan ulushlar. Har bir hisob suv balansi sifatida oʻqiladi: kim qancha oldi, kimga yetmadi, suv qayerda yoʻqoldi | Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/simulation_coursebook.html) · [PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/zrb_water_system_simulation_coursebook.pdf) (EN) · Ishga tushirish: [daftar](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_simulation.ipynb) (EN) |
| 7 | **Zarafshonni optimallashtirish** | Oʻsha model 124 ta ochiq «dastak» bilan: toʻrtta gidrouzelda daryoga qoldiriladigan suv ulushi va ikki suv omborining oyma-oy chiqarish qoidalari. Bir-biriga qarshi tortadigan toʻrtta maqsad: xoʻjaliklarning umumiy taqchilligi, elektr stansiyasining sovitish suvi, tumanlar orasidagi adolat va operator haqiqatan bajara oladigan chiqarishlar. Qidiruv usuli NSGA-II oʻn minglab rejani sinab koʻrib, ustun kelib boʻlmaydiganlarini qaytaradi; darslik toʻrt oʻlchamli Pareto frontini qanday oʻqishni va optimallashtirgich suv omborlarini boshqarishda nimani «oʻrganganini» koʻrsatadi | Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/optimization_coursebook.html) (EN) · Ishga tushirish: [daftar](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_optimization.ipynb) (EN) |
| | **Gemini bilan oʻz modelingizni yarating** | | |
| 8 | **Gemini bilan oʻz modelingizni yarating** | Boʻsh Colab daftaridan boshlang va suv ombori hamda ikkita xoʻjalikni oddiy soʻzlar bilan tasvirlang. Namoyishni kuzating, bogʻlanishlar va suv balansini tekshiring, xatoni tuzating, soʻng ixtiyoriy ravishda modelni oʻz vazifangizga moslang | Oʻqish: [soʻrovlar va tekshiruvlar qoʻllanmasi](gemini/README.md) (EN) · [Русский](gemini/README_RU.md) · Boshlash: [boʻsh daftar](https://colab.research.google.com/#create=true) · Ishga tushirish: [tayyor zaxira daftar](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue.ipynb) (EN · RU) |

Har bir daftar bir daqiqacha davom etadigan sozlash bloki bilan boshlanadi. Doim avval shu blokni ishga tushiring.
Oʻyinlar alohida veb-sahifalardir: havolani bosing va oʻynang, hech narsa oʻrnatish shart emas. Internetsiz xona
uchun GitHub da `games` papkasini oching, faylni bosing, yuklab olish tugmasini (oʻng yuqoridagi pastga strelka) bosing
va yuklangan faylni istalgan brauzerda oching.

## Agar biror narsa notoʻgʻri ketsa

- **Blokda qizil matn chiqdi va u toʻxtadi.** Qizil matnning oxirgi qatorini oʻqing. Soʻng butun qizil matnni
  Gemini ga qoʻyib, «nima notoʻgʻri ketdi?» deb soʻrang. Kurs davomida ham shunday ishlaysiz.
- **«Runtime disconnected».** Colab uzoq vaqt ishlatilmagan daftarni toʻxtatadi. Yana **Runtime → Run all** ni
  tanlang.
- **Sozlash bloki juda uzoq ishlayapti.** Ikki daqiqa kuting. Hech narsa boʻlmasa, **Runtime → Disconnect and delete
  runtime**, soʻng **Runtime → Run all** ni tanlang.
- **Gemini chiqmayapti.** Unga shaxsiy Google hisobi kerak va u hamma mamlakatda ham mavjud emas. Oʻrniga boshqa
  oynada bepul [Gemini ilovasi](https://gemini.google.com) yoki [ChatGPT](https://chat.openai.com) dan foydalaning:
  boshlanish daftaridagi eslatma varaqasini va savolingizni u yerga qoʻying, olingan kodni Colab ga qaytarib nusxalang.

## Kompyuterida Python bor kishilar uchun

Hammasi lokal ham ishlaydi, Python 3.12 yoki undan yangisi va `git` bilan:

```
git clone https://github.com/hydrosolutions/zarafshan-taqsim-course.git
cd zarafshan-taqsim-course
pip install deap ctrl-freak pymoo polars jupyter
pip install --no-deps "git+https://github.com/hydrosolutions/taqsim.git@v0.1.4"
pip install "git+https://github.com/hydrosolutions/fishy.git@881660e8901987d63d89caf61ef0d30991000301"
jupyter lab
```

Har bir daftarning boshidagi sozlash bloki dastur allaqachon oʻrnatilganini sezadi va faqat yoʻllarni belgilaydi.

## Papkada nima bor

- `00_starter.ipynb` … `06_gemini_rescue.ipynb`: kurs daftarlari. Yuqoridagi jadvalga amal qiling; fayllarning eski raqamlari saqlangan.
- `gemini/`: boʻsh daftardan boshlash qoʻllanmasi, tekshiruvlar va ixtiyoriy topshiriq.
- `src/zarafshan_taqsim/`: daftarlar ishlatadigan Zarafshon modelining kodi.
- `data/ZRB_baseline/`: oqim, suv talabi, suv omborlari va kanallar maʼlumotlari, 2010–2023.
- `eflow_game/`: «daryo uchun suv» daftari va oʻyini ortidagi model, oldindan hisoblangan natijalar bilan.
- `coursebooks/`: beshta darslik veb-sahifa koʻrinishida, hech narsa ishga tushirmasdan oʻqish uchun.
- `games/`: toʻrtta oʻyin.
- `_cache/`: uzoq hisob-kitoblar natijalari, optimallashtirish daftari soniyalarda ochilishi uchun.

Model dasturi — hydrosolutions GmbH tomonidan ishlab chiqilgan [TaqSim](https://github.com/hydrosolutions/taqsim).
Materiallar Toshkentda 2026-yil 14–15-oktabrda oʻtkaziladigan TaqSim oʻquv kursi uchun tayyorlangan.
