<p align="right"><a href="#english">English</a> · <a href="#russian">Русский</a> · <a href="#uzbek">Oʻzbekcha</a> &nbsp;|&nbsp; <a href="https://hydrosolutions.github.io/zarafshan-taqsim-course/">Course page</a> (links open in new tabs)</p>

<a id="english"></a>
# TaqSim course: water allocation in the Zarafshan basin

**TaqSim** is a Python tool for simulating water allocation: connect river inflows, reservoirs, canals and users, then follow where the water goes and who goes short. This course uses TaqSim v0.1.4 through notebooks and games.

[New? Start with setup](#before-the-course-three-things-to-do-15-minutes) · [Already ready? Open the course steps](#the-course-step-by-step)

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

3. Read Gemini’s proposed code. **Accept and execute** inserts and runs it; **Accept** inserts it for you to run; **Deny** discards it. Some interfaces instead offer **Insert**. You can also copy the code into **+ Code** and run it.
   The right answer is **9 percent**.

If that worked, you have done everything the course needs. More tasks for Gemini are in the notebook itself.

## ChatGPT and the optional AI Sider sidebar

**ChatGPT and Gemini web officially support Uzbekistan.** See [OpenAI's supported countries](https://help.openai.com/en/articles/7947663-chatgpt-supported-countries) and [Google's supported countries](https://support.google.com/gemini/answer/13575153?hl=en). This confirms provider eligibility, not access on the workshop Wi-Fi: local connectivity without VPN and extension installation still need to be checked before the workshop.

**Use AI Sider: ChatGPT + DeepSeek + Gemini, offered by zenttranslate.** This optional Chrome extension displays the providers' own websites beside your notebook. It is a different product from Sider.ai. No separate extension account is required; sign in to the provider you choose. A [free ChatGPT account](https://chatgpt.com/plans/free/) supplies normal ChatGPT assistance and remains subject to its usual limits. No paid subscription or API key is needed for these exercises.

1. In desktop Chrome, open the [exact AI Sider Chrome Web Store listing](https://chromewebstore.google.com/detail/ai-sider-chatgpt-%2B-deepse/cpggpmmbmacgemcffkapmeadpnfnmkbm), check that the publisher is **zenttranslate**, choose **Add to Chrome** and review the requested permissions. If already installed, open it from the Extensions menu (the puzzle icon).
2. Open the sidebar beside your Colab notebook, select ChatGPT or Gemini, and sign in to that provider. For ChatGPT, choose **Sign up** if needed and stay on the free plan. If sidebar sign-in fails, open [ChatGPT](https://chatgpt.com) or [Gemini](https://gemini.google.com) in a separate tab.
3. Explicitly share the relevant code cell, error, page text or screenshot. Do not assume the assistant can see the whole notebook. Ask: “Explain this code in simple words, then suggest one small change. Show the complete replacement cell.”
4. Read the proposed change, copy it into a new Colab code cell, run it yourself, and check the water balance and results. The sidebar is not a verified way to edit or run Colab automatically. Use only the public course examples when trying a new AI service.

The same prompts work in a separate ChatGPT or Gemini tab. For the reservoir-and-two-farms exercise, also provide the [TaqSim API card](gemini/API_CARD.md) / [Русский](gemini/API_CARD_RU.md), so the assistant uses the course's model version. The workshop demonstration uses Gemini in Colab; AI Sider is an optional alternative interface.

## Three kinds of material

Every step offers up to three things. The table below always names them the same way:

- **Read: coursebook.** A complete text with learning objectives, the background of the Zarafshan basin, the data and
  where they come from, the model, worked results and a reference list, as a web page with every figure in place.
  Nothing to run, no account needed.
- **Run: notebook.** The same text in Colab, with the code behind it, folded until you want to see it. Change a number,
  run again, see what happens. Needs a Google account.
- **Play: game.** An interactive web page: you move the levers, the results appear immediately. No code, no
  account. There are five games: TaqSim block by block (step 2), the reservoir game (step 3), the river for nature (step 4) and the Zarafshan in
  sixteen blocks (step 5), plus an optional annual Amu Darya demonstration.

**Languages.** Coursebooks switch between English, Russian and Uzbek. Notebooks have English and Russian links; step 3 also has an Uzbek notebook. The interactive block coursebook is English only. Some figures have English labels with translated captions. EN = English, RU = Russian, UZ = Uzbek.

**Data.** Open the [course data folder](https://github.com/hydrosolutions/zarafshan-taqsim-course/tree/main/data).

## The course, step by step

Notebook filenames retain older numbering. Follow the step numbers here; each notebook shows its course step.

Each step adds one thing to the step before. Start at the top, even if you know water models already: the tools are
new to everyone.

**The workshop runs over two half-days, 14–15 October 2026.** We work through the sequence below with demonstrations, games and hands-on exercises; the pace is flexible. The aim is to run and modify prepared examples and explain their results. We finish with a Gemini demonstration and an optional challenge. Anything unfinished can be continued afterwards; all materials stay online.

| Step | What | What you will do | Open |
|---|---|---|---|
| | **Introduction** | | |
| 1 | **Starter notebook** | Run a small river model in Colab and try changing it with Gemini. | Run: [notebook — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter_ru.ipynb) |
| 2 | **TaqSim block by block** | Explore the seven block types, their rules and the water balance. | **[Interactive coursebook — try it](https://hydrosolutions.github.io/zarafshan-taqsim-course/interactive/taqsim-blocks/) (EN)** · Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/taqsim_blocks_coursebook.html) (EN · RU · UZ) · Run: [notebook — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_blocks.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_blocks_ru.ipynb) · Play: [game](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/taqsim_blocks_game.html) (EN · RU) |
| | **Toy examples** | | |
| 3 | **A reservoir and a farm** | Try reservoir release rules and compare shortages; explore winter demand and forecasts. | Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/reservoir_and_farm_coursebook.html) (EN · RU · UZ) · Run: notebook in [English](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_en.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_ru.ipynb) · [Oʻzbekcha](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_uz.ipynb) · Play: [game](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/rationing_explorer.html) (EN · RU) |
| 4 | **River for nature, game and notebook** | Compare water for crops with water left for the river. | Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/river_for_nature_coursebook.html) (EN · RU · UZ) · Run: [notebook — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/05_eflow.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/05_eflow_ru.ipynb) · Play: [game](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/eflow_game.html) (EN · RU) |
| 5 | **The Zarafshan in sixteen blocks** | Explore allocation in a simplified Zarafshan basin without writing code. | Read: [what the model shows](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/sixteen_blocks_read_first.html) (EN · RU · UZ) · [handout, PDF — EN](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/sixteen_blocks_handout.pdf) · [Русский, PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/sixteen_blocks_handout_ru.pdf) · Play: [game](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/zarafshan_warmup_game.html) (EN · RU) |
| Optional demo | **Amu Darya: sharing an annual water budget** | Use the Qosh Tepa assessment to explore irrigated area, irrigation efficiency and a negotiated cap on existing withdrawals. Compare historical and reduced-supply assumptions; annual results are teaching scenarios, not current allocations or legal entitlements | Play: [game](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/amu_darya_game.html?lang=en) (EN · RU · UZ) |
| | **Real World application** | | |
| 6 | **The Zarafshan model** | Run the basin model and compare water deliveries, losses and shortages. | Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/simulation_coursebook.html) (EN · RU · UZ) · [PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/zrb_water_system_simulation_coursebook.pdf) (EN) · Run: [notebook — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_simulation.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_simulation_ru.ipynb) |
| 7 | **Optimising the Zarafshan** | Search for allocation rules that balance competing goals. | Read: [coursebook](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/optimization_coursebook.html) (EN · RU · UZ) · Run: [notebook — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_optimization.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_optimization_ru.ipynb) |
| | **Build your own model with Gemini** | | |
| 8 | **Build your own model with Gemini** | Build and check a small model with help from Gemini. | Read: [prompt guide and checks](gemini/README.md) (EN) · [Русский](gemini/README_RU.md) · Start: [blank notebook](https://colab.research.google.com/#create=true) · Run: [rescue notebook — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue_ru.ipynb) |

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
  [Gemini app](https://gemini.google.com) or [ChatGPT](https://chatgpt.com) in another browser tab instead: paste
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
- `games/`: the five games.
- `_cache/`: results of long computer runs, so the optimisation notebook opens in seconds.

The model software is [TaqSim](https://github.com/hydrosolutions/taqsim/tree/v0.1.4), by hydrosolutions GmbH. The course material
was prepared for the TaqSim training in Tashkent, 14 to 15 October 2026.


---

<a id="russian"></a>

# Курс TaqSim: распределение воды в бассейне Зарафшана

**TaqSim** — программа на Python для моделирования распределения воды: соедините притоки, водохранилища, каналы и потребителей и проследите, куда идёт вода и кому её не хватает. Курс использует TaqSim v0.1.4 через тетради и игры.

[Подготовка](#перед-курсом-три-шага-15-минут) · [Перейти к шагам курса](#курс-шаг-за-шагом)

Добро пожаловать. В этой папке есть всё, что нужно для практической части курса. Упражнения выполняются в
браузере, в бесплатном сервисе Google Colab. На компьютер ничего устанавливать не нужно.

## Перед курсом: три шага (15 минут)

**1. Заведите аккаунт Google.** Если у вас уже есть адрес Gmail, можно пользоваться им. Если нет, создайте аккаунт на
[accounts.google.com](https://accounts.google.com/signup). Google может попросить номер телефона для подтверждения.

**2. Откройте первую тетрадь.** Нажмите на кнопку:

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter_ru.ipynb)

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

## ChatGPT и необязательная боковая панель AI Sider

**Веб-версии ChatGPT и Gemini официально поддерживаются в Узбекистане.** См. [список стран OpenAI](https://help.openai.com/en/articles/7947663-chatgpt-supported-countries) и [список стран Google](https://support.google.com/gemini/answer/13575153?hl=en). Это подтверждает поддержку страны, но не работу через Wi-Fi в месте проведения семинара: подключение без VPN и установку расширения ещё нужно проверить на месте.

**Используйте AI Sider: ChatGPT + DeepSeek + Gemini от zenttranslate.** Это необязательное расширение Chrome открывает сайты самих ИИ-сервисов рядом с тетрадью. Оно отличается от Sider.ai. Отдельный аккаунт расширения не нужен: войдите в аккаунт выбранного ИИ-сервиса. [Бесплатный аккаунт ChatGPT](https://chatgpt.com/plans/free/) даёт обычные возможности ChatGPT с его стандартными ограничениями. Для упражнений платная подписка и ключ API не нужны.

1. В Chrome на компьютере откройте [страницу именно этого расширения AI Sider](https://chromewebstore.google.com/detail/ai-sider-chatgpt-%2B-deepse/cpggpmmbmacgemcffkapmeadpnfnmkbm), проверьте издателя **zenttranslate**, нажмите **Add to Chrome** и проверьте запрашиваемые разрешения. Если расширение уже установлено, откройте его через меню расширений (значок пазла).
2. Откройте панель рядом с тетрадью Colab, выберите ChatGPT или Gemini и войдите в аккаунт соответствующего сервиса. Для ChatGPT при необходимости выберите **Sign up** и бесплатный план. Если вход через панель не работает, откройте [ChatGPT](https://chatgpt.com) или [Gemini](https://gemini.google.com) в отдельной вкладке.
3. Явно передайте нужный блок кода, сообщение об ошибке, текст страницы или снимок экрана. Не предполагается, что помощник видит всю тетрадь. Спросите: «Объясни код простыми словами, предложи одно небольшое изменение и покажи полный блок для замены».
4. Прочитайте ответ, вставьте код в новый блок Colab, самостоятельно запустите его и проверьте водный баланс и результаты. Автоматическое редактирование и выполнение кода Colab через эту панель не проверено. Для знакомства с новым ИИ-сервисом используйте только открытые примеры курса.

Эти же запросы работают в отдельной вкладке ChatGPT или Gemini. Для задания с водохранилищем и двумя хозяйствами также передайте [памятку по API TaqSim на русском](gemini/API_CARD_RU.md), чтобы помощник использовал версию модели из курса. Демонстрация на семинаре использует Gemini в Colab; AI Sider — необязательный альтернативный интерфейс.

## Три вида материалов

Каждый шаг предлагает до трёх вещей. В таблице ниже они всегда названы одинаково:

- **Читать: учебник.** Цельный текст с целями обучения, сведениями о бассейне Зарафшана, данными и их источниками,
  моделью, разобранными результатами и списком литературы — в виде веб-страницы со всеми рисунками. Ничего запускать
  не нужно, аккаунт не нужен.
- **Запустить: тетрадь.** Тот же текст в Colab, вместе со стоящим за ним кодом, свёрнутым, пока он вам не нужен.
  Измените число, запустите заново, посмотрите, что изменилось. Нужен аккаунт Google.
- **Играть: игра.** Интерактивная веб-страница: вы двигаете рычаги, результаты появляются сразу. Без кода, без
  аккаунта. Игр пять: TaqSim блок за блоком (шаг 2), игра с водохранилищем (шаг 3), вода для реки (шаг 4) и Зарафшан в шестнадцати блоках
  (шаг 5), а также дополнительная годовая демонстрация для Амударьи.

**Языки.** Учебники доступны на английском, русском и узбекском. Тетради имеют отдельные ссылки EN и RU; на шаге 3 также UZ. Интерактивный учебник блоков — только EN. Некоторые рисунки имеют английские подписи и переведённые пояснения. EN — английский, RU — русский, UZ — узбекский.

**Данные:** [папка курса](https://github.com/hydrosolutions/zarafshan-taqsim-course/tree/main/data).

## Курс шаг за шагом

Номера файлов тетрадей исторические. Следуйте номерам шагов в таблице.

Каждый шаг добавляет одну вещь к предыдущему. Начинайте сверху, даже если водные модели вам знакомы: инструменты новы
для всех.

**Семинар проходит в течение двух полудней, 14–15 октября 2026 года.** Мы следуем приведённой ниже последовательности: демонстрации, игры и практические упражнения; темп гибкий. Цель — запускать и изменять готовые примеры и объяснять результаты. В конце — демонстрация Gemini и необязательное самостоятельное задание. Незавершённые упражнения можно продолжить после курса; все материалы останутся онлайн.

| Шаг | Что | Что вы будете делать | Открыть |
|---|---|---|---|
| | **Введение** | | |
| 1 | **Стартовая тетрадь** | Запустите небольшую модель реки в Colab и измените её с помощью Gemini. | Запустить: [тетрадь — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter_ru.ipynb) |
| 2 | **TaqSim блок за блоком** | Изучите семь типов блоков, их правила и водный баланс. | **[Интерактивный учебник — попробовать](https://hydrosolutions.github.io/zarafshan-taqsim-course/interactive/taqsim-blocks/) (EN)** · Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/taqsim_blocks_coursebook.html) (EN · RU · UZ) · Запустить: [тетрадь — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_blocks.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_blocks_ru.ipynb) · Играть: [игра](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/taqsim_blocks_game.html) (EN · RU) |
| | **Учебные примеры** | | |
| 3 | **Водохранилище и поле** | Сравните правила выпуска и дефицит; исследуйте зимний спрос и прогнозы. | Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/reservoir_and_farm_coursebook.html) (EN · RU · UZ) · Запустить: тетрадь на [English](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_en.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_ru.ipynb) · [Oʻzbekcha](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_uz.ipynb) · Играть: [игра](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/rationing_explorer.html) (EN · RU) |
| 4 | **Вода для реки: игра и тетрадь** | Сравните воду для полей и воду, оставленную реке. | Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/river_for_nature_coursebook.html) (EN · RU · UZ) · Запустить: [тетрадь — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/05_eflow.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/05_eflow_ru.ipynb) · Играть: [игра](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/eflow_game.html) (EN · RU) |
| 5 | **Зарафшан в шестнадцати блоках** | Исследуйте распределение воды в упрощённой модели Зарафшана без кода. | Читать: [что показывает модель](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/sixteen_blocks_read_first.html) (EN · RU · UZ) · [памятка, PDF — EN](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/sixteen_blocks_handout.pdf) · [Русский, PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/sixteen_blocks_handout_ru.pdf) · Играть: [игра](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/zarafshan_warmup_game.html) (EN · RU) |
| Дополнительная демонстрация | **Амударья: распределяем годовой объём воды** | По оценке канала Кош-Тепа исследуйте площадь орошения, эффективность и согласованный предел существующих водозаборов. Сравните исходный и сокращённый приток. Это учебные годовые сценарии, а не текущие распределения или юридические права | Играть: [игра](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/amu_darya_game.html?lang=ru) (EN · RU · UZ) |
| | **Применение к реальному бассейну** | | |
| 6 | **Модель Зарафшана** | Запустите модель бассейна и сравните подачу, потери и дефицит. | Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/simulation_coursebook.html) (EN · RU · UZ) · [PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/zrb_water_system_simulation_coursebook.pdf) (EN) · Запустить: [тетрадь — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_simulation.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_simulation_ru.ipynb) |
| 7 | **Оптимизация Зарафшана** | Найдите правила распределения, учитывающие несколько целей. | Читать: [учебник](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/optimization_coursebook.html) (EN · RU · UZ) · Запустить: [тетрадь — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_optimization.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_optimization_ru.ipynb) |
| | **Создайте свою модель с Gemini** | | |
| 8 | **Создайте свою модель с Gemini** | Создайте и проверьте небольшую модель с помощью Gemini. | Читать: [подсказки и проверки](gemini/README_RU.md) (RU) · [English](gemini/README.md) · Начать: [пустая тетрадь](https://colab.research.google.com/#create=true) · Запустить: [готовая запасная тетрадь — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue_ru.ipynb) |

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
  другой вкладке бесплатное [приложение Gemini](https://gemini.google.com) или [ChatGPT](https://chatgpt.com):
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
- `games/`: пять игр.
- `_cache/`: результаты долгих расчётов, чтобы тетрадь по оптимизации открывалась за секунды.

Программа модели — [TaqSim](https://github.com/hydrosolutions/taqsim/tree/v0.1.4), разработка hydrosolutions GmbH. Материалы
подготовлены для обучения TaqSim в Ташкенте, 14–15 октября 2026 года.


---

<a id="uzbek"></a>

# TaqSim kursi: Zarafshon havzasida suv taqsimoti

**TaqSim** — suv taqsimotini modellashtiradigan Python dasturi: oqimlar, omborlar, kanallar va isteʼmolchilarni ulab, suv qayerga borishi va kimga yetmasligini kuzatasiz. Kurs daftarlar va oʻyinlar orqali TaqSim v0.1.4 dan foydalanadi.

[Tayyorlash](#kursdan-oldin-uchta-ish-15-daqiqa) · [Kurs qadamlari](#kurs-qadam-baqadam)

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

3. Taklif qilingan kodni oʻqing. **Accept and execute** kodni kiritib ishga tushiradi; **Accept** faqat kiritadi; **Deny** rad etadi. Ayrim interfeyslarda **Insert** bor. Kodni **+ Code** orqali nusxalab, ishga tushirish ham mumkin. Toʻgʻri javob — **9 foiz**.

Shu ishlagan boʻlsa, kurs uchun kerak boʻlgan hamma narsani qildingiz. Gemini uchun boshqa topshiriqlar daftarning
oʻzida bor.

## ChatGPT va ixtiyoriy AI Sider yon paneli

**ChatGPT va Gemini veb-versiyalari Oʻzbekistonda rasman qoʻllab-quvvatlanadi.** [OpenAI mamlakatlar roʻyxati](https://help.openai.com/en/articles/7947663-chatgpt-supported-countries) va [Google mamlakatlar roʻyxatini](https://support.google.com/gemini/answer/13575153?hl=en) koʻring. Bu mamlakat qoʻllab-quvvatlanishini bildiradi, ammo seminar joyidagi Wi-Fi orqali ishlashini tasdiqlamaydi: VPNsiz ulanish va kengaytmani oʻrnatishni seminardan oldin joyida tekshirish kerak.

**zenttranslate taqdim etgan AI Sider: ChatGPT + DeepSeek + Gemini kengaytmasidan foydalaning.** Chrome uchun bu ixtiyoriy kengaytma daftar yonida AI xizmatlarining oʻz saytlarini ochadi. U Sider.ai mahsulotidan farq qiladi. Kengaytma uchun alohida hisob kerak emas; tanlangan AI xizmati hisobiga kiring. [Bepul ChatGPT hisobi](https://chatgpt.com/plans/free/) odatiy ChatGPT imkoniyatlarini uning standart cheklovlari bilan beradi. Mashqlar uchun pulli obuna yoki API kaliti kerak emas.

1. Kompyuterdagi Chrome orqali [aynan shu AI Sider kengaytmasining sahifasini](https://chromewebstore.google.com/detail/ai-sider-chatgpt-%2B-deepse/cpggpmmbmacgemcffkapmeadpnfnmkbm) oching, nashriyotchi **zenttranslate** ekanini tekshiring, **Add to Chrome** ni bosing va soʻralgan ruxsatlarni koʻrib chiqing. Kengaytma allaqachon oʻrnatilgan boʻlsa, uni kengaytmalar menyusidan (pazl belgisi) oching.
2. Colab daftari yonida panelni oching, ChatGPT yoki Gemini ni tanlang va tegishli xizmat hisobiga kiring. ChatGPT uchun kerak boʻlsa **Sign up** ni tanlab, bepul tarifda qoling. Panel orqali kirish ishlamasa, [ChatGPT](https://chatgpt.com) yoki [Gemini](https://gemini.google.com) ni alohida brauzer varagʻida oching.
3. Kerakli kod bloki, xato xabari, sahifa matni yoki ekran tasvirini yordamchiga aniq yuboring. U butun daftarni koʻryapti deb oʻylamang. Soʻrang: «Kodni oddiy soʻzlar bilan tushuntir, bitta kichik oʻzgarish taklif qil va almashtirish uchun toʻliq kod blokini koʻrsat».
4. Javobni oʻqing, kodni yangi Colab blokiga nusxalang, oʻzingiz ishga tushiring va suv balansi hamda natijalarni tekshiring. Bu panel orqali Colab kodini avtomatik tahrirlash yoki ishga tushirish tekshirilmagan. Yangi AI xizmatini sinashda faqat kursning ochiq misollaridan foydalaning.

Xuddi shu soʻrovlarni ChatGPT yoki Gemini ochilgan alohida brauzer varagʻida ham ishlatish mumkin. Suv ombori va ikkita xoʻjalik mashqi uchun yordamchiga [TaqSim API qoʻllanmasini](gemini/API_CARD.md) ham bering: shunda u kursdagi model versiyasidan foydalanadi. Seminar namoyishida Gemini Colab ichida ishlatiladi; AI Sider — ixtiyoriy muqobil interfeys.

## Uch xil material

Har bir qadam uchtagacha narsa taklif qiladi. Quyidagi jadvalda ular doim bir xil nomlanadi:

- **Oʻqish: darslik.** Oʻquv maqsadlari, Zarafshon havzasi haqidagi maʼlumot, maʼlumotlar va ularning manbalari,
  model, tahlil qilingan natijalar va adabiyotlar roʻyxati bilan toʻliq matn, barcha rasmlari bilan veb-sahifa
  sifatida. Hech narsa ishga tushirish shart emas, hisob kerak emas.
- **Ishga tushirish: daftar.** Oʻsha matn Colab da, orqasidagi kod bilan, siz koʻrmoqchi boʻlguncha yigʻilgan holda.
  Raqamni oʻzgartiring, qayta ishga tushiring, nima oʻzgarganini koʻring. Google hisobi kerak.
- **Oʻynash: oʻyin.** Interaktiv veb-sahifa: richaglarni siz surasiz, natijalar darhol koʻrinadi. Kodsiz, hisobsiz.
  Oʻyinlar beshta: TaqSim blokma-blok (2-qadam), suv ombori oʻyini (3-qadam), daryo uchun suv (4-qadam)
  va oʻn olti blokdagi Zarafshon (5-qadam), shuningdek Amudaryo uchun qoʻshimcha yillik namoyish.

**Tillar.** Darsliklar ingliz, rus va oʻzbek tillarida. Daftarlarning EN va RU havolalari bor; 3-qadamda UZ ham bor. Interaktiv bloklar darsligi faqat EN. Ayrim rasmlar yozuvi inglizcha, izohlari tarjima qilingan. EN — inglizcha, RU — ruscha, UZ — oʻzbekcha.

**Maʼlumotlar:** [kurs papkasi](https://github.com/hydrosolutions/zarafshan-taqsim-course/tree/main/data).

## Kurs qadam-baqadam

Daftar fayllarining eski raqamlari saqlangan. Jadvaldagi qadam raqamlariga amal qiling; har bir daftar boshida qadam koʻrsatilgan.

Har bir qadam oldingisiga bitta narsa qoʻshadi. Suv modellarini bilsangiz ham yuqoridan boshlang: vositalar hamma uchun
yangi.

**Seminar 2026-yil 14–15-oktabr kunlari, ikki yarim kun davom etadi.** Quyidagi ketma-ketlikda namoyishlar, oʻyinlar va amaliy mashqlar bilan ishlaymiz; surʼat moslashuvchan. Maqsad — tayyor misollarni ishga tushirish, oʻzgartirish va natijalarini tushuntirish. Yakunda Gemini namoyishi va ixtiyoriy mustaqil topshiriq boʻladi. Tugallanmagan mashqlarni keyin davom ettirish mumkin; barcha materiallar onlayn qoladi.

| Qadam | Nima | Bu qadamda nima qilasiz | Ochish |
|---|---|---|---|
| | **Kirish** | | |
| 1 | **Boshlanish daftari** | Colab da kichik daryo modelini ishga tushiring va Gemini bilan oʻzgartiring. | Ishga tushirish: [daftar — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter_ru.ipynb) |
| 2 | **TaqSim blokma-blok** | Yetti blok turi, ularning qoidalari va suv balansini oʻrganing. | **[Interaktiv darslik — sinab koʻring](https://hydrosolutions.github.io/zarafshan-taqsim-course/interactive/taqsim-blocks/) (EN)** · Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/taqsim_blocks_coursebook.html) (EN · RU · UZ) · Ishga tushirish: [daftar — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_blocks.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_blocks_ru.ipynb) · Oʻynash: [oʻyin](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/taqsim_blocks_game.html) (EN · RU) |
| | **Sodda oʻquv misollari** | | |
| 3 | **Suv ombori va dala** | Ombor qoidalari va taqchillikni solishtiring; qishki talab va prognozni oʻrganing. | Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/reservoir_and_farm_coursebook.html) (EN · RU · UZ) · Ishga tushirish: daftar [English](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_en.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_ru.ipynb) · [Oʻzbekcha](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_uz.ipynb) tilida · Oʻynash: [oʻyin](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/rationing_explorer.html) (EN · RU) |
| 4 | **Daryo uchun suv: oʻyin va daftar** | Ekinlarga berilgan va daryoda qoldirilgan suvni solishtiring. | Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/river_for_nature_coursebook.html) (EN · RU · UZ) · Ishga tushirish: [daftar — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/05_eflow.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/05_eflow_ru.ipynb) · Oʻynash: [oʻyin](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/eflow_game.html) (EN · RU) |
| 5 | **Oʻn olti blokdagi Zarafshon** | Zarafshonning sodda modelida suv taqsimotini kodsiz oʻrganing. | Oʻqish: [model nimani koʻrsatadi](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/sixteen_blocks_read_first.html) (EN · RU · UZ) · [bir sahifali eslatma, PDF — EN](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/sixteen_blocks_handout.pdf) · [Русский, PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/sixteen_blocks_handout_ru.pdf) · Oʻynash: [oʻyin](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/zarafshan_warmup_game.html) (EN · RU) |
| Qoʻshimcha namoyish | **Amudaryo: yillik suvni taqsimlash** | Qoʻshtepa baholashi asosida sugʻorish maydoni, samaradorlik va mavjud suv olish chegarasini oʻzgartiring. Yillik oʻquv ssenariylari; amaldagi taqsimot yoki huquqiy meʼyor emas | Oʻynash: [oʻyin](https://hydrosolutions.github.io/zarafshan-taqsim-course/games/amu_darya_game.html?lang=uz) (EN · RU · UZ) |
| | **Haqiqiy havzaga tatbiq** | | |
| 6 | **Zarafshon modeli** | Havza modelini ishga tushirib, yetkazish, yoʻqotish va taqchillikni solishtiring. | Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/simulation_coursebook.html) (EN · RU · UZ) · [PDF](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/zrb_water_system_simulation_coursebook.pdf) (EN) · Ishga tushirish: [daftar — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_simulation.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_simulation_ru.ipynb) |
| 7 | **Zarafshonni optimallashtirish** | Bir nechta maqsadni hisobga oladigan taqsimot qoidalarini izlang. | Oʻqish: [darslik](https://hydrosolutions.github.io/zarafshan-taqsim-course/coursebooks/optimization_coursebook.html) (EN · RU · UZ) · Ishga tushirish: [daftar — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_optimization.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_optimization_ru.ipynb) |
| | **Gemini bilan oʻz modelingizni yarating** | | |
| 8 | **Gemini bilan oʻz modelingizni yarating** | Gemini yordamida kichik model yarating va tekshiring. | Oʻqish: [soʻrovlar va tekshiruvlar qoʻllanmasi](gemini/README.md) (EN) · [Русский](gemini/README_RU.md) · Boshlash: [boʻsh daftar](https://colab.research.google.com/#create=true) · Ishga tushirish: [tayyor zaxira daftar — EN](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/06_gemini_rescue_ru.ipynb) |

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
  oynada bepul [Gemini ilovasi](https://gemini.google.com) yoki [ChatGPT](https://chatgpt.com) dan foydalaning:
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
- `games/`: beshta oʻyin.
- `_cache/`: uzoq hisob-kitoblar natijalari, optimallashtirish daftari soniyalarda ochilishi uchun.

Model dasturi — hydrosolutions GmbH tomonidan ishlab chiqilgan [TaqSim](https://github.com/hydrosolutions/taqsim/tree/v0.1.4).
Materiallar Toshkentda 2026-yil 14–15-oktabrda oʻtkaziladigan TaqSim oʻquv kursi uchun tayyorlangan.
