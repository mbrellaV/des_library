
import core
import distributions
import statistics
import random


delta = 0.5
v = 1
n = 0.1
y = 60

class Cancelation_event(core.Event):
    def __init__(self, time, order):
        super().__init__(time)
        self.order = order

    def execute(self, sim):
        book.cancel(self.order)

class limit_order:

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


    def insert(self, arrival) -> limit_order | None:


        if random.uniform(0, 1) < 0.5:
            self.next_id += 1
            new_price = self.mean_price() - distributions.Exponential(delta).sample()
            if new_price <= 0:
                return None
            bid = limit_order(arrival.time, new_price, False, self.next_id)
            self.bids.append(bid)
            return bid
        else:
            self.next_id += 1
            new_price = self.mean_price() + distributions.Exponential(delta).sample()
            if new_price <= 0:
                return None

            ask = limit_order(arrival.time, new_price, True, self.next_id)

            self.asks.append(ask)

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
                    self.bids.remove(bid)

        else:
            for ask in self.asks:
                if ask.id == order.id:
                    ask.cancel()
                    self.asks.remove(ask)

    def mean_price(self):
        return self.mid_price

    def contains(self, e):
        for bid in self.bids:
            if bid.id == e.id:
                return True
        for ask in self.asks:
            if ask.id == e.id:
                return True
        return False

def arrival(sim):
    if random.uniform(0,1) < 0.7:
        o = book.insert(action)
        if o is not None:
            sim.schedule(Cancelation_event(action.time + distributions.Exponential(y).sample(), o))
    elif random.uniform(0, 1) < 0.5:
        o = book.best_ask()
        if o is not None:
            book.asks.remove(o)
    else:
        o = book.best_bid()
        if o is not None:
            book.bids.remove(o)

    # wait = max(0.0, taken[0] - event.time)
    # taken[0] = event.time + wait + distributions.Exponential(1).sample()
    # s.record(wait)

    # event.time += random.expovariate(0.9)
    # event.time += distributions.Exponential(1.1).sample()
    # sim.schedule(event)

    action.time += distributions.Exponential(1).sample()
    sim.schedule(action)



s = statistics.SampleStatistic()


book = Book(0)

action = core.Event(0.0)
action.execute = arrival
sim = core.Simulation()
sim.schedule(action)

sim.schedule(core.StopSimulation(10000))

sim.run()

print("mean - " + str(s.mean()))
print(s.variance())