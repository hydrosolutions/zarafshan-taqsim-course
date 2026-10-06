<p align="right"><a href="#english">English</a> · <a href="#russian">Русский</a> · <a href="#uzbek">Oʻzbekcha</a></p>

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

## The notebooks

Open each one with its button. Every notebook starts with a setup box that takes about a minute. Always run that box
first.

| | Notebook | What you do |
|---|---|---|
| 0 | [Starter](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb) | Build and run a small river system, then change it with Gemini |
| 1 | [Simulation](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_simulation.ipynb) | The full Zarafshan model: 61 elements, six years, day by day |
| 2 | Rationing: [English](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_en.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_ru.ipynb) · [Oʻzbekcha](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_uz.ipynb) | Ration early or run dry? A reservoir rule, in your language |
| 3 | [Optimisation](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_optimization.ipynb) | Let the computer search thousands of allocation plans and show the trade-offs |
| 4 | [River flow for nature](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_eflow.ipynb) | How much water to leave in the river, and how |

## Order of the sessions

The course follows one thread, from a plan you can hold in your head to one a computer has to search for:

1. **Starter notebook** (0): the tools, and your first model change with Gemini.
2. **Warm-up game** (`games/zarafshan_warmup_game.html`): three levers, four results, and the question "can any
   other plan beat mine?". No code.
3. **Simulation notebook** (1): the real Zarafshan system, day by day.
4. **Rationing notebook** (2): two levers, a few results, and the set of plans that no other plan beats. This is the
   Pareto idea, without the word.
5. **Zarafshan game** (`games/zarafshan_tradeoff_game.html`): six levers, five results, and the optimiser's own
   front to compare your plan against.
6. **Optimisation notebook** (3): the same idea with its proper name, and the computer doing the search.
7. **River-for-nature game and notebook** (`games/eflow_game.html`, then 4): a different trade-off, water for the
   crops against a river that still behaves like a river.

The three games are single web pages in the folder `games/`. To use one: open the folder on GitHub, click the file,
click the download button (an arrow pointing down), then open the downloaded file in any browser. They work without
internet.

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

- `00_starter.ipynb` to `04_eflow.ipynb`: the course notebooks, in the order of the sessions.
- `src/zarafshan_taqsim/`: the Zarafshan model code the notebooks use.
- `data/ZRB_baseline/`: the inflow, demand, reservoir and canal data, 2010 to 2023.
- `eflow_game/`: the model behind the river-for-nature notebook and game, with its precomputed results.
- `games/`: the three interactive pages.
- `_cache/`: results of long computer runs, so the optimisation notebook opens in seconds.

