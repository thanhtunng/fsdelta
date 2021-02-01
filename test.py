#!/usr/bin/env python3

# import tarfile
# import os, sys

# def compare_tar():
#   os.chdir("/home/thanhtungvu/ICT/term9/SystemProgram/")
#   tar = tarfile.open("Slide_VN.tar.gz")
#   for member in tar.getmembers():
#     print (member)
#     # f=tar.extractfile(member)
#     # content=f.read()
#     # print ("%s has %d newlines") %(member, content.count("\n"))
#     # print ("%s has %d spaces") % (member,content.count(" "))
#     # print ("%s has %d characters") % (member, len(content))
#     sys.exit()
#   tar.close()

# compare_tar()

from multiprocessing.pool import ThreadPool, Pool
# import StringIO
import multiprocessing as mp
import tarfile, time

tar_name = "delta.tar.gz"

def write_tar():
    tar = tarfile.open('test.tar', 'w')
    contents = 'line1'
    info = tarfile.TarInfo('file1.txt')
    info.size = len(contents)
    tar.addfile(info, StringIO.StringIO(contents))
    tar.close()

def test_multithread():
    tar   = tarfile.open(tar_name,"r:gz")
    files = [tar.extractfile(member) for member in tar.getmembers()]
    pool  = ThreadPool(processes=10)
    result = pool.map(read_file2, files)
    tar.close()

def test_multiproc():
    tar   = tarfile.open(tar_name,"r:gz")
    files = [name for name in tar.getnames()]
    # pool  = Pool(processes=1)
    print (mp.cpu_count())
    pool = Pool(mp.cpu_count())
    result = pool.map(read_file3, files)
    tar.close()

# def read_file(f):
#     print f.read()

def read_file2(name):
    t2 = tarfile.open(tar_name,"r:gz")
    t2.extract(name,"./delta")
    # print (t2.extractfile(name))
    t2.close()

def read_file3(name):
    t3 = tarfile.open(tar_name,"r:gz")
    t3.extractall("./delta",members=name)
    t3.close()

# write_tar()
# test_multithread()
def elapsed_time(prefix=''):
    e_time = time.time()
    if not hasattr(elapsed_time, 's_time'):
        elapsed_time.s_time = e_time
    else:
        print(f'{prefix} used: {e_time - elapsed_time.s_time:.2f} sec')
        elapsed_time.s_time = e_time

elapsed_time()
# test_multithread()
test_multiproc()
# t2 = tarfile.open(tar_name,"r:gz")
# t2.extractall("./delta",members=[mem for mem in t2.getmembers()])
# t2.close()
elapsed_time("Total time")

