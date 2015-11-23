from __future__ import \
    division, unicode_literals, print_function, absolute_import

import json

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches
import matplotlib.ticker as ticker
import matplotlib.markers as markers

from .parse import Context, Event

RESOURCE_PLOT_HEIGHT = .4  # height of the resources in the task plots,
                           # where 1 is the height for the cpu schedule lines
MARGIN = .3  # white margin on y axis
END_RUN_MARGIN = .2

def main(tracefile):
    loaded = json.load(tracefile)
    events = loaded['events']
    ctx = Context(events)
    print(ctx)
    plot(ctx)
    plt.show()


def plot(ctx, **params):
    tasks = ctx.tasks
    resources = ctx.resources

    # figure setup
    fig = plt.figure()
    gs = gridspec.GridSpec(len(ctx.tasks)
                           + int(bool(ctx.system_ceiling_events)),
                           1)
    gs.update(hspace=0, wspace=0)

    # color palettes for tasks and resources
    # in the end, both are {name: color} dictionaries
    tcolors = plt.cm.Pastel1(np.linspace(0, 1, len(tasks)))
    tcolors = {tname: col for tname, col in zip(tasks.keys(), tcolors)}
    rcolors = plt.cm.Set1(np.linspace(0, 1, len(tasks)))
    rcolors = {resname: col for resname, col in zip(resources.keys(), rcolors)}

    # Tasks lines
    axs = []
    index = 0
    for tname, task in tasks.items():
        if not axs:
            ax = fig.add_subplot(gs[index])
        else:
            ax = fig.add_subplot(gs[index], sharex=axs[0])
        plot_task(ax, ctx, tname, color=tcolors[tname], rcolors=rcolors)
        axs.append(ax)
        index += 1

    # System ceiling line
    if ctx.system_ceiling_events:
        ax = fig.add_subplot(gs[index], sharex=axs[0])
        plot_system_ceiling(ax, ctx)
        axs.append(ax)
        index += 1

    # Restore time scale in the bottom ax
    ax = axs[-1]
    ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
    ax.set_xlabel('Simulation time')

    return fig


def plot_task(ax, ctx, tname, color, rcolors):
    task = ctx.tasks[tname]
    plot_setup_common(ax, ctx)
    plot_setup_cpus_res(ax, ctx.cpus, task.resources)
    ax.set_ylabel(tname)

    curr_job = None  # arrival time of running job
    curr_burst = None  # (start_time, cpu) of current cpu burst
    for evt in task.exec_events:
        if evt.type == Event.TYPES.arrival:
            current_job = evt.arrival_time
            _plot_task_arrival(ax, evt.time, num_cpus=len(ctx.cpus))
        if evt.type == Event.TYPES.dmiss:
            _plot_task_dmiss(ax, evt.time, num_cpus=len(ctx.cpus))
        elif evt.type == Event.TYPES.scheduled:
            assert curr_burst is None, str(curr_burst)
            curr_burst = (evt.time, evt.cpu)
        elif evt.type in (Event.TYPES.descheduled, Event.TYPES.end_instance):
            t0, cpu0 = curr_burst
            t1, cpu1 = evt.time, evt.cpu
            assert cpu0 == cpu1
            _plot_burst(ax, t0, t1, cpu0, color=color)
            curr_burst = None
            if evt.type == Event.TYPES.end_instance:
                curr_job = None
    if curr_burst is not None:  # continue pending bursts to end_time
        t0, cpu0 = curr_burst
        _plot_burst(ax, t0, ctx.end_time + END_RUN_MARGIN, cpu0, color=color)

    lock_stack = []  # stack of locked (time, res_name)
    for evt in task.res_events:
        if evt.type == Event.TYPES.wait:
            _plot_res_wait(ax, evt.time, rcolors[evt['resource']],
                           task.resources.index(evt['resource']),
                           num_cpus=len(ctx.cpus))
        elif evt.is_acquire_evt:
            lock_stack.append((evt.time, evt['resource']))
        elif evt.type == Event.TYPES.signal:
            try:
                t0, r0 = lock_stack.pop()
            except IndexError:
                raise AssertionError('Unmatched Signal Event')
            t1, r1 = evt.time, evt['resource']
            assert r0 == r1, 'Bad Critical section nesting'
            _plot_res_burst(ax, t0, t1, rcolors[r0], task.resources.index(r0),
                            num_cpus=len(ctx.cpus))
    while lock_stack:  # continue pending locks to end_time
        t0, r0 = lock_stack.pop()
        _plot_res_burst(ax, t0, ctx.end_time + END_RUN_MARGIN, rcolors[r0],
                        task.resources.index(r0), num_cpus=len(ctx.cpus))

    plot_finalize_cpus_res(ax, ctx.cpus, task.resources)
    ax.margins(x=.01, y=.05)


