#!/usr/bin/env python3
from systemd import journal
import datetime
import argparse
from subprocess import Popen, PIPE

verbose = False


def one_boot(boot, shut, susp, wake):
    up = [boot] + wake
    down = susp + [shut]

    print("Boot: {tboot} -> {tshut}".format(tboot=boot, tshut=shut))

    # if lists have unequal lenght, correcting it here
    if len(wake) is not len(susp):
        print("uneven list, trying to repair it...")

        new_up = [up[0]]
        del up[0]
        new_down = []

        next_is_up = False
        for i in range(len(down) * 2):
            if next_is_up:
                if up[0] > new_down[-1]:
                    new_up.append(up[0])
                    del up[0]
                    next_is_up = False
                else:
                    print()
                    print("uptime conflict with",
                          up[0], "and", new_up[-1])
                    print("deleting:", new_up[-1])
                    del new_up[-1]
                    new_up.append(up[0])
                    del up[0]
                    print()
            else:
                if down[0] > new_up[-1]:
                    new_down.append(down[0])
                    del down[0]
                    next_is_up = True
                else:
                    print()
                    print("downtime conflict with:",
                          down[0], "and", new_down[-1])
                    print(new_down[-1])
                    print("deleting:", down[0])
                    del down[0]
                    print()

        up = new_up
        down = new_down

    global verbose
    if verbose:
        for (s, e) in zip(up, down):
            print("  Work: {start} -> {end}".format(start=s, end=e))

    sum = datetime.timedelta(0, 0)
    for (u, d) in zip(up, down):
        sum += d - u
    print(sum)
    print()
    return sum


def main():
    parser = argparse.ArgumentParser(
        description='listing past uptimes of systemd')
    parser.add_argument("-b", "--boot",
                        type=int,
                        default=0,
                        dest="boot_amount",
                        help='number of boots beeing processed (0 for all)')
    parser.add_argument("-v", action="store_true", default=False)

    args = parser.parse_args()
    boot_amount = int(args.boot_amount)
    global verbose
    verbose = bool(args.v)

    p = Popen(['journalctl --list-boots'], stdout=PIPE, shell=True)
    output, err = p.communicate()
    exitcode = p.wait()
    if exitcode != 0:
        quit("Error with systemd")

    amount = -int(output.rstrip().split()[0].decode())
    boot_list = []

    for line in output.splitlines():
        boot = line.rstrip().decode().split()
        bootid = str(boot[1])
        bootup = str(boot[3] + "." + boot[4])
        shutdown = str(boot[6] + "." + boot[7])
        bootup_date = datetime.datetime.strptime(bootup, '%Y-%m-%d.%H:%M:%S')
        shutdown_date = datetime.datetime.strptime(
            shutdown, '%Y-%m-%d.%H:%M:%S')
        boot_list.append([bootid, bootup_date, shutdown_date])

    if boot_amount != 0:
        del boot_list[:(amount - boot_amount + 1)]

    j = journal.Reader(journal.SYSTEM)
    j.log_level(journal.LOG_DEBUG)

    j.add_match("MESSAGE=Suspending system...")
    j.add_disjunction()
    j.add_match("MESSAGE=PM: Finishing wakeup.")

    suspendTimes = []
    wakeTimes = []

    for entry in j:
        try:
            # print(str(entry['__REALTIME_TIMESTAMP'] )+ ' ' + entry['MESSAGE'])
            if "Suspending system..." in str(entry['MESSAGE']):
                suspendTimes.append(
                    entry['__REALTIME_TIMESTAMP'].replace(microsecond=0))
                continue
            if "Finishing wakeup" in str(entry['MESSAGE']):
                wakeTimes.append(
                    entry['__REALTIME_TIMESTAMP'].replace(microsecond=0))
                continue
            else:
                print(str(entry['MESSAGE']))
        except:
            continue
    j.close()

    suspendTimes.sort()
    wakeTimes.sort()

    sum = datetime.timedelta(0, 0)

    for boot in boot_list:
        susp = []
        wake = []
        for (i, j) in zip(suspendTimes, wakeTimes):
            if boot[1] < i and i < boot[2]:
                susp.append(i)
            if boot[1] < j and j < boot[2]:
                wake.append(j)
        sum += one_boot(boot[1], boot[2], susp, wake)

    print("Sum together:", sum)


if __name__ == '__main__':
    main()
