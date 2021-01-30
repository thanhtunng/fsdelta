#!/usr/bin/env python3
#
# Copyright © 2021 Toshiba corporation
# Maintainer: Vu Thanh Tung (thanhtungvu.hust@gmail.com)
#

import argparse
import os, sys, stat
import re
import glob, fnmatch
import tarfile
import hashlib

diff_list=[]        # list of changed files/folders (link,checksum) or new files/folders
del_list=[]         # list of deleted files/folders (only in base package)
permission_list={}  # list of different typical permission files/folders
ugid_list={}        # list of different owner/group id files/folders
exclude_patterns=["$!"] # Pattern list which is not in comparison
include_patterns=[] # Pattern list which will be compared
tar_name="delta.tar.gz"
script_name="delta.sh"

def gen_tar_file(prefix, diff_list):
  """
  Function to generate a delta tar file by reading from a list
  """
  with tarfile.open(tar_name, "w:gz") as tar_obj:
    for obj in diff_list:
      tar_obj.add(os.path.join(prefix,obj),arcname=obj)

def gen_script(del_list, permission_list, ugid_list):
  """
  Function to generate a script to:
    - Remove files/folders in base package which deleted in new package
    - Update metadata of files/folders by new package
  """
  with open(script_name, 'w+') as out:
    print('#!/bin/bash \n# Usage : sudo ./%s folder/\n' % script_name,file=out)
    print("declare -a DEL_LIST=(",file=out)
    for obj in del_list:
      out.write("  %s\n" % (obj))
    out.write(")\n")

    print("declare -A PERMISSION_LIST=(",file=out)
    for key, value in permission_list.items():
      out.write("  [%s]=%s\n" % (key, value))
    out.write(")\n")

    for key, values in ugid_list.items():
      print("declare -a %s_UGID=( %s %s )" % (key.replace('/','_'), values[0], values[1]), file=out)

    print ('for obj in "${DEL_LIST[@]}"\n\
do\n  rm -rf $1/$obj\n\
done\n\
for obj in "${!PERMISSION_LIST[@]}"\n\
do\n  chmod ${PERMISSION_LIST[$obj]} $1/$obj\n\
done\n',file=out)
    for key, value in ugid_list.items():
      print ('chown ${%s_UGID[0]}:${%s_UGID[1]} $1/%s' % (key.replace('/','_'), key.replace('/','_'), key),file=out)

def ignore(name):
  """
  Files/folders to ignore when comparing
  """
  for pattern in exclude_patterns:
    if bool(re.match(pattern, name)) == True or bool(fnmatch.fnmatch(name, pattern)) == True:
      return True
    
  return False

def md5_checksum(filename, block_size=2**20):
  """
  Calculate MD5 checksum of a file
  """
  f = open(filename,"r",encoding='ISO-8859-1')
  md5 = hashlib.md5()
  while True:
    data = f.read(block_size)
    if not data:
      break
    md5.update(data.encode('ISO-8859-1'))
  f.close()
  return md5.digest()

def diff_meta(name, name1, name2):
  if os.path.islink(name1) and os.path.islink(name2):
    link1 = os.readlink(name1)
    link2 = os.readlink(name2)
    if link1 != link2:
      # Symlink differs
      diff_list.append(name)
      return
  elif os.path.islink(name1) or os.path.islink(name2):
    # File type differs
    diff_list.append(name)
    return
  stat1 = os.stat(name1)
  stat2 = os.stat(name2)
  if stat1.st_mode != stat2.st_mode:
    # Add new element in permission changed list with corresponding octal permission representation
    permission_list[name] = oct(stat2.st_mode)[-3:]
  if stat1.st_uid != stat2.st_uid or stat1.st_gid != stat2.st_gid:
    # Add new element in owner/group id changed list with user id & group id
    ugid_list[name] = []
    ugid_list[name].append(stat2.st_uid)
    ugid_list[name].append(stat2.st_gid)
  # else:
    # Unknown file type
    # More comparison methods here

