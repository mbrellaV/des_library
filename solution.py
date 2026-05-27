
import core
import distributions
import statistics
import random
import math


delta = 0.5
v = 10
alpha = 0.02
y = 60

class Cancelation_event(core.Event):
    def __init__(self, time, order):
        super().__init__(time)
        self.order = order

    def execute(self, sim):
        book.cancel(self.order)

class Limit_order:

    def __init__(self, time: float, price: float, type: bool, id: int):
        # false buy, true sell
        self.id: int = id
        self.arrival_time: float = time
        self.cancelled: bool = False
        self.price = price
        self.type = type

    def cancel(self) -> None:
        self.cancelled = True

    @property
    def active(self) -> bool:
        return not self.cancelled


class Book:

    def __init__(self, time: float):
        self.time: float = time
        self.cancelled: bool = False
        self.bids = []
        self.asks = []
        self.next_id = 0
        self.mid_price = 100


    def insert(self, arrival) -> Limit_order | None:

        if random.uniform(0, 1) < 0.5:
            self.next_id += 1
            new_price = self.mean_price() - distributions.Exponential(delta).sample()
            if new_price <= 0:
                return None
            bid = Limit_order(arrival.time, new_price, False, self.next_id)
            self.bids.append(bid)
            calc_spread()

            return bid
        else:
            self.next_id += 1
            new_price = self.mean_price() + distributions.Exponential(delta).sample()
            if new_price <= 0:
                return None

            ask = Limit_order(arrival.time, new_price, True, self.next_id)

            self.asks.append(ask)
            calc_spread()

            return ask

    def best_bid(self) -> None:

        if len(self.bids) < 1:
            return None
        elif len(self.bids) < 2:
            return self.bids[0]

        best_bid = self.bids[0]


        for bid in self.bids:
            if bid.cancelled:
                continue
            if bid.price > best_bid.price:
                best_bid = bid
        return best_bid

    def best_ask(self) -> None:

        if len(self.asks) < 1:
            return None
        elif len(self.asks) < 2:
            return self.asks[0]

        best_ask = self.asks[0]

        for ask in self.asks:
            if ask.cancelled:
                continue
            if ask.price < best_ask.price:
                best_ask = ask
        return best_ask

    def cancel(self, order) -> None:
        if order is None:
            return  None
        if order.type == False:
            for bid in self.bids:
                if bid.id == order.id:
                    bid.cancel()
                    cancels.increment()
                    self.bids.remove(bid)

        else:
            for ask in self.asks:
                if ask.id == order.id:
                    ask.cancel()
                    cancels.increment()
                    self.asks.remove(ask)
        calc_spread()

    def mean_price(self):
        return self.mid_price

    def trade(self, t):

        ran = alpha * distributions.Exponential(v).sample()
        self.mid_price += ran if t else -ran

        if abs(self.mid_price - 100) > 5:
            self.mid_price -= 0.1 * (self.mid_price - 100)

def arrival(sim):
    if random.uniform(0,1) < 0.7:
        o = book.insert(action)
        if o is not None:
            sim.schedule(Cancelation_event(action.time + distributions.Exponential(y).sample(), o))
    elif random.uniform(0, 1) < 0.5:
        o = book.best_ask()
        if o is not None:
            f.record(action.time - o.arrival_time)
            book.trade(o.type)
            book.asks.remove(o)
            calc_spread()
        else:
            rejects.increment()

    else:
        o = book.best_bid()
        if o is not None:
            f.record(action.time - o.arrival_time)
            book.trade(o.type)
            book.bids.remove(o)
            calc_spread()
        else:
            rejects.increment()

    l0, lmin, beta = 5, 0.5, 0.05
    rate = l0 * math.exp(-beta * (book.mid_price - 100)**2) + lmin
    rate_log.append((action.time, rate))
    action.time += distributions.Exponential(1 / rate).sample()
    sim.schedule(action)

def calc_spread():
    b, a = book.best_bid(), book.best_ask()
    if b is not None and a is not None:
        spread.update(sim.current_time, a.price - b.price)

