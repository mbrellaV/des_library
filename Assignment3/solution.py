import math
import core
import distributions
import statistics
import random

random.seed(1)

cost_inpatient= 200
cost_outpatient = 10
profit_outpatient = 100
profit_inpatient = 20

pe = 0.25
pi = 0.65
ps = 0.84
wo = 1.5
wi = 0

rate_base_in = 6 / (16*60)

rate_peak_in = (21 - rate_base_in * 480) / (720 / math.pi)

SHOW_PR_OUTPATIENT = 0.84

FULL_DAY = (8*60, 16*60)
MAX_SCAN_TIME = 19

mean_emergency = 60

def day_time(t):
    return t % (24*60)

def is_weekday(dayw):
    return dayw % 7 < 5

def inpatient_rate_at_time(t):
    td = t % (24 * 60)

    if is_weekday(int(t // (24 * 60))) and 9 * 60 <= td < 15 * 60:
        return rate_base_in + rate_peak_in * abs(math.sin(math.pi * (td - 9 * 60) / 180))

    return rate_base_in


def next_call_time(t):
    tn = t + distributions.Exponential((FULL_DAY[1] - FULL_DAY[0]) / 23).sample()

    while True:
        dayc = int(tn // (24*60))
        td = tn - dayc*(24*60)
        if not is_weekday(dayc) or td >= FULL_DAY[1]:
            tn = (dayc + 1) * 24*60 + FULL_DAY[0]
        elif td < FULL_DAY[0]:
            tn = dayc * 24 * 60 + FULL_DAY[0]
        else:
            return tn


class Booking:
    def __init__(self, reservation_table, blueprint, ndays, warmup):
        self.warmup = warmup
        slot_times = []

        for ih, openh in enumerate(reservation_table):
            if openh:
                slot_times.append(FULL_DAY[0] + ih * 15)

        layers = [list(slot_times)]

        for dp in blueprint:
            if dp:
                layers.append([t for t in slot_times if dp[0] <= t < dp[1]])

        base = list(slot_times)

        self.calendar = {}

        for da in range(ndays):
            self.calendar[da] = list(base) if is_weekday(da) else []

        self.waiting_list = []
        self.access = statistics.SampleStatistic()

    def take(self, dayf, call_day, dept, simulation):
        t = self.calendar[dayf].pop(0)
        simulation.schedule(OutpatientAppointment(dayf  * (24*60) + t, dept))

        if call_day * (24 * 60) >= self.warmup:
            self.access.record(dayf - call_day)


    def assign(self, call_day, dept, simulation):
        sat = (call_day // 7) * 7 + 5

        for dn in range(call_day + 1, sat):
            if self.calendar.get(dn):
                self.take(dn, call_day, dept, simulation)
                return

        self.waiting_list.append(call_day)

    def friday_check(self, dayfr, dept, simulation):
        nxt = (dayfr // 7 + 1) * 7
        wt = []

        for calld in self.waiting_list:
            for dn in range(nxt, nxt + 5):
                if self.calendar.get(dn):
                    self.take(dn, calld, dept,simulation)
                    break
            else:
                wt.append(calld)

        self.waiting_list = wt

class FridayPlan(core.Event):
    def __init__(self, time, dept, booking):
        super().__init__(time)
        self.dept = dept
        self.booking = booking

    def execute(self, simulation):
        self.booking.friday_check(int(self.time // (60 * 24)), self.dept, simulation)
        simulation.schedule(FridayPlan(self.time  + 7 * 24*60, self.dept, self.booking))

class OutpatientCall(core.Event):
    def __init__(self, time, dept, booking):
        super().__init__(time)
        self.dept = dept
        self.booking = booking

    def execute(self, simulation):
        self.booking.assign(int(self.time // (60*24)), self.dept, simulation)
        simulation.schedule(OutpatientCall(next_call_time(self.time), self.dept, self.booking))


class Patient:
    def __init__(self, request_time: float, arrival_time: float, scheduled_time, kind):
        self.request_time = request_time
        self.arrival_time = arrival_time
        self.scheduled_time = scheduled_time
        self.kind = kind

class Scanner:
    def __init__(self, id, always_open):
        self.id = id
        self.close_time = None
        self.busy = False
        self.always_open = always_open
        self.open = always_open

class Department:
    def __init__(self, simulation, scanners):
        self.simulation = simulation
        self.scanners = scanners
        self.emergency = []
        self.inpatients = []
        self.outpatients = []
        self.busy_count = 0
        self.inpatient_requests = []
        self.inpatient_transit = False
        self.inpatient_late = 0
        self.inpatient_total_during_office = 0

        self.number_under = 0
        self.total_scanned = 0
        self.wait_emergency = statistics.SampleStatistic()
        self.wait_outpatient = statistics.SampleStatistic()
        self.patients_outside_room = 0
        self.total_arrivals = 0
        self.last_time_update = 0
        self.busy_time_office = 0
        self.busy_time_outside_office = 0
        self.free_time_office = 0
        self.free_time_outside_office = 0



        self.utilization = statistics.TimeWeightedStatistic()
        self.wait = statistics.SampleStatistic()
        self.scanned = 0

    def free_scanner(self, time_now):
        for s in self.scanners:
            if not s.open or s.busy:
                continue

            if s.always_open or time_now + MAX_SCAN_TIME <= s.close_time:
                return s

        return None


    def choose_next(self):
        if self.emergency:
            return self.emergency.pop(0)

        candidates = []

        if self.inpatients:
            candidates.append((self.inpatients[0].arrival_time, "i"))

        if self.outpatients:
            candidates.append((self.outpatients[0].arrival_time, "o"))

        if not candidates:
            return None

        candidates.sort()

        if candidates[0][1] == "i":
            return self.inpatients.pop(0)
        else:
            return self.outpatients.pop(0)

    def admit(self, time_now, patient, q):
        if time_now >= 24*60:
            self.total_arrivals += 1
            if len(self.emergency) + len(self.inpatients) + len(self.outpatients) >= 3:
                self.patients_outside_room += 1

        q.append(patient)
        self.start_scan(time_now)

        return None

    def start_scan(self, time_now):

        while True:
            s = self.free_scanner(time_now)
            if s is None:
                return

            patient = self.choose_next()

            if patient is None:
                return

            s.busy = True
            self.record_busy(time_now)
            self.busy_count += 1
            self.utilization.update(time_now, self.busy_count)
            self.record(time_now, patient)

            self.simulation.schedule(ScanCompletion(time_now +
                distributions.Uniform(10,19).sample(), self, s, patient))

            if patient.kind == "inpatient":
                self.call_inpatient(time_now)


    def call_inpatient(self, time_now):
        if self.inpatient_requests and not self.inpatient_transit and not self.inpatients:
            request_time = self.inpatient_requests.pop(0)
            self.inpatient_transit = True
            self.simulation.schedule(InpatientArrival(
                time_now + distributions.Uniform(9, 15).sample(), self, request_time))


    def record(self, time_now, patient):
        self.wait.record(time_now - patient.arrival_time)
        if time_now < 24 * 60:
            return

        waiting_time = time_now - patient.arrival_time

        if patient.kind == "emergency":
            self.wait_emergency.record(waiting_time)
        elif patient.kind == "outpatient":
            self.wait_outpatient.record(waiting_time)


        if patient.kind == "inpatient":
            req = patient.request_time
            req_t = req % (24 * 60)
            if is_weekday(int(req // (24 * 60))) and FULL_DAY[0] <= req_t < FULL_DAY[1]:
                self.inpatient_total_during_office += 1

                same_day = int(req // (24 * 60)) == int(time_now // (24 * 60))

                in_office_hours = (time_now % (24 * 60)) < FULL_DAY[1]
                if not (same_day and in_office_hours):
                    self.inpatient_late += 1

        self.scanned += 1
        if time_now - patient.arrival_time < 20:
            self.number_under += 1
        self.total_scanned += 1

    def record_busy(self, time_now):
        dt = time_now - self.last_time_update
        minute = day_time(self.last_time_update)

        open_scanners = 0
        for s in self.scanners:
            if s.open:
                open_scanners+=1

        if is_weekday(int(self.last_time_update // (24*60))) and FULL_DAY[0] <= minute < FULL_DAY[1]:
            self.busy_time_office += self.busy_count * dt
            self.free_time_office += open_scanners * dt
        else:
            self.busy_time_outside_office += self.busy_count * dt
            self.free_time_outside_office += open_scanners * dt

        self.last_time_update = time_now

class EmergencyArrival(core.Event):
    def __init__(self, time, dept):
        super().__init__(time)
        self.dept = dept

    def execute(self, simulation):
        patient = Patient(self.time, self.time, scheduled_time=None, kind="emergency")
        self.dept.admit(self.time, patient, self.dept.emergency)

        next = self.time + distributions.Exponential(mean_emergency).sample()
        simulation.schedule(EmergencyArrival(next, self.dept))


class InpatientRequest(core.Event):

    def __init__(self, time, dept):
        super().__init__(time)
        self.dept = dept

    def execute(self, simulation):
        if random.random() < inpatient_rate_at_time(self.time) / (rate_base_in+rate_peak_in):
            self.dept.inpatient_requests.append(self.time)
            self.dept.call_inpatient(self.time)

        next_action = distributions.Exponential(1 / (rate_base_in+rate_peak_in)).sample()
        simulation.schedule(InpatientRequest(self.time + next_action, self.dept))


class OpenScanner(core.Event):
    def __init__(self, time, model, scanner, close_time):
        super().__init__(time)
        self.model = model
        self.scanner = scanner
        self.close_time = close_time


    def execute(self, simulation):
        self.model.record_busy(self.time)
        self.scanner.open = True
        self.scanner.close_time = self.close_time

class CloseScanner(core.Event):
    def __init__(self, time, model, scanner, close_time):
        super().__init__(time)
        self.model = model
        self.scanner = scanner

    def execute(self, simulation):
        self.model.record_busy(self.time)

        if not self.scanner.always_open:
            self.scanner.open = False


class InpatientArrival(core.Event):
    def __init__(self, time, dept,request_time):
        super().__init__(time)
        self.dept = dept
        self.request_time = request_time


    def execute(self, simulation):
        self.dept.inpatient_transit = False
        patient = Patient(self.request_time, self.time, scheduled_time=None, kind="inpatient")
        self.dept.admit(self.time, patient, self.dept.inpatients)


class OutpatientAppointment(core.Event):
    def __init__(self, time, dept):
        super().__init__(time)
        self.dept = dept

    def execute(self, simulation):
        if random.uniform(0,1) < SHOW_PR_OUTPATIENT:
            patient = Patient(self.time, self.time, scheduled_time=None, kind="outpatient")
            self.dept.admit(self.time, patient, self.dept.outpatients)


class ScanCompletion(core.Event):
    def __init__(self, time, dept, scanner, patient):
        super().__init__(time)
        self.time = time
        self.dept = dept
        self.scanner = scanner
        self.patient = patient

    def execute(self, sim):
        self.scanner.busy = False
        self.dept.record_busy(self.time)

        self.dept.busy_count -= 1
        self.dept.utilization.update(self.time, self.dept.busy_count)
        self.dept.start_scan(self.time)

def run(blueprint):
    outpatients_table = [1] * 16 + [1,1,1,0] * 4

    utilization_in_office_hours = []
    utilization_in_outside_hours = []
    wait_emergency_means = []
    wait_outpatient_means = []
    fraction_outside_room = []

    # //
    N_DAYS = 7 * 10
    n_sim = 100

    ma = []
    scanned = []
    wait = []
    uti = []
    interval = []
    inps = []

    for s in range(n_sim):
        random.seed(s)
        sim = core.Simulation()

        scanners = [Scanner(0, always_open=True), Scanner(1, always_open=False)]

        d = Department(sim, scanners)

        for day in range(N_DAYS):
            if not is_weekday(day):
                continue

            base = day * 24 * 60

            sim.schedule(OpenScanner(base + FULL_DAY[0], d, scanners[1], base + FULL_DAY[1]))
            sim.schedule(CloseScanner(base + FULL_DAY[1], d, scanners[1], base + FULL_DAY[1]))

        sim.schedule(EmergencyArrival(0, d))
        sim.schedule(InpatientRequest(FULL_DAY[0], d))

        booking = Booking(outpatients_table, blueprint=blueprint, ndays=N_DAYS, warmup=24 * 60)
        sim.schedule(OutpatientCall(next_call_time(0), d, booking))
        sim.schedule(FridayPlan(4 * 24 * 60 + FULL_DAY[1], d, booking))

        sim.schedule(core.StopSimulation(N_DAYS * 24 * 60))
        sim.run()

        time = sim.current_time
        d.record_busy(time)

        ma.append(booking.access.mean())
        inps.append(d.inpatient_late / d.inpatient_total_during_office)

        utilization_in_office_hours.append(d.busy_time_office / d.free_time_office)
        utilization_in_outside_hours.append(d.busy_time_outside_office / d.free_time_outside_office)
        wait_emergency_means.append(d.wait_emergency.mean())
        wait_outpatient_means.append(d.wait_outpatient.mean())
        fraction_outside_room.append(d.patients_outside_room / d.total_arrivals)

    for metric_name, samples in [
        ("utilization_office", utilization_in_office_hours),
        ("utilization_outside", utilization_in_outside_hours),
        ("access_time_days", ma),
        ("wait_emergency", wait_emergency_means),
        ("wait_outpatient", wait_outpatient_means),
        ("fraction_outside_room", fraction_outside_room),
        ("inpatient_late", inps)]:

        number_of_runs = len(samples)
        mean = sum(samples) / number_of_runs
        variance = sum((x - mean) ** 2 for x in samples) / (number_of_runs - 1)
        hw = 1.96 * math.sqrt(variance / number_of_runs)
        print(metric_name, mean, hw, )

    return scanned, wait, uti,interval,ma, inps

def experiment():
    run([FULL_DAY])

if __name__ == "__main__":
    experiment()