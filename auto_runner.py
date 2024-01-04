#!/usr/bin/env python
import subprocess
import argparse
import time
import sys, os
 
from copy import deepcopy
from pprint import pprint

from utils import *


class AutoRun():
    def __init__(self, args):
        self.args = args
        cmd = self.args.cmd
        sleep_time = self.args.time
        self.process = None   # subprocess.Popen()的返回值，初始化为None
        self.cmd_idx = 0
        
        tmp_cmd = []
        if os.path.isfile(cmd):
            print('Loading commands from {}'.format(cmd))
            with open(cmd, 'r', errors='ignore') as f:
                lines = f.readlines()
                for line in lines:
                    tmp_cmd.append(line.strip())
        else:
            tmp_cmd = cmd.split(';')

        self.cmd = [c for c in tmp_cmd if c != '']

        print('Total {} Commads:'.format(len(self.cmd)))
        pprint(self.cmd)

        self.run()                        
        try:
            while True:
                time.sleep(sleep_time)
                self.poll = self.process.poll()
                if self.poll is not None:
                    self.run()
        except KeyboardInterrupt as e:
            self.process.kill()
            print(e)
 
    def run(self):
        print('Starting...')
        cmd = self.cmd[self.cmd_idx % len(self.cmd)]
        self.process = subprocess.Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, shell=True)
        self.cmd_idx += 1


def check_bandwidth_state(args):
    if args.max_bandwidth is not None:
        bandwith_res, bandwith_msg = check_bandwidth_limit(args.max_bandwidth)
        if args.max_bandwidth > 1:
            bandwidth_str = "{:.2f}G".format(args.max_bandwidth)
        else:
            bandwidth_str = "{:.2f}%".format(args.max_bandwidth * 100)

        if not bandwith_res:
            print('=> [x] JustMySocks: {}, max: {}'.format(bandwith_msg, bandwidth_str))
            return False
        else:
            print('=> [✓] JustMySocks: {}, max: {}'.format(bandwith_msg, bandwidth_str))
            return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--time', default=60, type=int, help='程序状态检测间隔（单位：分钟）')  
    parser.add_argument('-c', '--cmd', default=None, type=str, help='需要执行程序的绝对路径，支持jar 如：D:\\calc.exe 或者D:\\test.jar')  
      
    args = parser.parse_args()
    pprint('=> Called with:')
    pprint(vars(args))

    if args.cmd is None:
        print("Invalid command.")
        return 

    app = AutoRun(args)

'''
python auto_runner.py -c "python main.py key -d /Volumes/iwt/pixiv --cache ./cache --update-cache"
'''
if __name__ == '__main__':
    main()