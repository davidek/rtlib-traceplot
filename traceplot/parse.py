from __future__ import \
    division, unicode_literals, print_function, absolute_import

import json
from collections import defaultdict, OrderedDict

class Struct(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class Event(object):
    """Wraps a json event object"""
    def __init__(self, orig):
        self._orig = orig

        self.time = int(self['time'])
        self.is_server_evt = ('server_name' in self)
        self.type = self['event_type']

    def __getitem__(self, key):
        return self._orig[key]

    def __contains__(self, key):
        return (key in self._orig)

    @property
    def task_name(self):
        if 'server_name' in self:
            return self['server_name']
        else:
            return self['task_name']
    @property
    def current_budget(self):
        return int(self['current_budget'])
    @property
    def has_current_budget(self):
        return ('current_budget' in self)
    @property
    def arrival_time(self):
        return int(self['arrival_time'])
    @property
    def cpu(self):
        assert self['cpu_num'] != 'any'
        return int(self['cpu_num'])
    @property
    def is_acquire_evt(self):
        return (self.type == 'end_instr' and self['instr_type'] == 'wait')

    class TYPES:
        arrival = 'arrival'
        end_instance = 'end_instance'
        dmiss = 'dline_miss'
        scheduled = 'scheduled'
        descheduled = 'descheduled'
        signal = 'signal'
        wait = 'wait'
        end_instr = 'end_instr'

    class INSTR_TYPES:
        wait = 'wait'


def _sort_dict(d):
    return OrderedDict(sorted(d.items()))


class Context(object):
    def __init__(self, raw_events):
        self._events = [Event(e) for e in raw_events]
        self.tasks = defaultdict(lambda: Struct(
            exec_events=[],     # schedule, deschedule, arrival, end
            res_events=[],      # wait, end_instr-wait, signal
            resources=set(),
        ))
        self.servers = set()
        self.budget_servers = defaultdict(lambda: Struct(
            budget_events = [],
        ))
        self.resources = defaultdict(lambda: Struct(
            events=[],          # end_instr-wait, signal
        ))
        self.cpus = defaultdict(lambda: Struct(
            events=[],          # schedule, deschedule
        ))
        self.end_time = 0
        # TODO: for mrtp, we may have one list per cpu, in the `cpus` dict
        self.system_ceiling_events = []

        for evt in self._events:
            self._inspect_event(evt)

        # normalize, as parsing is now done
        self.tasks = _sort_dict(self.tasks)
        self.servers = sorted(self.servers)
        self.budget_servers = _sort_dict(self.budget_servers)
        self.resources = _sort_dict(self.resources)
        self.cpus = _sort_dict(self.cpus)
        for t in self.tasks.values():
            t.resources = sorted(t.resources)

    def is_server(self, tname):
        return (tname in self.servers)

    def _inspect_event(self, evt):
        self.end_time = max(self.end_time, evt.time)
        t = evt.type

        if t in ('arrival', 'end_instance', 'scheduled', 'descheduled',
                 'dline_miss'):
            self.tasks[evt.task_name].exec_events.append(evt)

        if t in ('scheduled', 'descheduled'):
            self.cpus[evt.cpu].events.append(evt)

        if t == 'signal' or evt.is_acquire_evt:
            self.resources[evt['resource']].events.append(evt)

        if t == 'wait' or t == 'signal' or evt.is_acquire_evt:
            self.tasks[evt.task_name].res_events.append(evt)
            self.tasks[evt.task_name].resources.add(evt['resource'])

        if t == 'system_ceiling_changed':
            self.system_ceiling_events.append(evt)

        if evt.is_server_evt:
            self.servers.add(evt)

        if evt.has_current_budget:
            self.budget_servers[evt.task_name].budget_events.append(evt)

    def __str__(self):
        return json.dumps(OrderedDict([
            ('events count', len(self._events)),
            ('tasks', self.tasks.keys()),
            ('budget_servers', self.budget_servers.keys()),
            ('resources', self.resources.keys()),
            ('cpus', self.cpus.keys()),
        ]), indent=4)



