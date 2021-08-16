#!/usr/bin/env python3
#
# Copyright © 2021 Toshiba corporation
# Maintainer: Vu Thanh Tung (thanhtungvu.hust@gmail.com)
#

import argparse
import os, sys, stat, time
import glob, fnmatch
import tarfile
import hashlib
import pathlib, shutil
import atexit

diff_list = []        # list of changed files/folders (link,checksum) or new files/folders
del_list = []         # list of deleted files/folders (only in base package)
permission_list = {}  # list of changed typical permission files/folders
ugid_list = {}        # list of changed owner/group id files/folders
exclude_patterns = ["$^"]   # Pattern list which is not in comparison
include_patterns = []       # Pattern list which will be compared
tar_name = "delta.tar.gz"   # name of the tarfile will be generated
script_name = "delta.sh"    # name of script will be generatd

# Directory for extracted files if tarballs
extract_oldfs = None
extract_newfs = None

def tar_to_list_filter(archive, extract_dir):
    """
    Function to write files extracted from tarball to list which match pattern
    """
    file_list = []
    for member in archive:
        for pattern in include_patterns:
            if fnmatch.fnmatch(member.name, pattern):
                file_list.append(member.name)
                archive.extract(member.name, extract_dir)
    return file_list

def gen_tar_file(prefix, diff_list):
    """
    Function to generate a delta tar file by reading from a list
    """
    with tarfile.open(tar_name, "w:gz") as target:
        for name in diff_list:
            target.add(os.path.join(prefix, name), arcname=name)

def gen_script(del_list, permission_list, ugid_list):
    """
    Function to generate a script to:
      - Remove files/folders in base package which deleted in new package
      - Update metadata of files/folders by new package
    """
    with open(script_name, 'w+') as out:
        print('#!/bin/bash \n# Usage : sudo ./%s folder/\n' %
              script_name, file=out)
        print("declare -a DEL_LIST=(", file=out)
        for obj in del_list:
            out.write("  %s\n" % (obj))
        out.write(")\n")

        print("declare -A PERMISSION_LIST=(", file=out)
        for key, value in permission_list.items():
            out.write("  [%s]=%s\n" % (key, value))
        out.write(")\n")

        print('for obj in "${DEL_LIST[@]}"\n\
do\n  rm -rf $1/$obj\n\
done\n\
for obj in "${!PERMISSION_LIST[@]}"\n\
do\n  chmod ${PERMISSION_LIST[$obj]} $1/$obj\n\
done\n', file=out)
        for key, values in ugid_list.items():
            print('chown %s:%s $1/%s' %
                  (values[0], values[1], key), file=out)

def ignore(name):
    """
    Files/folders to ignore when comparing
    """
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False

def md5_checksum(filename, block_size=2**20):
    """
    Calculate MD5 checksum of a file
    """
    f = open(filename, "r", encoding='ISO-8859-1')
    md5 = hashlib.md5()
    data = f.read(block_size)
    while data:
        md5.update(data.encode('ISO-8859-1'))
        data = f.read(block_size)
    f.close()
    return md5.digest()

def diff_meta(name, old_file, new_file):
    """
    Function to compare metadata
    name: name of file/folder to compare
    old_file, new_file: name of file to compare within corresponding folders
        e.g: name = a.txt, old_file = oldfs/a.txt, new_file = newfs/a.txt
    """
    if os.path.islink(old_file) and os.path.islink(new_file):
        old_link = os.readlink(old_file)
        new_link = os.readlink(new_file)
        if old_link != new_link:
            # Symlink differs
            diff_list.append(name)
        return 1
    elif os.path.islink(old_file) or os.path.islink(new_file):
        # File type differs
        diff_list.append(name)
        return 1
    old_stat = os.stat(old_file)
    new_stat = os.stat(new_file)
    old_type = old_stat.st_mode & ~0o777
    new_type = new_stat.st_mode & ~0o777
    if old_type != new_type:
        # Metadata file type differs
        return 1
    if old_stat.st_mode != new_stat.st_mode:
        # Add new element in permission changed list with corresponding octal permission representation
        permission_list[name] = oct(new_stat.st_mode)[-3:]
    if old_stat.st_uid != new_stat.st_uid or old_stat.st_gid != new_stat.st_gid:
        # Add new element in owner/group id changed list with user id & group id
        ugid_list[name] = []
        ugid_list[name].append(new_stat.st_uid)
        ugid_list[name].append(new_stat.st_gid)
    # else:
        # More comparison methods here