def compare(prefix, dir1, dir2):
  """
  Recursively diff two directories, checking metadata then calling checksum
  """
  list1 = []
  list2 = []
  if len(include_patterns) != 0:
    for pattern in include_patterns:
      list1.extend([el.replace(dir1,'',1) for el in glob.glob(os.path.join(dir1, pattern),recursive=True)])
      list2.extend([el.replace(dir2,'',1) for el in glob.glob(os.path.join(dir2, pattern),recursive=True)])
  else:
    list1 = sorted(os.listdir(dir1))
    list2 = sorted(os.listdir(dir2))

  for entry in list1:
    name = os.path.join(prefix, entry)
    name1 = os.path.join(dir1, entry)
    name2 = os.path.join(dir2, entry)
    if ignore(name):
      continue
    if entry in list2:
      if os.path.islink(name1) and os.path.islink(name2):
        link1 = os.readlink(name1)
        link2 = os.readlink(name2)
        if link1 != link2:
          # Symlink differs
          diff_list.append(name)
        continue
      elif os.path.islink(name1) or os.path.islink(name2):
        # File type differs
        diff_list.append(name)
        continue
      stat1 = os.stat(name1)
      stat2 = os.stat(name2)
      type1 = stat1.st_mode & ~0o777
      type2 = stat2.st_mode & ~0o777
      if type1 != type2:
        # Metadata file type differs
        continue
      if stat1.st_mode != stat2.st_mode:
        # Add new element in permission changed list with corresponding octal permission representation
        permission_list[name]=oct(stat2.st_mode)[-3:]
      if stat1.st_uid != stat2.st_uid or stat1.st_gid != stat2.st_gid:
        # Add new element in owner/group id changed list with user id & group id
        ugid_list[name]=[]
        ugid_list[name].append(stat2.st_uid)
        ugid_list[name].append(stat2.st_gid)
      if os.path.isdir(name1):
        compare(name, name1, name2)
      elif os.path.isfile(name1):
        if md5_checksum(name1) != md5_checksum(name2):
          diff_list.append(name)
      # else:
        # Unknown file type
        # More comparison methods here
    else:
      print("%s: Only in %s" % (name, dir1))
      del_list.append(name)
  # Check if there are new files/folders
  for entry in list2: 
    name = os.path.join(prefix, entry)
    name1 = os.path.join(dir1, entry)
    name2 = os.path.join(dir2, entry)
    if ignore(name):
      continue
    if entry not in list1:
      print("%s: Only in %s" % (name, dir2))
      diff_list.append(name)


def gen(diff_list, del_list, permission_list, ugid_list, new_dir):
  """
  Call all generating functions
  """
  if len(diff_list)!=0:
    print ("Generating %s ..." % tar_name)
    gen_tar_file(new_dir,diff_list)
  if len(del_list)!=0 or len(permission_list)!=0 or len(ugid_list)!=0:
    print ("Generating %s ..." % script_name)
    gen_script(del_list,permission_list,ugid_list)
    os.chmod(script_name,0o777)

def main():
  parser = argparse.ArgumentParser()
  subparsers = parser.add_subparsers(dest='command')

  generate = subparsers.add_parser('generate',
      help='generate delta tar file and a script')
  generate.add_argument('--exclude',action='append',nargs='+',
      help='exclude files matching',metavar='PATTERN')
  generate.add_argument('--include',action='append',nargs='+',
      help='only including matching files',metavar='PATTERN')

  parser.add_argument('dir1',help='The new target folder')
  parser.add_argument('dir2', help='The old target folder')
  
  args = parser.parse_args()

  # Check if option --exclude | --include set
  if args.exclude:
    global exclude_patterns
    exclude_patterns = [el for elements in args.exclude for el in elements]
  if args.include:
    global include_patterns
    include_patterns = [el for elements in args.include for el in elements]

  # Start comparing
  compare('', args.dir2, args.dir1)

  print ("==================================================================")
  print ("Number of different or new files/folders: " + str(len(diff_list)))
  print(*diff_list, sep = "\n")
  print ("==================================================================")
  print ("Number of deleted files/folders: " + str(len(del_list)))
  print(*del_list, sep = "\n")
  print ("==================================================================")
  print ("Number of different permission files/folders: " + str(len(permission_list.keys())))
  print (*permission_list.keys(), sep = "\n")
  print ("==================================================================")
  print ("Number of different owner/group id files/folders: " + str(len(ugid_list.keys())))
  print (*ugid_list.keys(), sep = "\n")
  print ("==================================================================")

  # Action for positional arguments
  if args.command == 'generate':
    gen(diff_list, del_list, permission_list, ugid_list, args.dir1)
  else:
    print ("Unknown argument %s" % args.command)

  print ("DONE.")

if __name__ == '__main__':
  main()
