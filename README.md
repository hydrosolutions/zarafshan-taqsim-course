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

The folder `games/` holds three interactive pages used in the sessions. Download one and open it in any browser;
they work without internet.

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
