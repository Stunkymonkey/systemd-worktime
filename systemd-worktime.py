#!/usr/bin/env python3
from systemd import journal
import datetime
import argparse
from subprocess import Popen, PIPE
import sys
import json
import logging

logger = logging.getLogger(__name__)


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

    def total_uptime(self) -> datetime.timedelta:
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
        logger.info(f"Boot {self.bootid}: {up_times[0]} -> {down_times[-1]}")
        for start, end in zip(up_times, down_times):
            logger.debug(f"\tWork: {start} -> {end}")

        # Sum all uptimes
        total = datetime.timedelta(0)
        for start, end in zip(up_times, down_times):
            total += end - start

        logger.info(total)

        return total


def correct_list(up, down):
    """
    Synchronizes 'up' and 'down' lists to ensure they have matching pairs.
    Handles cases where journal entries might be missing.
    """
    new_up = []
    new_down = []

    up_idx = 0
    down_idx = 0

    while up_idx < len(up) and down_idx < len(down):
        current_up = up[up_idx]
        current_down = down[down_idx]

        if current_up < current_down:
            # Check if there's a subsequent 'up' before this 'down'
            if up_idx + 1 < len(up) and up[up_idx + 1] < current_down:
                logger.warning(f"Skip missing shutdown for boot at: {current_up}")
                up_idx += 1
                continue

            # Valid pair
            new_up.append(current_up)
            new_down.append(current_down)
            up_idx += 1
            down_idx += 1
        else:
            # Down event before Up event, or missing Up
            logger.warning(f"Skip missing boot for shutdown at: {current_down}")
            down_idx += 1

    return new_up, new_down


def get_bootlist(boot_amount: int) -> list[Boot]:
    """
    return all boots of the system
    """
    p = Popen(["journalctl", "--list-boots", "--output=json"], stdout=PIPE)
    output, err = p.communicate()
    exitcode = p.wait()
    if exitcode != 0:
        logger.error("Error with systemd")
        sys.exit(1)

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        logger.error("Error parsing journalctl output")
        sys.exit(1)

    boot_list = []
    for entry in data:
        bootid = entry["boot_id"]
        # timestamps are in microseconds
        bootup_date = datetime.datetime.fromtimestamp(
            entry["first_entry"] / 1e6, tz=datetime.timezone.utc
        ).replace(microsecond=0)
        shutdown_date = datetime.datetime.fromtimestamp(
            entry["last_entry"] / 1e6, tz=datetime.timezone.utc
        ).replace(microsecond=0)
        boot_list.append(Boot(bootid, bootup_date, shutdown_date))

    if boot_amount != 0:
        amount = len(boot_list)
        if boot_amount < amount:
            del boot_list[: (amount - boot_amount)]

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
        "PM: suspend entry (deep)",
    ]
    hibernateStartList = ["Suspending system...", "PM: hibernation: hibernation entry"]
    suspendWakeList = [
        "ACPI: PM: Waking up from system sleep state S3",
        "ACPI: Waking up from system sleep state S3",
    ]
    hibernateWakeList = [
        "ACPI: PM: Waking up from system sleep state S4",
        "ACPI: Waking up from system sleep state S4",
    ]

    for item in (
        hibernateStartList + suspendStartList + suspendWakeList + hibernateWakeList
    ):
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


def parser() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="listing past uptimes of systemd")
    parser.add_argument(
        "-b",
        "--boot",
        type=int,
        default=0,
        help="number of boots being processed (0 for all)",
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-v", "--verbose", action="store_true", default=False, help="verbose output"
    )
    group.add_argument(
        "-q", "--quiet", action="store_true", default=False, help="less output"
    )
    
    parser.add_argument(
        "-s", "--seconds", action="store_true", default=False, help="output in seconds"
    )

    return parser.parse_args()


def main():
    args = parser()

    log_level = logging.INFO
    if args.quiet:
        log_level = logging.ERROR
    elif args.verbose:
        log_level = logging.DEBUG

    logging.basicConfig(level=log_level, format="%(message)s")

    raw_boot_list = get_bootlist(args.boot)
    boot_list = [get_wake_sleep(boot) for boot in raw_boot_list]

    total = sum(
        (boot.total_uptime() for boot in boot_list), datetime.timedelta(0)
    )
    worktime_str = str(int(total.total_seconds())) if args.seconds else str(total)
    print(f"\nWorktime: {worktime_str}")


if __name__ == "__main__":
    main()