def compare(prefix, oldfs, newfs):
    """
    This function wraps all diff methods (diff metadata, checksum)
    If objects are tarballs, extract to temporary dir, then do differing
    Otherwise, if include patterns set, write matched files/folders to list, then do differing
    Else recursively diff two directories
    """
    if '*' in exclude_patterns or '**' in exclude_patterns: # If exclude all
        return
    old_list = []
    new_list = []
    # Flag to diff recursive or not
    recursive = 0
    # If not directory, assume those are tarballs
    if not os.path.isdir(oldfs) and not os.path.isdir(newfs):
        try:
            old_archive = tarfile.open(os.path.join(prefix, oldfs))
        except tarfile.ReadError:
            print ("%s is not neither tarball nor directory" % oldfs)
            sys.exit(1)
        try:
            new_archive = tarfile.open(os.path.join(prefix, newfs))
        except tarfile.ReadError:
            print ("%s is not neither tarball nor directory" % newfs)
            sys.exit(1)

        # Extract tarballs to temporary directories named the first substring of tarname
        # e.g: new.tar.gz -> new/
        global extract_oldfs
        extract_oldfs = os.path.join(prefix, str(oldfs).split('.')[0])
        # If extracted directory exists, exit
        if os.path.exists(extract_oldfs):
            print ("%s/ already existed, can't extract %s" % (extract_oldfs, oldfs))
            sys.exit(1)
        global extract_newfs
        extract_newfs = os.path.join(prefix, str(newfs).split('.')[0])
        if os.path.exists(extract_newfs):
            print ("%s/ already existed, can't extract %s" % (extract_newfs, newfs))
            sys.exit(1)

        # If include patterns set, just extract matched elements to extract_dir
        if len(include_patterns) != 0 and "**" not in include_patterns and "*" not in include_patterns:
            old_list = tar_to_list_filter(old_archive, extract_oldfs)
            new_list = tar_to_list_filter(new_archive, extract_newfs)
        # Else extract all to dir
        else:
            for member in old_archive:
                old_list.append(member.name)
            for member in new_archive:
                new_list.append(member.name)
            old_archive.extractall(extract_oldfs, members=old_archive.getmembers())
            new_archive.extractall(extract_newfs, members=new_archive.getmembers())
        oldfs = extract_oldfs
        newfs = extract_newfs
        old_archive.close()
        new_archive.close()

    elif len(include_patterns) != 0 and "**" not in include_patterns and "*" not in include_patterns:
        if '/' not in oldfs:
            oldfs = oldfs + '/'
        if '/' not in newfs:
            newfs = newfs + '/'
        for pattern in include_patterns:
            if len(glob.glob(os.path.join(oldfs, pattern), recursive=True)):
                old_list.extend([el.replace(oldfs, '', 1) for el in glob.glob(os.path.join(oldfs, pattern), recursive=True)])
            if len(glob.glob(os.path.join(newfs, pattern), recursive=True)):
                new_list.extend([el.replace(newfs, '', 1) for el in glob.glob(os.path.join(newfs, pattern), recursive=True)])
    else:
        recursive = 1
        old_list = os.listdir(oldfs)
        new_list = os.listdir(newfs)

    # Start differing
    for entry in old_list:
        name = os.path.join(prefix, entry)
        if ignore(name):
            continue
        old_file = os.path.join(oldfs, entry)
        if not os.path.exists(old_file):
            continue
        new_file = os.path.join(newfs, entry)
        if entry in new_list and os.path.exists(new_file):
            if diff_meta(name, old_file, new_file) == 1:    # Metadata differing
                continue
            if recursive == 1 and os.path.isdir(old_file):  # Recursive differing
                compare(name, old_file, new_file)
            elif os.path.isfile(old_file):
                if md5_checksum(old_file) != md5_checksum(new_file):  # Checksum comparison
                    diff_list.append(name)
            # else:
                # Unknown file type
        else:
            del_list.append(name)   # Deleted files - files only in old package, not in new package
    # Check if there are new files/folders
    for entry in new_list:
        name = os.path.join(prefix, entry)
        if ignore(name):
            continue
        if entry not in old_list:
            diff_list.append(name)  # New files - files only in new package, not in old package

def generate(diff_list, del_list, permission_list, ugid_list, newfs):
    """
    Call all generating functions
    """
    if extract_newfs != None: # Check if tarball set and extracted
        newfs =  extract_newfs
    if len(diff_list) != 0:
        print("Generating %s ..." % tar_name)
        gen_tar_file(newfs, diff_list)
    if len(del_list) != 0 or len(permission_list) != 0 or len(ugid_list) != 0:
        print("Generating %s ..." % script_name)
        gen_script(del_list, permission_list, ugid_list)
        os.chmod(script_name, 0o744)

@atexit.register
def clean():
    # Remove temporary extracted directory if comparing tarballs
    if extract_oldfs != None :
        shutil.rmtree(extract_oldfs, ignore_errors=True)
    if extract_newfs != None :
        shutil.rmtree(extract_newfs, ignore_errors=True)

def elapsed_time(prefix=''):
    """
    Function to measure the consumed amount of time
    """
    e_time = time.time()
    if not hasattr(elapsed_time, 's_time'):
        elapsed_time.s_time = e_time
    else:
        print(f'{prefix}: {e_time - elapsed_time.s_time:.2f} sec')
        elapsed_time.s_time = e_time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exclude', action='append', nargs='*',
                          help='exclude matched files', metavar='PATTERN')
    parser.add_argument('--include', action='append', nargs='*',
                          help='only include matched files', metavar='PATTERN')
    parser.add_argument('oldfs', help='The old fs/tarfile')
    parser.add_argument('newfs', help='The new fs/tarfile')

    args = parser.parse_args()

    # Check if option --exclude | --include set
    if args.exclude:
        global exclude_patterns
        exclude_patterns = [el for elements in args.exclude for el in elements]
    if args.include:
        global include_patterns
        include_patterns = [el for elements in args.include for el in elements]

    # Comparing
    print ("Comparing %s and %s ..." % (args.oldfs, args.newfs))
    elapsed_time()
    compare('', args.oldfs, args.newfs)

    print("==================================================================")
    print("Number of changed or new files/folders: " + str(len(diff_list)))
    print(*diff_list, sep="\n")
    print("==================================================================")
    print("Number of deleted files/folders: " + str(len(del_list)))
    print(*del_list, sep="\n")
    print("==================================================================")
    print("Number of changed permission files/folders: " +
          str(len(permission_list.keys())))
    print(*permission_list.keys(), sep="\n")
    print("==================================================================")
    print("Number of changed owner/group id files/folders: " +
          str(len(ugid_list.keys())))
    print(*ugid_list.keys(), sep="\n")
    print("==================================================================")

    # Generate delta
    generate(diff_list, del_list, permission_list, ugid_list, args.newfs)

    # Clean temporary data
    clean()

    elapsed_time("Total time")
    print("DONE.")

if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt):
        clean()
        raise
