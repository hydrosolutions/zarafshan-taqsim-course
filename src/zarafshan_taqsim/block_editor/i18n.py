"""The editor's words. Block ids, kind names and code stay English in every language (LANGUAGE_COVERAGE.md)."""

from __future__ import annotations

EN: dict[str, str] = {
    # --- the frame
    "ui.blocks": "Blocks: drag one onto the canvas, or click it",
    "ui.blocks_hint": "Drag a block onto the canvas, or click it.",
    "ui.connect_hint": "To connect two blocks, drag from the dot on the right of one block to the next block. On a phone: tap the dot, then tap the next block.",
    "ui.settings": "Settings",
    "ui.nothing_selected": "Click a block to see its numbers.",
    "ui.no_settings": "This block has no numbers to set.",
    "ui.edge_selected": "A connection is selected.",
    "ui.remove": "Remove",
    "ui.rule": "Its rule: rationing",
    "ui.result": "What TaqSim calculated",
    "ui.next": "Next step",
    "ui.back": "Back",
    "ui.show_me": "Build it for me",
    "ui.start_over": "Clear the canvas",
    "ui.show_code": "Show the Python code",
    "ui.hide_code": "Hide the Python code",
    "ui.code_about": "This is what your drawing looks like as TaqSim code. You do not need it for this exercise.",
    "ui.working": "TaqSim is calculating 100 years…",
    "ui.step_of": "Step {n} of {total}",
    "ui.done": "Done",
    "ui.last_step": "This is the last step that is ready. More steps follow.",
    # --- blocks
    "block.river": "River",
    "block.reservoir": "Reservoir",
    "block.farm": "Farm",
    "block.downstream": "Outlet",
    "about.river": "Brings water every month: 100 years of river flow, low in winter, high in summer.",
    "about.reservoir": "Stores water, and releases what its rule says.",
    "about.farm": "Asks for water every month and records what it did not get.",
    "about.downstream": "Takes the water that is left.",
    # --- sliders
    "field.summer_need": "Summer need",
    "field.winter_need": "Winter need",
    "field.capacity": "Capacity",
    "field.initial_storage": "Water at the start",
    "field.trigger": "Trigger",
    "field.ration": "Ration",
    "help.summer_need": "What the farm asks for over the six summer months.",
    "help.winter_need": "What the farm asks for over the six winter months.",
    "help.capacity": "How much water the reservoir can hold.",
    "help.initial_storage": "How full the reservoir is in the first month.",
    "help.trigger": "In summer, when the reservoir holds less than this, the farm gets only the ration.",
    "help.ration": "The share of its need the farm gets while water is rationed. 100 % means no rationing.",
    # --- steps
    "step.river_farm.title": "A river and a farm",
    "step.river_farm.body": "A TaqSim model is made of <b>blocks</b> and the <b>connections</b> between them. Water moves along the connections, from left to right. We start with the smallest system that has a problem: a river, a farm that takes water from it, and an outlet for what is left.",
    "step.river_farm.task": "Put the three blocks on the canvas and connect them: River → Farm → Outlet.",
    "step.river_farm.done": "The model runs. Look at the result below, then go to the next step.",
    "step.reservoir.title": "Add a reservoir",
    "step.reservoir.body": "The farm is short of water in most years. The river brings enough over the year, but at the wrong time: much of it arrives in winter, when the farm needs little. A <b>reservoir</b> can keep winter water for the summer.",
    "step.reservoir.task": "Add the Reservoir between the River and the Farm: River → Reservoir → Farm → Outlet. Tip: drop it on the connection.",
    "step.reservoir.done": "The reservoir is in place. Try a larger or smaller capacity, then go on.",
    "step.rationing.title": "Ration before the reservoir is empty",
    "step.rationing.body": "So far the reservoir gives the farm everything it asks for until it is empty. Then the farm gets almost nothing. A <b>rationing rule</b> starts saving earlier: in summer, when the reservoir holds less than the <b>trigger</b>, the farm gets only the <b>ration</b>, a share of its need.",
    "step.rationing.task": "Click the Reservoir and set its rule: a trigger above 0 and a ration below 100 %. Then try other values and watch the three scores.",
    "step.rationing.done": "Your rule is running. There is no best plan here: a deeper cut makes the worst month milder but takes more water from the farm on average.",
    # --- hints and problems
    "hint.add_block": "Add the block “{block}” from the list on the left.",
    "hint.river_farm": "Connect the blocks in this order: River → Farm → Outlet.",
    "hint.reservoir": "The water must pass through the reservoir: River → Reservoir → Farm → Outlet.",
    "hint.rationing": "Keep the chain River → Reservoir → Farm → Outlet for this step.",
    "hint.set_rule": "Click the Reservoir and move “Trigger” above 0 and “Ration” below 100 %.",
    "problem.empty": "The canvas is empty. Start with the River.",
    "problem.no_source": "The model needs a block that brings water: add the River.",
    "problem.no_sink": "The model needs a block where the water ends: add the Outlet.",
    "problem.no_way_out": "“{block}” is not connected to a next block. Drag from the dot on its right side.",
    "problem.no_way_in": "No water reaches “{block}” yet. Connect another block to it.",
    "problem.taqsim": "TaqSim cannot run this network: {error}",
    # --- results
    "card.mean_shortage": "Average shortage per year",
    "card.worst_month": "Worst month",
    "card.years_short": "Years with a shortage",
    "card.of_years": "{n} of {years}",
    "card.spilled": "Spilled per year",
    "label.yours": "Your plan",
    "label.before": "without reservoir",
    "label.in_full_short": "no rationing",
    "label.no_reservoir": "River and farm, no reservoir",
    "label.with_reservoir": "With a reservoir of {capacity:g} Mm³, delivered in full until empty",
    "label.in_full": "Deliver in full until empty",
    "label.plan": "below {trigger:g} Mm³, deliver {ration:.0f} %",
    "note.river_farm": "Each bar is one year: its worst month, as the share of that month’s need the farm did not get. The farm asks for {need:g} Mm³ a year and misses <b>{missed:.1f}</b> of them on average; it is short in <b>{short} of {years} years</b>. The reason is timing, not a lack of water: the farm needs {summer:g} Mm³ in summer, and the winter water flows past it unused.",
    "note.reservoir": "The reservoir of {capacity:g} Mm³ carries winter water into summer. Years with a shortage fall from {a_short} to <b>{b_short}</b>, the water missed from {a_missed:.1f} to <b>{b_missed:.1f} Mm³ a year</b>. But when the reservoir does run empty the farm gets very little: the worst month is still <b>{worst:.0f} %</b> short. <b>{spilled:.1f} Mm³</b> a year spill because the reservoir is full; that water passes the farm and leaves at the outlet.",
    "note.rationing": "Left: the worst month of each year. Right: the water in the reservoir during the worst drought; the dashed line is your trigger. With your rule the worst month goes from {a_worst:.0f} % to <b>{b_worst:.0f} %</b> short, and the average shortage from {a_missed:.1f} to <b>{b_missed:.1f} Mm³ a year</b>. The lowest the reservoir gets is {lowest:.1f} Mm³.",
}

WORDS: dict[str, dict[str, str]] = {"en": EN}


def t(lang: str, key: str, **blanks) -> str:
    """The text for `key` in `lang` (English if that language does not have it yet), with its blanks filled."""
    text = WORDS.get(lang, EN).get(key) or EN.get(key, key)
    return text.format(**blanks) if blanks else text