batch_len = 200
warmup = 1000
batch_f = statistics.SampleStatistic()
batch_spread = statistics.SampleStatistic()
batch_cancels = statistics.SampleStatistic()
batch_rejects = statistics.SampleStatistic()
previous_sum = 0
previous_n = 0
previous_cancels = 0
previous_rejects = 0
previous_accumulated = 0


class Batch(core.Event):
    def execute(self, sim):
        global previous_sum, previous_n, previous_cancels, previous_rejects, previous_accumulated

        if self.time > warmup:

            n = f.count - previous_n
            if n > 0:
                batch_f.record((f.total - previous_sum) / n)

            batch_cancels.record((cancels.value - previous_cancels) / batch_len)
            batch_rejects.record((rejects.value - previous_rejects) / batch_len)
            accumulation = spread.accumulated(self.time)
            batch_spread.record((accumulation - previous_accumulated) / batch_len)

        previous_sum = f.total
        previous_n = f.count
        previous_cancels = cancels.value
        previous_rejects = rejects.value
        previous_accumulated = spread.accumulated(self.time)
        sim.schedule(Batch(self.time+batch_len))


class Sample(core.Event):
    def execute(self, sim):
        mid_log.append(book.mid_price)
        sim.schedule(Sample(self.time + 1))

f = statistics.SampleStatistic()
spread = statistics.TimeWeightedStatistic()
cancels = statistics.Counter()
rejects = statistics.Counter()
rate_log = []
mid_log = []

book = Book(0)

action = core.Event(0.0)
action.execute = arrival
sim = core.Simulation()
sim.schedule(action)
sim.schedule(Batch(batch_len))
sim.schedule(Sample(0))

sim.schedule(core.StopSimulation(100000))

sim.run()


for name, b_stat in [("fill", batch_f), ("cancels", batch_cancels), ("rejects", batch_rejects), ("spread", batch_spread)]:

    mean = b_stat.mean()

    lo, hi =  b_stat.confidence_interval(0.95)
    relation = (hi  - lo) / 2 / abs(mean) if mean  else float("inf")
    print(f"{name} mean: {mean:.3f}, (lo hi):{lo,hi} confidence: {relation:.3f}")

rs = []

for i in range(len(mid_log) -1):
    a, b = mid_log[i], mid_log[i+1]
    if a > 0 and b > 0 and a!=b:
        rs.append(math.log(b / a))

mu = sum(rs) / len(rs)
volatility = math.sqrt(sum((r - mu)**2 for r in rs) / len(rs))
print("volatility: " + str(volatility))




# verify
print("verification block")

def verify(m):
    if m == 1:
        th = 2
    else:
        th = 1.5

    arrival_rate = 0.5
    service_rate = 1

    reps = statistics.SampleStatistic()

    for seed in range(20):
        random.seed(seed)
        q = []
        sj = statistics.SampleStatistic()

        sim_verify =  core.Simulation()

        def nexts():
            return 1 / service_rate if m == 2 else random.expovariate(service_rate)

        class Arrival(core.Event):
            def execute(self, sim):
                empty = not q

                q.append(self.time)

                if empty:
                    sim.schedule(Dep(self.time + nexts()))
                sim.schedule(Arrival(self.time + random.expovariate(arrival_rate)))


        class Dep(core.Event):
            def execute(self, sim):
                sj.record(self.time -  q.pop(0))

                if q:
                    sim.schedule(Dep(self.time + nexts()))

        sim_verify.schedule(Arrival(random.expovariate(arrival_rate)))
        sim_verify.schedule(core.StopSimulation(5000))
        sim_verify.run()
        reps.record(sj.mean())


    lo, hi =  reps.confidence_interval(0.95)
    mod = "V2(M/D/1)" if m == 2 else "V1 (M/M/1)"
    print(f"{mod} sim: {reps.mean():.3f}, (CI):{lo,hi} theory: {th:.3f}")

verify(1)
verify(2)