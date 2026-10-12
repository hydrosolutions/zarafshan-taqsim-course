# Карточка API TaqSim v0.1.4 для упражнения

Скопируйте эту карточку вместе с запросом. Используйте закреплённую версию курса, а не предполагаемый API.

```python
%pip install -q numpy pandas matplotlib networkx ipython deap ctrl-freak
%pip install -q --no-deps "git+https://github.com/hydrosolutions/taqsim.git@v0.1.4"
```

Ниже — проверенный небольшой пример, а не предложение запускать скрытые вспомогательные функции. Все значения — объёмы за месячный шаг. Водохранилище принимает приток, сбрасывает избыток, затем учитывает потери и выпуск. Метод выпуска видит запас ПОСЛЕ притока: не прибавляйте приток повторно. Перелив и выпуск поступают в следующий узел.

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
        # В TaqSim 0.1.4 приток текущего месяца в этот момент уже включён в запас.
        return min(self.need, max(0.0, node.storage - node.dead_storage))


@dataclass(frozen=True)
class ShareWater(Strategy):
    __params__ = ("share_a",)
    __bounds__ = {"share_a": (0.0, 1.0)}
    share_a: float

    def split(self, node: Splitter, amount: float, t: Timestep) -> dict[str, float]:
        return {"farm_a": amount * self.share_a, "farm_b": amount * (1.0 - self.share_a)}


def build_model(share_a: float = SHARE_A) -> WaterSystem:
    """Создать новую шестимесячную учебную модель для одного правила распределения."""
    if not 0.0 <= share_a <= 1.0:
        raise ValueError("share_a должна быть от 0 до 1")
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

Запуск: `model = build_model(); model.simulate(6)`. Для каждого сравнения создавайте новую модель. `model.validate()` проверяет структуру сети, но не правильность смысла правил.

Читайте события с правильными именами полей:

```python
release = model.nodes["reservoir"].trace(WaterReleased)
month_1_release = release.get(0, 0.0)
shortage = model.nodes["farm_a"].trace(DeficitRecorded, field="deficit")
month_1_shortage = shortage.get(0, 0.0)
```

События `WaterConsumed`, `WaterReceived`, `WaterReleased` и `WaterSpilled` используют поле `amount`; `DeficitRecorded` — `deficit`. Отсутствие шага в журнале означает ноль для этих месячных сумм; используйте `.get(t, 0.0)`. Ключи словаря распределения — ID нижележащих УЗЛОВ, а не рёбер. Доли должны давать в сумме единицу. В упражнении используется `NoLoss()`; не добавляйте потери без изменения баланса. Полные отчёты и проверки приведены в резервном блокноте.
