import core
import distributions
import statistics
import random


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
