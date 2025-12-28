#!/usr/bin/env python3
from systemd import journal
import datetime
import argparse
from subprocess import Popen, PIPE
import sys
import json


class Boot:
    def __init__(self, bootid, bootup, shutdown):
        self.bootid = bootid
        self.bootup = bootup
        self.shutdown = shutdown
        self.suspendTimes = []
        self.wakeTimes = []

    def __str__(self):
        return "Boot: {tboot} -> {tshut}".format(tboot=self.bootup, tshut=self.shutdown)

    def add_suspend(self, suspend):
        self.suspendTimes.append(suspend)
        self.suspendTimes.sort()

    def add_wake(self, wake):
        self.wakeTimes.append(wake)
        self.wakeTimes.sort()

    def total_uptime(
        self, quiet: bool = False, verbose: bool = False
    ) -> datetime.timedelta:
        """
        Calculate the total uptime for this boot session, considering suspends/wakes.
        """
        # Build start and end lists
        up_times = [self.bootup] + self.wakeTimes
        down_times = self.suspendTimes + [self.shutdown]

        # Ensure equal length
        if len(up_times) != len(down_times):
            up_times, down_times = correct_list(up_times, down_times)

        # Print info
        if not quiet:
            print(f"\nBoot {self.bootid}: {up_times[0]} -> {down_times[-1]}")
            if verbose:
                for start, end in zip(up_times, down_times):
                    print(f"\tWork: {start} -> {end}")

        # Sum all uptimes
        total = datetime.timedelta(0)
        for start, end in zip(up_times, down_times):
            total += end - start

        if not quiet:
            print(total)

        return total


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


def get_bootlist(boot_amount: int) -> list[Boot]:
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


def get_wake_sleep(boot: Boot):
    j = journal.Reader(journal.SYSTEM)
    j.this_boot(boot.bootid)
    j.add_conjunction()
    j.log_level(journal.LOG_DEBUG)

    # Patterns for suspend and resume/wake events
    suspendStartList = [
        "Entering sleep state 'suspend'...",
        "Reached target Sleep.",
        "PM: suspend entry (deep)"
    ]
    hibernateStartList = [
        "Suspending system...",
        "PM: hibernation: hibernation entry"
    ]
    suspendWakeList = [
        "ACPI: PM: Waking up from system sleep state S3",
        "ACPI: Waking up from system sleep state S3"
    ]
    hibernateWakeList = [
        "ACPI: PM: Waking up from system sleep state S4",
        "ACPI: Waking up from system sleep state S4"
    ]

    for item in (hibernateStartList + suspendStartList + suspendWakeList + hibernateWakeList):
        j.add_match(f"MESSAGE={item}")
        j.add_disjunction()

    for entry in j:
        try:
            msg = str(entry.get("MESSAGE", ""))
        except KeyError:
            continue
        if any(p in msg for p in suspendStartList + hibernateStartList):
            boot.add_suspend(
                entry["__REALTIME_TIMESTAMP"]
                .astimezone(datetime.timezone.utc)
                .replace(microsecond=0)
            )
        elif any(p in msg for p in suspendWakeList + hibernateWakeList):
            boot.add_wake(
                entry["__REALTIME_TIMESTAMP"]
                .astimezone(datetime.timezone.utc)
                .replace(microsecond=0)
            )
    j.close()

    return boot


def parser() -> int:
    parser = argparse.ArgumentParser(description="listing past uptimes of systemd")
    parser.add_argument(
        "-b",
        "--boot",
        type=int,
        default=0,
        dest="amount",
        help="number of boots beeing processed (0 for all)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False, help="verbose output"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", default=False, help="less output"
    )
    parser.add_argument(
        "-s", "--seconds", action="store_true", default=False, help="output in seconds"
    )

    args = parser.parse_args()
    boot_amount = int(args.amount)
    seconds = bool(args.seconds)
    verbose = bool(args.verbose)
    quiet = bool(args.quiet)

    return boot_amount, seconds, verbose, quiet


def main():
    boot_amount, seconds, verbose, quiet = parser()

    boot_list = get_bootlist(boot_amount)

    for boot in boot_list:
        boot = get_wake_sleep(boot)

    total = sum(
        (boot.total_uptime(quiet, verbose) for boot in boot_list), datetime.timedelta(0)
    )
    worktime_str = str(int(total.total_seconds())) if seconds else str(total)
    print(f"\nWorktime: {worktime_str}")


if __name__ == '__main__':
    main()