The model software is [TaqSim](https://github.com/hydrosolutions/taqsim), by hydrosolutions GmbH. The course material
was prepared for the TaqSim training in Tashkent, 12 to 13 October 2026.


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

## Тетради

Открывайте каждую по её кнопке. Каждая тетрадь начинается с блока настройки, который занимает около минуты. Всегда
запускайте этот блок первым.

| | Тетрадь | Что вы делаете |
|---|---|---|
| 0 | [Старт](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb) | Собираете и запускаете маленькую речную систему, затем меняете её с помощью Gemini |
| 1 | [Моделирование](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_simulation.ipynb) | Полная модель Зарафшана: 61 элемент, шесть лет, день за днём |
| 2 | Лимитирование: [English](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_en.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_ru.ipynb) · [Oʻzbekcha](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_uz.ipynb) | Ограничивать подачу заранее или опустошить водохранилище? Правило для водохранилища, на вашем языке |
| 3 | [Оптимизация](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_optimization.ipynb) | Компьютер перебирает тысячи планов распределения и показывает компромиссы |
| 4 | [Вода для реки](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_eflow.ipynb) | Сколько воды оставлять в реке — и как |

## Порядок занятий

Курс идёт по одной нити: от плана, который можно удержать в голове, до плана, который приходится искать компьютеру:

1. **Стартовая тетрадь** (0): инструменты и первое изменение модели с помощью Gemini.
2. **Разминочная игра** (`games/zarafshan_warmup_game.html`): три рычага, четыре результата и вопрос «может ли
   какой-нибудь другой план побить мой?». Без кода.
3. **Тетрадь по моделированию** (1): настоящая система Зарафшана, день за днём.
4. **Тетрадь по лимитированию** (2): два рычага, несколько результатов и набор планов, которые не побить никаким
   другим планом. Это идея Парето, пока без самого слова.
5. **Игра «Зарафшан»** (`games/zarafshan_tradeoff_game.html`): шесть рычагов, пять результатов и фронт, найденный
   оптимизатором, чтобы сравнить с ним свой план.
6. **Тетрадь по оптимизации** (3): та же идея под своим именем, и поиск делает компьютер.
7. **Игра и тетрадь «вода для реки»** (`games/eflow_game.html`, затем 4): другой компромисс — вода для полей против
   реки, которая всё ещё ведёт себя как река.

Три игры — это отдельные веб-страницы в папке `games/`. Чтобы открыть одну: откройте папку на GitHub, нажмите на
файл, нажмите кнопку скачивания (стрелка вниз) и откройте скачанный файл в любом браузере. Интернет для них не нужен.

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

- `00_starter.ipynb` … `04_eflow.ipynb`: тетради курса в порядке занятий.
- `src/zarafshan_taqsim/`: код модели Зарафшана, который используют тетради.
- `data/ZRB_baseline/`: данные о притоке, водопотреблении, водохранилищах и каналах, 2010–2023.
- `eflow_game/`: модель, стоящая за тетрадью и игрой «вода для реки», с заранее рассчитанными результатами.
- `games/`: три интерактивные страницы.
- `_cache/`: результаты долгих расчётов, чтобы тетрадь по оптимизации открывалась за секунды.

Программа модели — [TaqSim](https://github.com/hydrosolutions/taqsim), разработка hydrosolutions GmbH. Материалы
подготовлены для обучения TaqSim в Ташкенте, 12–13 октября 2026 года.


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

## Daftarlar

Har birini oʻz tugmasi bilan oching. Har bir daftar bir daqiqacha davom etadigan sozlash bloki bilan boshlanadi. Doim
avval shu blokni ishga tushiring.

| | Daftar | Nima qilasiz |
|---|---|---|
| 0 | [Boshlanish](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/00_starter.ipynb) | Kichik daryo tizimini qurib ishga tushirasiz, soʻng Gemini yordamida oʻzgartirasiz |
| 1 | [Modellashtirish](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/01_simulation.ipynb) | Zarafshonning toʻliq modeli: 61 element, olti yil, kun-bakun |
| 2 | Cheklash: [English](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_en.ipynb) · [Русский](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_ru.ipynb) · [Oʻzbekcha](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/02_rationing_uz.ipynb) | Erta cheklash yoki omborni boʻshatish? Suv ombori qoidasi, oʻz tilingizda |
| 3 | [Optimallashtirish](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/03_optimization.ipynb) | Kompyuter minglab taqsimot rejalarini koʻrib chiqib, murosalarni koʻrsatadi |
| 4 | [Daryo uchun suv](https://colab.research.google.com/github/hydrosolutions/zarafshan-taqsim-course/blob/main/04_eflow.ipynb) | Daryoda qancha suv qoldirish kerak — va qanday qilib |

## Mashgʻulotlar tartibi

Kurs bitta ip boʻylab boradi: xayolda ushlab turish mumkin boʻlgan rejadan kompyuter qidirishi kerak boʻlgan rejagacha:

1. **Boshlanish daftari** (0): vositalar va Gemini bilan birinchi model oʻzgartirishi.
2. **Isinish oʻyini** (`games/zarafshan_warmup_game.html`): uchta richag, toʻrtta natija va «boshqa biror reja
   menikini yenga oladimi?» degan savol. Kodsiz.
3. **Modellashtirish daftari** (1): haqiqiy Zarafshon tizimi, kun-bakun.
4. **Cheklash daftari** (2): ikkita richag, bir nechta natija va boshqa hech qaysi reja yenga olmaydigan rejalar
   toʻplami. Bu Pareto gʻoyasi, hozircha soʻzning oʻzisiz.
5. **«Zarafshon» oʻyini** (`games/zarafshan_tradeoff_game.html`): oltita richag, beshta natija va oʻz rejangizni
   solishtirish uchun optimallashtiruvchi topgan front.
6. **Optimallashtirish daftari** (3): oʻsha gʻoya oʻz nomi bilan, qidiruvni esa kompyuter qiladi.
7. **«Daryo uchun suv» oʻyini va daftari** (`games/eflow_game.html`, soʻng 4): boshqa murosa — ekinlar uchun suv
   va hali ham daryodek oqadigan daryo.

Uchta oʻyin `games/` papkasidagi alohida veb-sahifalardir. Birini ochish uchun: GitHub da papkani oching, faylni
bosing, yuklab olish tugmasini (pastga qaragan strelka) bosing va yuklangan faylni istalgan brauzerda oching. Ular
internetsiz ishlaydi.

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

- `00_starter.ipynb` … `04_eflow.ipynb`: kurs daftarlari, mashgʻulotlar tartibida.
- `src/zarafshan_taqsim/`: daftarlar ishlatadigan Zarafshon modelining kodi.
- `data/ZRB_baseline/`: oqim, suv talabi, suv omborlari va kanallar maʼlumotlari, 2010–2023.
- `eflow_game/`: «daryo uchun suv» daftari va oʻyini ortidagi model, oldindan hisoblangan natijalar bilan.
- `games/`: uchta interaktiv sahifa.
- `_cache/`: uzoq hisob-kitoblar natijalari, optimallashtirish daftari soniyalarda ochilishi uchun.

Model dasturi — hydrosolutions GmbH tomonidan ishlab chiqilgan [TaqSim](https://github.com/hydrosolutions/taqsim).
Materiallar Toshkentda 2026-yil 12–13-oktabrda oʻtkaziladigan TaqSim oʻquv kursi uchun tayyorlangan.
