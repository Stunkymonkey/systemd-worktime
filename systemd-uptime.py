#!/usr/bin/python3
from systemd import journal
import datetime
import time
import argparse
from subprocess import Popen, PIPE


def main():
	parser = argparse.ArgumentParser(description='listing past uptimes of systemd')
	parser.add_argument("-b", "--boot",
						type=int,
						default=0,
						dest="boot_amount",
						help='number of boots beeing processed (0 for all)')

	args = parser.parse_args()
	boot_amount = int(args.boot_amount)


	# p = Popen(['journalctl --list-boots --utc'], stdout=PIPE, shell=True)
	p = Popen(['journalctl --list-boots'], stdout=PIPE, shell=True)
	output, err = p.communicate()
	exitcode = p.wait()
	if exitcode != 0:
		quit("Error with systemd")

	amount = int(output.rstrip().split()[0].decode())
	boot_list = []

	for line, i in zip(output.splitlines(), range(-amount)):
		boot = line.rstrip().decode().split()
		bootid = str(boot[1])
		bootup = str(boot[3] + "." + boot[4])
		shutdown = str(boot[6] + "." + boot[7])
		bootup_date = datetime.datetime.strptime(bootup, '%Y-%m-%d.%H:%M:%S')
		shutdown_date = datetime.datetime.strptime(shutdown, '%Y-%m-%d.%H:%M:%S')
		if (i < boot_amount or boot_amount == 0):
			boot_list.append([bootid, bootup_date, shutdown_date])
		#print("bootid: " + bootid)
		#print("bootup: " + str(bootup_date))
		#print("shutdown: " + str(shutdown_date))

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
				suspendTimes.append(entry['__REALTIME_TIMESTAMP'])
				continue
			if "Finishing wakeup" in str(entry['MESSAGE']):
				wakeTimes.append(entry['__REALTIME_TIMESTAMP'])
				continue
			else:
				print(str(entry['MESSAGE']))
		except:
			continue
	j.close()

	# print(len(suspendTimes))
	# print(len(wakeTimes))

	for boot in boot_list:
		print("Bootup: " + str(boot[1]))
		for (i, j) in zip (suspendTimes, wakeTimes):
			if boot[1] > i and i < boot[2]:
				print("Suspend: " + str(i))
			if boot[1] > j and j < boot[2]:
				print("Wakeup: " + str(j))
		print("Shutdown: " + str(boot[2]))


if __name__ == '__main__':
	main()