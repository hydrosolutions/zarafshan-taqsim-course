"""TaqSim block by block, as a marimo app: the coursebook's content with a slider on every rule.

Run it (marimo is not a project dependency; it is added for the run only):

    uv run --with marimo marimo run notebooks/taqsim_blocks_app.py

or open it for editing with `marimo edit` instead of `marimo run`.
"""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="TaqSim block by block")


@app.cell
async def _():
    import inspect
    import sys

    import marimo as mo

    if sys.platform == "emscripten":
        import micropip
        from pyodide_js import loadPackage

        # Use Pyodide's compiled scientific packages, and serve our pure Python
        # wheels beside the exported page (also works below a GitHub Pages path).
        await loadPackage(["numpy", "pandas", "matplotlib", "networkx"])
        # TaqSim eagerly imports this helper; its parallel optimizer is not used.
        await micropip.install(["joblib==1.5.2", "ctrl-freak==0.1.0"], deps=False)
        await micropip.install(
            [
                str(mo.notebook_location() / "wheels" / "taqsim-0.1.4-py3-none-any.whl"),
                str(mo.notebook_location() / "wheels" / "zarafshan_taqsim-0.1.0+wasm.catalogue20261013-py3-none-any.whl"),
            ],
            deps=False,
        )

    import matplotlib

    matplotlib.use("Agg")
    import numpy as np
    import pandas as pd
    from taqsim import Demand, Edge, Frequency, PassThrough, Reach, Sink, Source, Splitter, Storage, TimeSeries, WaterSystem
    from taqsim.node import (
        DeficitRecorded,
        WaterConsumed,
        WaterGenerated,
        WaterLost,
        WaterOutput,
        WaterPassedThrough,
        WaterReceived,
        WaterReleased,
        WaterSpilled,
        WaterStored,
    )

    from zarafshan_taqsim.blocks_demo import (
        CAPACITY_MM3,
        DEAD_STORAGE_MM3,
        FARM_NEED_MM3,
        INFLOW_MM3,
        MONTHS,
        START_STORAGE_MM3,
        CanalShare,
        Evaporation,
        Knobs,
        LagRouting,
        ReleaseTheNeed,
        SeepageLoss,
        balance_table,
        monthly,
        plot_balance,
        plot_block_catalogue,
        plot_demo_network,
        plot_months,
        plot_where_the_water_went,
        simulate_demo,
        system_balance,
    )

    river = np.array(INFLOW_MM3)
    need = np.array(FARM_NEED_MM3)

    def card(obj) -> object:
        """A rule's source, as the coursebook's rule card."""
        return mo.vstack([mo.md(f"```python\n{inspect.getsource(obj)}```"), mo.accordion({"How to read this card": mo.md("The class names the rule. Its fields hold settings; `@dataclass` is Python notation for that record. A `Strategy` exposes adjustable settings through `__params__` and allowed ranges through `__bounds__`. The method runs each month. In a split rule, dictionary keys name destination blocks: canal and turbine. LagRouting keeps a queue: take the oldest volume, shift the queue, then add this month’s inflow. Source and Sink need no decision rule; Demand and PassThrough use built-in behaviour.")})])

    def wire(system, *pairs):
        for a, b in pairs:
            system.add_edge(Edge(id=f"{a}_to_{b}", source=a, target=b))
        system.validate()
        return system

    return (
        CAPACITY_MM3,
        CanalShare,
        DEAD_STORAGE_MM3,
        DeficitRecorded,
        Demand,
        Evaporation,
        FARM_NEED_MM3,
        Frequency,
        Knobs,
        LagRouting,
        MONTHS,
        PassThrough,
        Reach,
        ReleaseTheNeed,
        START_STORAGE_MM3,
        SeepageLoss,
        Sink,
        Source,
        Splitter,
        Storage,
        TimeSeries,
        WaterConsumed,
        WaterLost,
        WaterOutput,
        WaterPassedThrough,
        WaterReceived,
        WaterReleased,
        WaterSpilled,
        WaterStored,
        WaterSystem,
        balance_table,
        card,
        mo,
        monthly,
        need,
        np,
        plot_balance,
        plot_block_catalogue,
        plot_demo_network,
        plot_months,
        plot_where_the_water_went,
        river,
        simulate_demo,
        system_balance,
        wire,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # TaqSim block by block

    *Seven kinds of block, one small river, and the rule card each block carries*

    Picture a row of people passing buckets of water along a line. Each person does one simple thing with the
    bucket: one fills it from a spring, one carries it down a corridor, one pours part of it into a second line,
    one keeps it in a tub, one drinks from it, one hands it through a narrow gate, and the last one tips it into
    the sea. Nobody in the line decides anything. Each person holds a small card that says exactly what to do
    with every bucket that arrives.

    That is a TaqSim model. The people are **blocks**, the line is the set of **edges**, and the cards are the
    **rules**. There are seven kinds of block. This page introduces them one at a time, each with its everyday
    picture, the question its rule answers, the smallest system that shows what it does, and **a slider on its
    rule**: move it and everything below it recomputes. At the end all seven work together in one small river
    system, and we check that every drop is accounted for.
    """)
    return


@app.cell
def _(plot_block_catalogue):
    plot_block_catalogue()
    return


@app.cell
def _(mo):
    mo.md(r"""
    Three things are true of every block. **A block only moves water**: it receives, keeps, loses, hands on, and
    never looks at the rest of the network. **A block's rule is a card, not a brain**: a few lines of Python
    that say *given what arrived this month and what I hold, do this*. **A block keeps a diary**: every month it
    writes down what it received, stored, lost, released or failed to deliver, and reading a result means
    reading the diaries.

    **Monthly steps are a choice for this example, not a limit of TaqSim.** A time step is the interval
    represented by one model calculation: choose it to suit your question and data, from hours to years.
    The supplied frequency settings are daily, weekly, monthly and yearly; hourly or other intervals need
    a custom setup, including compatible time handling and rules. Inflows, demands, release limits and
    losses must all match the chosen interval—you cannot simply relabel monthly values as hourly ones.

    **In this course example**, time moves in months, the year starts in October like the hydrological
    year of the Zarafshan, and volumes are in million cubic metres (Mm³). The river is the Zarafshan at
    Ravatkhoja, where it enters the irrigated oasis. For each calendar month we use the median flow of 2010–2023: twelve values describing a typical year, starting in October.

    ## Source and Sink: the spring and the sea

    The two ends of every line. A **Source** puts water into the network each month, from a list of numbers you
    give it. A **Sink** takes water out and records it. Neither has a rule to write. The smallest system is one
    Source, one Sink and one edge; the figure shows what the sea received, which is exactly what the river gave.
    """)
    return


@app.cell
def _(
    Frequency,
    Sink,
    Source,
    TimeSeries,
    WaterReceived,
    WaterSystem,
    monthly,
    plot_months,
    river,
    wire,
):
    _s = WaterSystem(frequency=Frequency.MONTHLY)
    _s.add_node(Source(id="river", inflow=TimeSeries(values=list(river))))
    _s.add_node(Sink(id="sea"))
    wire(_s, ("river", "sea")).simulate(12)
    plot_months({"the river, as the sea received it": monthly(_s.nodes["sea"], WaterReceived, 12)}, "A Source: one number per month, from a list")
    return


@app.cell
def _(LagRouting, SeepageLoss, card, mo):
    mo.vstack(
        [
            mo.md(
                r"""
                ## Reach: a corridor

                A **Reach** is a stretch of river or canal. Water that enters it comes out later, and some of it
                leaks on the way. It carries two cards: a *routing model* that says how long water takes, and a
                *loss rule* that says how much leaks. A `Strategy` is a rule whose parameters the optimizer may tune. Neither of these is a `Strategy`: physics is not something the
                optimizer should tune.
                """
            ),
            mo.vstack([card(LagRouting), card(SeepageLoss)]),
        ]
    )
    return


@app.cell
def _(mo):
    lag = mo.ui.slider(0, 3, value=1, step=1, label="Months the corridor holds water")
    seep = mo.ui.slider(0, 30, value=10, step=5, label="Share that leaks, %")
    mo.hstack([lag, seep], justify="start", gap=3)
    return lag, seep


@app.cell
def _(
    Frequency,
    LagRouting,
    Reach,
    SeepageLoss,
    Sink,
    Source,
    TimeSeries,
    WaterLost,
    WaterOutput,
    WaterReceived,
    WaterSystem,
    lag,
    monthly,
    plot_months,
    river,
    seep,
    wire,
):
    _s = WaterSystem(frequency=Frequency.MONTHLY)
    _s.add_node(Source(id="river", inflow=TimeSeries(values=list(river))))
    _s.add_node(Reach(id="canyon", routing_model=LagRouting(months=lag.value), loss_rule=SeepageLoss(share=seep.value / 100)))
    _s.add_node(Sink(id="sea"))
    wire(_s, ("river", "canyon"), ("canyon", "sea")).simulate(12)
    _c = _s.nodes["canyon"]
    plot_months(
        {"entered the canyon": monthly(_c, WaterReceived, 12), "came out": monthly(_c, WaterOutput, 12), "leaked away": monthly(_c, WaterLost, 12)},
        f"A Reach: {lag.value} month(s) of delay, {seep.value} % loss",
    )
    return


@app.cell
def _(CanalShare, card, mo):
    mo.vstack(
        [
            mo.md(
                r"""
                ## Splitter: a fork with a traffic officer

                A **Splitter** sends water to two or more places. Its card, the *split rule*, says how much goes to
                each target, by the target's name. This card *is* a `Strategy`: `__params__` names the knob the
                optimizer may turn, and `__bounds__` says between which values.
                """
            ),
            card(CanalShare),
        ]
    )
    return


@app.cell
def _(mo):
    share = mo.ui.slider(0, 100, value=30, step=5, label="Share into the canal, %")
    share
    return (share,)


@app.cell
def _(
    CanalShare,
    Frequency,
    Sink,
    Source,
    Splitter,
    TimeSeries,
    WaterReceived,
    WaterSystem,
    monthly,
    plot_months,
    river,
    share,
    wire,
):
    _s = WaterSystem(frequency=Frequency.MONTHLY)
    _s.add_node(Source(id="river", inflow=TimeSeries(values=list(river))))
    _s.add_node(Splitter(id="headworks", split_policy=CanalShare(share=share.value / 100)))
    _s.add_node(Sink(id="canal"))
    _s.add_node(Sink(id="turbine"))
    wire(_s, ("river", "headworks"), ("headworks", "canal"), ("headworks", "turbine")).simulate(12)
    plot_months(
        {"into the canal": monthly(_s.nodes["canal"], WaterReceived, 12), "down the river": monthly(_s.nodes["turbine"], WaterReceived, 12)},
        f"A Splitter: {share.value} % this way, the rest that way",
        kind="bar",
        stacked=True,
    )
    return


@app.cell
def _(Evaporation, ReleaseTheNeed, card, mo):
    mo.vstack(
        [
            mo.md(
                r"""
                ## Storage: a bathtub with a valve

                A **Storage** block is a reservoir. Water pours in, the tub fills, when it is full the rest
                overflows, some goes up as vapour, and the valve at the bottom lets out what you tell it to. Below
                the valve there is water the valve cannot reach (the *dead storage*). Every month the tub does
                things in a fixed order: **receive, store (overflow if full), lose, release.** The tub is fed with
                20% of the river. Both figures below show the second year of a two-year run, reducing the influence of the initial storage.

                **How much evaporates in a real reservoir?** A historical Central Asian modelling study
                used **2 metres per year for Kattakurgan**: over its listed maximum surface area of
                **84.5 km²**, that would mean **169 million m³/year** if the reservoir stayed that full
                all year—an illustrative calculation, not a measured annual loss
                ([Raskin et al., 1992, Table 6](https://www.cawater-info.net/bk/water_land_resources_use/english/english_ver/pdf/raskin-et-al.pdf#page=9)).
                Use this as a lowland benchmark, not a universal setting: real evaporation varies by
                season and equals **evaporation depth × water surface area**, whereas this teaching
                slider removes a simplified percentage of stored water each month (3% by default).
                """
            ),
            mo.vstack([card(ReleaseTheNeed), card(Evaporation)]),
        ]
    )
    return


@app.cell
def _(mo):
    cap = mo.ui.slider(10, 150, value=60, step=10, label="Valve maximum, Mm³ per month")
    evap = mo.ui.slider(0, 6, value=3, step=1, label="Evaporation, % of the content per month")
    mo.hstack([cap, evap], justify="start", gap=3)
    return cap, evap


@app.cell
def _(
    CAPACITY_MM3,
    DEAD_STORAGE_MM3,
    Evaporation,
    Frequency,
    ReleaseTheNeed,
    START_STORAGE_MM3,
    Sink,
    Source,
    Storage,
    TimeSeries,
    WaterLost,
    WaterReleased,
    WaterSpilled,
    WaterStored,
    WaterSystem,
    cap,
    evap,
    mo,
    monthly,
    need,
    np,
    plot_months,
    river,
    wire,
):
    _s = WaterSystem(frequency=Frequency.MONTHLY)
    _s.add_node(Source(id="canal", inflow=TimeSeries(values=list(river * 0.2) * 2)))
    _s.add_node(
        Storage(
            id="reservoir",
            capacity=CAPACITY_MM3,
            dead_storage=DEAD_STORAGE_MM3,
            initial_storage=START_STORAGE_MM3,
            release_policy=ReleaseTheNeed(cap=float(cap.value)),
            loss_rule=Evaporation(share=evap.value / 100),
        )
    )
    _s.add_node(Sink(id="total_outflow"))
    wire(_s, ("canal", "reservoir"), ("reservoir", "total_outflow")).simulate(24)
    _t = _s.nodes["reservoir"]
    _stored, _over, _evap, _rel = (monthly(_t, e, 24) for e in (WaterStored, WaterSpilled, WaterLost, WaterReleased))
    _level = (START_STORAGE_MM3 + np.cumsum(_stored - _evap - _rel))[12:]
    _f1 = plot_months(
        {"went into the tub": _stored[12:], "overflowed": _over[12:], "evaporated": _evap[12:], "released by the valve": _rel[12:]},
        f"A Storage: valve at most {cap.value}, vapour {evap.value} % a month",
        kind="bar",
        reference=("the farm's need", need),
    )
    _f2 = plot_months({"water in the tub": _level}, "How full the tub is (second year)", unit="Mm³")
    _ax = _f2.axes[0]
    _ax.axhline(CAPACITY_MM3, color="#6b6a66", lw=1, ls="--")
    _ax.axhline(DEAD_STORAGE_MM3, color="#6b6a66", lw=1, ls=":")
    _ax.set_ylim(0, 720)
    mo.vstack([_f1, _f2, mo.md(f"The tub ends the second year holding **{_level[-1]:,.0f} Mm³**; it overflowed **{_over[12:].sum():,.0f} Mm³** in the year, this is separate from the valve release. In the complete network below, overflow returns to the river, not the farm.")])
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Demand: a customer

    The **requirement** is the net water needed at the point of use each month, in Mm³, after application losses. In the code it is `need` (`FARM_NEED_MM3`), twelve values starting in October. The Demand receives water allocated upstream; it cannot request an extra diversion. With efficiency e, meeting net requirement d needs d/e at the farm inlet. Surplus water passes downstream.

    The Demand has two settings: application efficiency and consumed share. Conveyance losses happen before it, in the canal Reach; do not count them again at the farm.

    For this irrigation example, a **Demand** is the farm. Distinguish the water arriving at the farm from what happens within it:

    - **Conveyance efficiency** describes losses before water reaches the farm, along the network
      connections—represented here by the canal **Reach** and its seepage rule.
    - **Field application efficiency** (first slider) is the fraction of water withdrawn at the farm
      that is effectively delivered at the point of use. This is the Demand node's `efficiency`.
    - **Consumed share of delivered water** (second slider) is the fraction of that effective delivery
      that is used up, for example by evapotranspiration. The rest returns downstream. This is
      `consumption_fraction`, not a second application-efficiency factor.

    **Read the sliders in that order: apply water, then divide delivery into consumption and return.**
    For 100 m³ withdrawn, 85% application efficiency gives 85 m³ of effective delivery and 15 m³
    of application loss; consuming 70% of the 85 m³ gives **59.5 m³ consumed + 25.5 m³ returned**.
    These add up: **100 = 15 + 59.5 + 25.5 m³**.

    The requirement is compared with **effective delivery**, not with the consumed share alone.
    A shortfall creates a `DeficitRecorded` entry. Water arriving beyond what the farm needs also
    passes downstream. Here the farm receives a fifth of the river, with no reservoir.

    **Where does application loss go?** The 15 m³ in the example leaves this model, recorded as `WaterLost` in the farm’s diary. Unlike the 25.5 m³ returned, it is not routed downstream. Real losses may partly reach groundwater or return to the river; representing recovery requires an explicit connection or rule.
    """)
    return


@app.cell
def _(mo):
    consumption = mo.ui.slider(0, 100, value=70, step=10, label="Consumed share of delivered water, %")
    efficiency = mo.ui.slider(50, 100, value=85, step=5, label="Field application efficiency, %")
    mo.hstack([efficiency, consumption], justify="start", gap=3)
    return consumption, efficiency


@app.cell
def _(
    DeficitRecorded,
    Demand,
    FARM_NEED_MM3,
    Frequency,
    Sink,
    Source,
    TimeSeries,
    WaterConsumed,
    WaterLost,
    WaterOutput,
    WaterSystem,
    consumption,
    efficiency,
    mo,
    monthly,
    need,
    plot_months,
    river,
    wire,
):
    _s = WaterSystem(frequency=Frequency.MONTHLY)
    _s.add_node(Source(id="canal", inflow=TimeSeries(values=list(river * 0.2))))
    _s.add_node(Demand(id="farm", requirement=TimeSeries(values=list(FARM_NEED_MM3)), consumption_fraction=consumption.value / 100, efficiency=efficiency.value / 100))
    _s.add_node(Sink(id="drain"))
    wire(_s, ("canal", "farm"), ("farm", "drain")).simulate(12)
    _f = _s.nodes["farm"]
    _short = monthly(_f, DeficitRecorded, 12, field="deficit")
    mo.vstack(
        [
            plot_months(
                {
                    "consumed after application": monthly(_f, WaterConsumed, 12),
                    "field application loss": monthly(_f, WaterLost, 12),
                    "return flow + unused surplus": monthly(_f, WaterOutput, 12),
                    "short": _short,
                },
                f"Farm: {efficiency.value}% application efficiency; {consumption.value}% of delivery consumed",
                kind="bar",
                stacked=True,
                reference=("the farm's need", need),
            ),
            mo.md(f"**For every 100 m³ withdrawn at the farm:** {100-efficiency.value:.0f} m³ application loss + {efficiency.value*consumption.value/100:.1f} m³ consumed + {efficiency.value*(100-consumption.value)/100:.1f} m³ returned. **Unmet effective-delivery requirement over the year: {_short.sum():,.1f} Mm³.** Changing the consumed share changes return flow, not this delivery shortfall."),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## PassThrough: a turbine with limited capacity

    Here the gate represents a hydropower turbine. Capacity is the maximum monthly volume it can take. This teaching model stops following the bypass spill; a physical bypass would need an explicit downstream route.

    A **PassThrough** is the simplest block with a number: a gate. Water up to its *capacity* goes through; the
    rest is recorded as spilled, and **water above a gate's capacity leaves the books**: TaqSim records it and
    does not follow it further. That is a different kind of spill from the bathtub's overflow, which travels on.
    """)
    return


@app.cell
def _(mo):
    gate = mo.ui.slider(100, 1000, value=600, step=50, label="What the turbine can take, Mm³ per month")
    gate
    return (gate,)


@app.cell
def _(
    Frequency,
    PassThrough,
    Sink,
    Source,
    TimeSeries,
    WaterPassedThrough,
    WaterSpilled,
    WaterSystem,
    gate,
    mo,
    monthly,
    plot_months,
    river,
    wire,
):
    _s = WaterSystem(frequency=Frequency.MONTHLY)
    _s.add_node(Source(id="river", inflow=TimeSeries(values=list(river))))
    _s.add_node(PassThrough(id="turbine", capacity=float(gate.value)))
    _s.add_node(Sink(id="sea"))
    wire(_s, ("river", "turbine"), ("turbine", "sea")).simulate(12)
    _t = _s.nodes["turbine"]
    _past = monthly(_t, WaterSpilled, 12)
    mo.vstack(
        [
            plot_months({"through the gate": monthly(_t, WaterPassedThrough, 12), "spilled past it": _past}, f"A PassThrough: a gate of {gate.value} Mm³ a month", kind="bar", stacked=True),
            mo.md(f"**{_past.sum():,.0f} Mm³** of the river's {river.sum():,.0f} spilled past the gate and left the model."),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## The full example: seven block types, ten blocks

    The river enters a canyon, reaches a headworks that sends a share into a canal and the rest to a turbine on
    the river, the canal feeds the reservoir, the reservoir releases water to the farm, and a separate outlet routes overflow back to the downstream river.
    The outlet Splitter reads the reservoir’s actual release and overflow records; it does not choose a percentage.
    **The valve limit applies only to controlled release to the farm. Overflow bypasses the farm and turbine.**
    The canyon delays water by one month with zero seepage, a simplifying assumption for this example. The valve is the reservoir outlet: its controlled release is limited by farm demand, the slider and available water above dead storage.

    Ten blocks of seven kinds, ten edges, five cards with a number in them: the five knobs below. The system
    runs three years and shows the last one; pick a month to see the water on every edge.
    """)
    return


@app.cell
def _(mo):
    k_share = mo.ui.slider(5, 50, value=20, step=5, label="Headworks rule: share into the canal, %")
    k_seep = mo.ui.slider(0, 20, value=10, step=5, label="Canal rule: seepage, %")
    k_cap = mo.ui.slider(20, 120, value=60, step=20, label="Reservoir: controlled release limit to farm, Mm³ per month")
    k_gate = mo.ui.slider(300, 1000, value=600, step=100, label="Turbine: gate capacity, Mm³ per month")
    k_use = mo.ui.slider(40, 100, value=70, step=10, label="Farm: consumed share of delivered water, %")
    month = mo.ui.dropdown({name: i for i, name in enumerate(["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"])}, value="Jul", label="Show month (display only)")
    mo.vstack([mo.hstack([k_share, k_seep, k_cap], justify="start", gap=2), mo.hstack([k_gate, k_use], justify="start", gap=2), mo.md("Choose a month to inspect the results; this does not change the model."), month])
    return k_cap, k_gate, k_seep, k_share, k_use, month


@app.cell
def _(Knobs, k_cap, k_gate, k_seep, k_share, k_use, simulate_demo):
    knobs = Knobs(canal_share=k_share.value / 100, canal_seepage=k_seep.value / 100, release_cap=float(k_cap.value), turbine_capacity=float(k_gate.value), consumption=k_use.value / 100)
    run = simulate_demo(knobs)
    return (run,)


@app.cell
def _(MONTHS, mo, month, plot_demo_network, run):
    mo.vstack([plot_demo_network(run, month=month.value), mo.md(f"**{MONTHS[month.value]}**: controlled release to the farm **{run.series['reservoir']['released'][month.value]:,.1f} Mm³** (valve limit **{run.knobs.release_cap:,.0f}**); overflow to the river **{run.series['reservoir']['spilled'][month.value]:,.1f} Mm³**. The farm is short by **{run.series['farm']['deficit'][month.value]:,.1f} Mm³**; the reservoir holds **{run.storage_level[month.value]:,.0f}** of 667; **{run.series['turbine']['spilled'][month.value]:,.0f} Mm³** spill past the turbine.")])
    return


@app.cell
def _(plot_where_the_water_went, run):
    plot_where_the_water_went(run)
    return


@app.cell
def _(balance_table, mo, plot_balance, run, system_balance):
    _b = system_balance(run)
    mo.vstack(
        [
            mo.md(
                r"""
                ### Every drop accounted for

                Every block keeps its diary, so for every block we can check: what came in equals what went out, plus
                what was used up, lost, left the model at a gate, or stayed in store. `closes` must be zero on every
                row; the reservoir's `out` includes both controlled release and overflow. The outlet Splitter sends
                release to the farm and overflow to the river; the
                turbine's `left` is water that TaqSim stopped following.
                """
            ),
            mo.ui.table(balance_table(run).round(1), selection=None, pagination=False),
            plot_balance(run),
            mo.md(f"River {_b['river']:,.0f} = sinks {_b['to_sinks']:,.0f} + used {_b['consumed']:,.0f} + lost {_b['lost']:,.0f} + left at the gate {_b['left']:,.0f} + stored {(0.0 if abs(_b['stored']) < 0.5 else _b['stored']):,.0f}"),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## What to notice

    1. **The canyon delays the river by a month.** The July peak reaches the headworks in August.
    2. **Two spills, two meanings.** A full reservoir's overflow returns to the downstream river through its own outlet. A gate's spill leaves the
       books. The diary entry has the same name, `WaterSpilled`; the block it sits in tells you which it is.
    3. **A shortfall can be a rule's doing.** Set the valve to 20 and look at May and June: the farm is short
       while the reservoir holds over 600 Mm³. Before blaming the river, read the rule.
    4. **Efficiency sits between the gate and the need.** Even with a wide valve the farm is a little short,
       because the valve was told the need at the gate and 15 % is lost after it.

    *The same material as a notebook to run in Colab, and as a game page, is on the course site. This page is a
    marimo app: every slider recomputes the cells below it, in TaqSim, as you move it.*
    """)
    return


if __name__ == "__main__":
    app.run()
