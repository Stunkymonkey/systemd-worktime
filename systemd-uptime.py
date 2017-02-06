#!/usr/bin/env python3
from systemd import journal
import datetime
import argparse
from subprocess import Popen, PIPE


def one_boot(boot, shut, susp, wake):
    print("Boot: {tboot} -> {tshut}".format(tboot=boot, tshut=shut))

    for (s, w) in zip(susp, wake):
        print("  Sleep: {start} -> {wake}".format(start=s, wake=w) )
    print()


def main():
    parser = argparse.ArgumentParser(
        description='listing past uptimes of systemd')
    parser.add_argument("-b", "--boot",
                        type=int,
                        default=0,
                        dest="boot_amount",
                        help='number of boots beeing processed (0 for all)')

    args = parser.parse_args()
    boot_amount = int(args.boot_amount)

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
        # print("bootid: " + bootid)
        # print("bootup: " + str(bootup_date))
        # print("shutdown: " + str(shutdown_date))

    if boot_amount != 0:
        del boot_list[:(amount - boot_amount + 1)]
    # print(boot_list)

    j = journal.Reader(journal.SYSTEM)
    j.log_level(journal.LOG_DEBUG)

    """
    j.add_match("MESSAGE=Linux version")
    j.add_disjunction()
    j.add_match("MESSAGE=Shutting down.")
    j.add_disjunction()
    j.add_match("MESSAGE=System is rebooting.")
    j.add_disjunction()
    """
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

    # print(len(suspendTimes))
    # print(len(wakeTimes))

    suspendTimes.sort()
    wakeTimes.sort()

    for boot in boot_list:
        susp = []
        wake = []
        for (i, j) in zip(suspendTimes, wakeTimes):
            if boot[1] < i and i < boot[2]:
                susp.append(i)
            if boot[1] < j and j < boot[2]:
                wake.append(j)
        one_boot(boot[1], boot[2], susp, wake)


if __name__ == '__main__':
    main()
