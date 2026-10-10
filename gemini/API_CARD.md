# TaqSim v0.1.4 API card for this exercise

Copy this card with your prompt. / Передайте эту карточку вместе с запросом.

Use the pinned course release, not a guessed API. / Используйте закреплённую версию курса.

```python
%pip install -q numpy pandas matplotlib networkx ipython deap ctrl-freak
%pip install -q --no-deps "git+https://github.com/hydrosolutions/taqsim.git@v0.1.4"
```

The following is a verified small reference, not a request to run hidden helper code. All values are volumes per monthly step. The reservoir stores inflow, spills excess, then applies losses and release. Its release method sees storage AFTER inflow: do not add inflow again. Overflow and release both go to its downstream node.

Ниже — проверенный небольшой пример. Все значения — объёмы за месячный шаг. Водохранилище принимает приток, сбрасывает избыток, затем учитывает потери и выпуск. Метод выпуска видит запас ПОСЛЕ притока: не прибавляйте приток повторно. Перелив и выпуск поступают в следующий узел.

```python
from dataclasses import dataclass
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display
from taqsim import Demand, Edge, Frequency, Sink, Source, Splitter, Storage, Strategy, TimeSeries, Timestep, WaterSystem
from taqsim.node import NoLoss, WaterConsumed, WaterReceived, WaterReleased, WaterSpilled, DeficitRecorded

INFLOW = [8.0, 4.0, 2.0, 0.0, 10.0, 2.0]
INITIAL_STORAGE = 6.0
CAPACITY = 20.0
NEED_A = 4.0
NEED_B = 3.0
SHARE_A = NEED_A / (NEED_A + NEED_B)


@dataclass(frozen=True)
class ReleaseNeed(Strategy):
    __params__ = ()
    need: float

    def release(self, node: Storage, inflow: float, t: Timestep) -> float:
        # In TaqSim 0.1.4 this month's inflow is already stored at this point.
        return min(self.need, max(0.0, node.storage - node.dead_storage))


@dataclass(frozen=True)
class ShareWater(Strategy):
    __params__ = ("share_a",)
    __bounds__ = {"share_a": (0.0, 1.0)}
    share_a: float

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        return {"farm_a": amount * self.share_a, "farm_b": amount * (1.0 - self.share_a)}


def build_model(share_a: float = SHARE_A) -> WaterSystem:
    """Build a fresh six-month teaching model for one allocation rule."""
    if not 0.0 <= share_a <= 1.0:
        raise ValueError("share_a must be between 0 and 1")
    model = WaterSystem(frequency=Frequency.MONTHLY)
    model.add_node(Source(id="river", inflow=TimeSeries(values=INFLOW)))
    model.add_node(Storage(id="reservoir", capacity=CAPACITY, initial_storage=INITIAL_STORAGE,
                           dead_storage=0.0, release_policy=ReleaseNeed(NEED_A + NEED_B), loss_rule=NoLoss()))
    model.add_node(Splitter(id="allocation", split_policy=ShareWater(share_a)))
    model.add_node(Demand(id="farm_a", requirement=TimeSeries(values=[NEED_A] * len(INFLOW)),
                          consumption_fraction=1.0, efficiency=1.0))
    model.add_node(Demand(id="farm_b", requirement=TimeSeries(values=[NEED_B] * len(INFLOW)),
                          consumption_fraction=1.0, efficiency=1.0))
    model.add_node(Sink(id="downstream"))
    for source, target in [("river", "reservoir"), ("reservoir", "allocation"),
                           ("allocation", "farm_a"), ("allocation", "farm_b"),
                           ("farm_a", "downstream"), ("farm_b", "downstream")]:
        model.add_edge(Edge(id=f"{source}_to_{target}", source=source, target=target))
    model.validate()
    return model

```

Run with `model = build_model(); model.simulate(6)`. Construct a fresh model for each comparison. `model.validate()` checks network structure; it does not prove the meaning of the rules.

Для сравнения создавайте новую модель. `model.validate()` проверяет структуру сети, но не смысл правил.

Read events using their correct fields:

```python
release = model.nodes["reservoir"].trace(WaterReleased)
month_1_release = release.get(0, 0.0)
shortage = model.nodes["farm_a"].trace(DeficitRecorded, field="deficit")
month_1_shortage = shortage.get(0, 0.0)
```

`WaterConsumed`, `WaterReceived`, `WaterReleased` and `WaterSpilled` use field `amount`; `DeficitRecorded` uses `deficit`. Missing trace timesteps mean zero for these monthly sums; use `.get(t, 0.0)`. Split dictionaries are keyed by downstream NODE IDs, not edge IDs. The shares must sum to one. This exercise uses `NoLoss()`; do not introduce losses without updating the water balance. The rescue notebook contains the full reporting and checks.

События дефицита используют поле `deficit`, остальные перечисленные события — `amount`. Ключи распределения — имена следующих узлов, не рёбер. Сумма долей должна быть единицей. Не добавляйте потери без изменения баланса. Полные проверки приведены в резервном блокноте.
