import os
import tarfile
from alive_progress import alive_bar
import timeit
import time
from progress.spinner import MoonSpinner
import argparse

diff_list = ["/thanhtungvu/ICT/term9/Internetworking_note.txt", "/thanhtungvu/ICT/term9/note_internet_working",
             "/thanhtungvu/ICT/term9/NetworkSecurity/week7/"]

def createTar(tar_name):
    with tarfile.open(tar_name, "w:gz") as tar_obj:
        with alive_bar(700, bar="bubbles") as bar:
            for obj in diff_list:
                tar_obj.add("/home"+obj,arcname=obj)
                bar()

def elapsed_time(prefix=''):
    e_time = time.time()
    if not hasattr(elapsed_time, 's_time'):
        elapsed_time.s_time = e_time
    else:
        print(f'{prefix} used: {e_time - elapsed_time.s_time:.2f} sec')
        elapsed_time.s_time = e_time


parser = argparse.ArgumentParser()
parser.add_argument("-f", "--file", dest="filename",
                    help="write report to FILE", metavar="FILE")
parser.add_argument("-q", "--quiet",
                    action="store_false", dest="verbose", default=True,
                    help="don't print status messages to stdout")

args = parser.parse_args()

elapsed_time()
# with alive_bar(700, bar="bubbles") as bar:
#     for i in createTar("delta.tar.gz"):
#         bar()
createTar("delta.tar.gz")
elapsed_time("Totaltime ")

