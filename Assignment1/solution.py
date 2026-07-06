import core
import statistics
import random
import math

random.seed(1)

class CancelEvent(core.Event):
    def __init__(self, time, order, book):
        super().__init__(time)
        self.order = order
        self.book = book

    def execute(self, sim):
        self.book.cancel(self.order)
        self.book.match(sim.current_time)

class LimitOrder:
    def __init__(self, time: float, price: float, type: bool, id: int):
        # false buy, true sell
        self.id: int = id
        self.arrival_time: float = time
        self.cancelled: bool = False
        self.price = price
        self.type = type
        self.cancel_event = None

    def cancel(self) -> None:
        self.cancelled = True
        self.cancel_event.cancel()

    @property
    def active(self) -> bool:
        return not self.cancelled


class Book:

    def __init__(self, time: float, sim):
        self.time: float = time
        self.cancelled: bool = False
        self.bids = []
        self.asks = []
        self.next_id = 0
        self.cancels = 0
        self.limit_count = 0
        self.rejects = statistics.Counter()
        self.spread = statistics.TimeWeightedStatistic()
        self.spread_defined = statistics.TimeWeightedStatistic()

        self.time_to_fill = statistics.SampleStatistic()
        self.ask_length = statistics.TimeWeightedStatistic()
        self.bid_length = statistics.TimeWeightedStatistic()

        self.trade_count = statistics.Counter()

        self.sim = sim


    def insert(self, arrival,n):
        if random.uniform(0, 1) < 0.5:
            self.next_id += 1
            new_price = round(100 + 2 * math.sin(n * math.e), 2)
            obj = LimitOrder(arrival.time, new_price, False, self.next_id)
            self.limit_count += 1
            self.bids.append(obj)
        else:
            self.next_id += 1
            new_price = round(100 + 2 * math.sin(n * math.e), 2)

            obj = LimitOrder(arrival.time, new_price, True, self.next_id)
            self.limit_count+=1
            self.asks.append(obj)

        self.calculate_spread(self.sim)
        return obj


    def best_bid(self) -> None:

        if len(self.bids) < 1:
            return None
        elif len(self.bids) < 2:
            return self.bids[0]

        best_bid = self.bids[0]

        for bid in self.bids:
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
            if ask.price < best_ask.price:
                best_ask = ask
        return best_ask

    def cancel(self, order):
        if order.type == False:
            for bid in self.bids:
                if bid.id == order.id:
                    bid.cancel()
                    self.cancels += 1
                    self.bids.remove(bid)

        else:
            for ask in self.asks:
                if ask.id == order.id:
                    ask.cancel()
                    self.cancels += 1
                    self.asks.remove(ask)

        self.calculate_spread(self.sim)

    def match(self, time_now):
        bid = self.best_bid()
        ask = self.best_ask()
        if bid is None or ask is None or bid.price < ask.price:
            return

        self.time_to_fill.record(time_now - bid.arrival_time)
        self.time_to_fill.record(time_now - ask.arrival_time)
        self.asks.remove(ask)
        self.bids.remove(bid)
        self.trade_count.increment(1)
        ask.cancel()
        bid.cancel()
        self.calculate_spread(self.sim)

        self.check_stop_condition()

        return None

    def check_stop_condition(self):
        if self.trade_count.value >= 500:
            self.sim.stop()

    def calculate_spread(self, sim):
        b, a = self.best_bid(), self.best_ask()

        if b is not None and a is not None:
            self.spread.update(sim.current_time, a.price - b.price)
            self.ask_length.update(sim.current_time, len(self.asks))
            self.bid_length.update(sim.current_time, len(self.bids))
            self.spread_defined.update(sim.current_time, 1)
        else:
            self.spread.update(sim.current_time, 0)
            self.ask_length.update(sim.current_time, len(self.asks))
            self.bid_length.update(sim.current_time, len(self.bids))
            self.spread_defined.update(sim.current_time, 0)

class ArrivalEvent(core.Event):
    def __init__(self, time: float, book, n):
        super().__init__(time)
        self.n = n
        self.book = book

    def execute(self, sim):
        if random.uniform(0, 1) < 0.7:
            order = self.book.insert(self,self.n)
            if order is not None:

                order.cancel_event = CancelEvent(self.time + (30 * (1 + (math.cos(self.n)) ** 2)),
                                order, self.book)
                sim.schedule(order.cancel_event)
                self.book.match(sim.current_time)

        elif random.uniform(0, 1) < 0.5:
            order = self.book.best_ask()
            if order is not None:
                self.book.time_to_fill.record(self.time - order.arrival_time)
                self.book.asks.remove(order)
                order.cancel()
                self.book.trade_count.increment(1)
                self.book.check_stop_condition()
                self.book.calculate_spread(sim)
            else:
                self.book.rejects.increment()

        else:
            order = self.book.best_bid()
            if order is not None:
                self.book.time_to_fill.record(self.time - order.arrival_time)
                order.cancel()
                self.book.bids.remove(order)
                self.book.trade_count.increment(1)
                self.book.calculate_spread(sim)
                self.book.check_stop_condition()


            else:
                self.book.rejects.increment()

        self.time += 5 * (1 + abs(math.sin(math.pi * self.n / 3)))
        sim.schedule(ArrivalEvent(self.time, self.book, self.n+1))

def run():
    sim = core.Simulation()

    book = Book(0, sim)

    start_action = ArrivalEvent(0, book, 0)
    sim.schedule(start_action)

    sim.schedule(core.StopSimulation(100000))

    sim.run()

    T = sim.current_time

    print("T", T)
    print("spread", book.spread.accumulated(T) / book.spread_defined.accumulated(T))
    print("time to fill", book.time_to_fill.mean())
    print("cancel fraction", book.cancels / book.limit_count)
    print("bid queue", book.bid_length.mean(T))
    print("ask queue", book.ask_length.mean(T))
    print("reject queue", book.rejects.value)


if __name__ == "__main__":
    run()