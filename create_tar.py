import os
import tarfile
from alive_progress import alive_bar
import timeit
import time

diff_list = ["/thanhtungvu/ICT/term9/Internetworking_note.txt", "/thanhtungvu/ICT/term9/note_internet_working",
             "/thanhtungvu/ICT/term9/NetworkSecurity/week7/"]

def createTar(tar_name):
    with tarfile.open(tar_name, "w:gz") as tar_obj:
        for obj in diff_list:
            tar_obj.add("/home"+obj,arcname=obj)
            yield

def print_elapsed_time(prefix=''):
    e_time = time.time()
    if not hasattr(print_elapsed_time, 's_time'):
        print_elapsed_time.s_time = e_time
    else:
        print(f'{prefix} consumes: {e_time - print_elapsed_time.s_time:.2f} sec')
        print_elapsed_time.s_time = e_time

print_elapsed_time()
with alive_bar(700, bar="bubbles") as bar:
    for i in createTar("delta.tar.gz"):
        bar()
print_elapsed_time("Creating delta.tar.gz")