def plot_system_ceiling(ax, ctx):
    plot_setup_common(ax, ctx)
    ax.set_ylabel("System\nceiling")

    xs, ys = [0], [0]
    prev_ceiling = 0
    for evt in ctx.system_ceiling_events:
        c = int(evt['ceiling'])
        xs.extend([evt.time, evt.time])
        ys.extend([prev_ceiling, c])
        prev_ceiling = c
    # continue to the end
    xs.append(ctx.end_time + END_RUN_MARGIN)
    ys.append(prev_ceiling)

    ax.plot(xs, ys, color='black', linewidth=2)

    ax.margins(x=.01, y=.05)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(
        nbins=9, steps=[1, 2, 5, 10], integer=True))


def _plot_task_arrival(ax, t, num_cpus):
    ax.vlines(x=t, ymin=0, ymax=num_cpus+MARGIN*2/3,
              colors='black', linewidth=2, zorder=2)
    ax.plot([t], [num_cpus+MARGIN*2/3], marker=markers.CARETUP,
            markeredgecolor='black', markeredgewidth=2,
            markerfacecolor='None', markersize=8)

def _plot_task_dmiss(ax, t, num_cpus):
    ax.vlines(x=t, ymin=0, ymax=num_cpus-MARGIN*2/3,
              colors='red', linewidth=2, zorder=3)
    ax.plot([t], [0], marker=markers.CARETDOWN, markeredgecolor='red',
            markeredgewidth=2, markerfacecolor='None', markersize=8)

def _plot_burst(ax, t0, t1, cpu, color):
    ax.add_patch(patches.Rectangle(xy=(t0, cpu), width=t1-t0, height=1,
                                   facecolor=color, edgecolor='black'))

def _plot_res_burst(ax, t0, t1, color, res_index, num_cpus):
    R = RESOURCE_PLOT_HEIGHT
    ax.add_patch(patches.Rectangle(xy=(t0, (-res_index-1)*R),
                                   width=t1-t0, height=R,
                                   facecolor=color, edgecolor='black'))
    ax.vlines(x=t1, ymin=0, ymax=num_cpus, colors=color, linestyle='dotted')

def _plot_res_wait(ax, t, color, res_index, num_cpus):
    R = RESOURCE_PLOT_HEIGHT
    ax.vlines(x=t, ymin=(-res_index-1)*R,
              ymax=-res_index*R, colors='black', linewidth=2)
    ax.vlines(x=t, ymin=0, ymax=num_cpus, colors=color, linestyle='dashed')


def plot_setup_cpus_res(ax, cpus, resources):
    R = RESOURCE_PLOT_HEIGHT

    ax.axhline(0, color='black')
    for y in range(len(cpus)):
        ax.axhline(y+1, color='grey', linewidth=.5)
    for y in range(len(resources)):
        ax.axhline((-y-1)*R, color='grey', linewidth=.5)

    ax.set_yticks([(-y-1)*R for y in range(len(resources))]
                  + [0]
                  + [(y+1) for y in range(len(cpus))])
    ax.yaxis.set_major_formatter(ticker.NullFormatter())

    ax.set_yticks([(-y-.5)*R for y in range(len(resources))]
                  + [(y+.5) for y in range(len(cpus))],
                  minor=True)
    ax.set_yticklabels(list(resources)
                       + ['CPU {}'.format(cpu) for cpu in cpus],
                       minor=True)

    for tick in ax.yaxis.get_minor_ticks():
        tick.tick1line.set_markersize(0)
        tick.tick2line.set_markersize(0)


def plot_finalize_cpus_res(ax, cpus, resources):
    R = RESOURCE_PLOT_HEIGHT
    ax.set_ybound(lower=-len(resources)*R-MARGIN,
                  upper=len(cpus)+MARGIN)


def plot_setup_common(ax, ctx):
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(base=1))
    ax.xaxis.set_minor_formatter(ticker.NullFormatter())
    ax.xaxis.set_major_locator(ticker.MaxNLocator(
        nbins=29, steps=[1, 2, 5, 10], integer=True))
    ax.xaxis.set_major_formatter(ticker.NullFormatter())
    ax.xaxis.grid(True, which='major')

    # end simulation line
    ax.axvline(ctx.end_time + END_RUN_MARGIN, color='grey',
               linewidth=3, zorder=5)

