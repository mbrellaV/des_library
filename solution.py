
import core
import distributions
import statistics
import random


delta = 1

class limit_order:

    def __init__(self, time: float, price: float, type: bool, id: int):
        # false buy, true sell
        self.id: int = id
        self.arrival_time: float = time
        self.cancelled: bool = False
        self.price = float = price
        self.type = type

    def cancel(self) -> None:
        self.cancelled = True

    @property
    def active(self) -> bool:
        return not self.cancelled


class book:

    def __init__(self, time: float):
        self.time: float = time
        self.cancelled: bool = False
        self.bids = []
        self.asks = []
        self.next_id = 0


    def insert(self, arrival) -> limit_order:


        if random.uniform(0, 1) < 0.5:
            self.next_id += 1
            new_price = self.mean_price() - distributions.Exponential(delta).sample()
            if new_price <= 0:
                return arrival
            bid = limit_order(arrival.time, new_price, False, self.next_id)
            self.bids.append(bid)
            return bid
        else:
            self.next_id += 1
            new_price = self.mean_price() + distributions.Exponential(delta).sample()
            if new_price <= 0:
                return arrival

            ask = limit_order(arrival.time, new_price, True, self.next_id)

            self.asks.append(ask)

            return ask

    def best_bid(self) -> None:
        i=0
        while i < len(self.bids) - 1:
            if self.bids[i].cancelled:
                continue
            else:
                best_bid = self.bids[i]
            i += 1
        for bid in self.bids:
            if bid.cancelled:
                continue
            if bid.price > best_bid.price:
                best_bid = bid
        return best_bid

    def best_ask(self) -> None:

        i=0
        while i < len(self.asks) - 1:
            if self.asks[i].cancelled:
                continue
            else:
                best_ask = self.asks[i]
            i += 1

        for ask in self.asks:
            if ask.cancelled:
                continue
            if ask.price < best_ask.price:
                best_ask = ask
        return best_ask

    def cancel(self, limit_order: limit_order) -> None:
        if limit_order.type == False:
            for bid in self.bids:
                if bid.id == limit_order.id:
                    bid.cancel()
                    self.bids.remove(bid)

        else:
            for ask in self.asks:
                if ask.id == limit_order.id:
                    ask.cancel()
                    self.asks.remove(ask)

    def mean_price(self):
        return 100


def scan(sim):
    wait = max(0.0, taken[0] - event.time)
    taken[0] = event.time + wait + distributions.Exponential(1).sample()
    s.record(wait)

    # event.time += random.expovariate(0.9)
    event.time += distributions.Exponential(1.1).sample()
    sim.schedule(event)

# simulation = core.Simulation()
taken = [0.0]
s = statistics.SampleStatistic()
event = core.Event(0.0)
event.execute = scan

sim = core.Simulation()
sim.schedule(event)
sim.schedule(core.StopSimulation(1000000))

sim.run()

print("mean - " + str(s.mean()))
print(s.variance())
