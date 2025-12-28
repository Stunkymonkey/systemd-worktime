#!/usr/bin/env python3
from systemd import journal
import datetime
import argparse
from subprocess import Popen, PIPE
import sys
import json

verbose = False
quiet = False
seconds = False


def correct_list(up, down):
    """
    correcting uneven lists
    """
    new_up = list()
    new_down = list()

    up_index, down_index = 0, 0
    while True:
        # leave out all boot that have not a direct shutdown behind
        while (up_index < len(up) - 1) and (up[up_index + 1] < down[down_index]):
            print("skip boot:", up[up_index], "(direct shutdown was not found)")
            up_index += 1
        # add valid boot and shutdown
        if down[down_index] > up[up_index]:
            new_down.append(down[down_index])
            new_up.append(up[up_index])
            up_index += 1
            down_index += 1
        if up_index >= len(up):
            break
        # leave out all shutdown out without boots
        while up[up_index] > down[down_index]:
            print("skip shutdown:", down[down_index], "(direct boot was not found)")
            down_index += 1

    return new_up, new_down


def one_boot(boot, shut, susp, wake):
    """
    calculating the timedelta of one boot
    """
    up = [boot] + wake
    down = susp + [shut]

    if len(wake) is not len(susp):
        up, down = correct_list(up, down)

    if not quiet:
        print("Boot: {tboot} -> {tshut}".format(tboot=up[0], tshut=down[-1]))
        if verbose:
            for (s, e) in zip(up, down):
                print("  Work: {start} -> {end}".format(start=s, end=e))

    sum = datetime.timedelta(0, 0)
    for (u, d) in zip(up, down):
        sum += d - u
    if not quiet:
        print(sum)
        print()

    return sum


def get_bootlist(boot_amount):
    """
    return all boots of the system
    """
    p = Popen(['journalctl', '--list-boots', '--output=json'], stdout=PIPE)
    output, err = p.communicate()
    exitcode = p.wait()
    if exitcode != 0:
        print("Error with systemd")
        sys.exit(1)

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        print("Error parsing journalctl output")
        sys.exit(1)

    boot_list = []
    for entry in data:
        bootid = entry['boot_id']
        # timestamps are in microseconds
        bootup_date = datetime.datetime.fromtimestamp(
            entry['first_entry'] / 1e6, tz=datetime.timezone.utc)
        shutdown_date = datetime.datetime.fromtimestamp(
            entry['last_entry'] / 1e6, tz=datetime.timezone.utc)
        boot_list.append([bootid, bootup_date, shutdown_date])

    if boot_amount != 0:
        amount = len(boot_list)
        if boot_amount < amount:
            del boot_list[:(amount - boot_amount)]

    return boot_list


def get_wake_sleep():
    j = journal.Reader(journal.SYSTEM)
    j.log_level(journal.LOG_DEBUG)

    j.add_match("MESSAGE=Suspending system...")
    j.add_disjunction()
    j.add_match("MESSAGE=PM: Finishing wakeup.")
    j.add_disjunction()
    j.add_match("MESSAGE=PM: hibernation exit")

    suspendTimes = []
    wakeTimes = []

    for entry in j:
        try:
            # print(str(entry['__REALTIME_TIMESTAMP'] )+ ' ' + entry['MESSAGE'])
            if "Suspending system..." in str(entry['MESSAGE']):
                suspendTimes.append(
                    entry['__REALTIME_TIMESTAMP'].replace(microsecond=0))
                continue
            elif "Finishing wakeup" in str(entry['MESSAGE']):
                wakeTimes.append(
                    entry['__REALTIME_TIMESTAMP'].replace(microsecond=0))
                continue
            elif "hibernation exit" in str(entry['MESSAGE']):
                wakeTimes.append(
                    entry['__REALTIME_TIMESTAMP'].replace(microsecond=0))
                continue
            else:
                print(str(entry['MESSAGE']))
        except:
            continue
    j.close()

    return suspendTimes, wakeTimes


def parser():
    parser = argparse.ArgumentParser(
        description='listing past uptimes of systemd')
    parser.add_argument("-b", "--boot",
                        type=int,
                        default=0,
                        dest="amount",
                        help="number of boots beeing processed (0 for all)")
    parser.add_argument("-v", "--verbose", action="store_true", default=False,
                        help="verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", default=False,
                        help="less output")
    parser.add_argument("-s", "--seconds", action="store_true", default=False,
                        help="output in seconds")

    args = parser.parse_args()
    boot_amount = int(args.amount)
    global seconds
    seconds = bool(args.seconds)
    global verbose
    verbose = bool(args.verbose)
    global quiet
    quiet = bool(args.quiet)

    return boot_amount


def main():
    boot_amount = parser()

    boot_list = get_bootlist(boot_amount)

    suspendTimes, wakeTimes = get_wake_sleep()

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

    if seconds:
        print(int(sum.total_seconds()))
    else:
        print("Worktime:", sum)


if __name__ == '__main__':
    main()
