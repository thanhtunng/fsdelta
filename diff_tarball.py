#!/usr/bin/env python3
#
# Copyright © 2021 Toshiba corporation
#

import argparse
import os
import sys
import stat
import re
import glob
import fnmatch
import tarfile
import zipfile
import hashlib
import pathlib

# list of changed files/folders (link,checksum) or new files/folders
diff_list = []
del_list = []         # list of deleted files/folders (only in base package)
permission_list = {}  # list of different typical permission files/folders
ugid_list = {}        # list of different owner/group id files/folders
exclude_patterns = ["$^"]  # Pattern list which is not in comparison
include_patterns = []     # Pattern list which will be compared
tar_name = "delta.tar.gz"
script_name = "delta.sh"

# Dictionary of some compressed file types
magic_dict = {
    "\x1f\x8b\x08": "gz",
    "\x42\x5a\x68": "bz2",
    "\x50\x4b\x03\x04": "zip"
}

def is_tarball_file(obj):
    """
    Function to check if obj is a tarball file which is a type of magic_dict
    """
    if os.path.isdir(obj):
        return False
    max_len = max(len(x) for x in magic_dict)
    with open(obj, encoding="ISO-8859-1") as f:
        file_start = f.read(max_len)
    for magic, _ in magic_dict.items():
        if file_start.startswith(magic):
            return True
    return False

def gen_tar_file(prefix, diff_list):
    """
    Function to generate a delta tar file by reading from a list
    """
    if is_tarball_file(prefix):
        with tarfile.open(prefix, "r:gz") as archive:
            with tarfile.open(tar_name, "w:gz") as target:
                for member in archive.getmembers():
                    name = str(member.name).replace(prefix.split('.')[0],'',1).replace('/','',1)
                    if name in diff_list:
                        target.add(member.name, arcname=name)
    else:
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

        for key, values in ugid_list.items():
            print("declare -a %s_UGID=( %s %s )" %
                  (key.replace('/', '_'), values[0], values[1]), file=out)

        print('for obj in "${DEL_LIST[@]}"\n\
do\n  rm -rf $1/$obj\n\
done\n\
for obj in "${!PERMISSION_LIST[@]}"\n\
do\n  chmod ${PERMISSION_LIST[$obj]} $1/$obj\n\
done\n', file=out)
        for key, value in ugid_list.items():
            print('chown ${%s_UGID[0]}:${%s_UGID[1]} $1/%s' %
                  (key.replace('/', '_'), key.replace('/', '_'), key), file=out)

def ignore(name):
    """
    Files/folders to ignore when comparing
    """
    for pattern in exclude_patterns:
        if re.match(pattern, name) or fnmatch.fnmatch(name, pattern):
            return True
    return False

def md5_checksum(filename, block_size=2**20):
    """
    Calculate MD5 checksum of a file
    """
    f = open(filename, "r", encoding='ISO-8859-1')
    md5 = hashlib.md5()
    while True:
        data = f.read(block_size)
        if not data:
            break
        md5.update(data.encode('ISO-8859-1'))
    f.close()
    return md5.digest()


def diff_meta(name, name1, name2):
    """
    Function to compare metadata
    """
    if os.path.islink(name1) and os.path.islink(name2):
        link1 = os.readlink(name1)
        link2 = os.readlink(name2)
        if link1 != link2:
            # Symlink differs
            diff_list.append(name)
        return 1
    elif os.path.islink(name1) or os.path.islink(name2):
        # File type differs
        diff_list.append(name)
        return 1
    stat1 = os.stat(name1)
    stat2 = os.stat(name2)
    type1 = stat1.st_mode & ~0o777
    type2 = stat2.st_mode & ~0o777
    if type1 != type2:
        # Metadata file type differs
        return 1
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

def tarball_to_list_with_checking(prefix, archive):
    """
    Function to write from tar to list with filter
    """
    file_list = []
    for member in archive:
        element = member.name
        for pattern in include_patterns:
            if re.match(pattern, element) or fnmatch.fnmatch(element, pattern):
                file_list.append(element)
    return file_list

def compare(prefix, dir1, dir2):
    """
    This function wraps all diff methods.
    If include patterns set, write matched files/folders to list, then checking metadata and calling checksum
    Else recursively diff two directories, then checking metadata and calling checksum
    If dir1 and dir2 are tarballs, 
    """
    list1 = []
    list2 = []
    is_tarball = 0
    # Check if tarball first
    if is_tarball_file(dir1) and is_tarball_file(dir2):
        is_tarball = 1
        archive1 = tarfile.open(os.path.join(prefix, dir1),)
        archive2 = tarfile.open(os.path.join(prefix, dir2),)
        extract_dir1 = str(dir1).split('.')[0]
        extract_dir2 = str(dir2).split('.')[0]
        if len(include_patterns) != 0 and "**" not in include_patterns and "*" not in include_patterns:
            list1 = tarball_to_list_with_checking(dir1, archive1)
            list2 = tarball_to_list_with_checking(dir2, archive2)
        else:
            for member1 in archive1:
                list1.append(member1.name)
                archive1.extract(member1.name, extract_dir1)
            for member2 in archive2:
                list2.append(member2.name)
                archive1.extract(member2.name, extract_dir2)
        archive1.close()
        archive2.close()

    elif len(include_patterns) != 0 and "**" not in include_patterns and "*" not in include_patterns:
        for pattern in include_patterns:
            list1.extend([el.replace(dir1, '', 1) for el in glob.glob(
                os.path.join(dir1, pattern), recursive=True)])
            list2.extend([el.replace(dir2, '', 1) for el in glob.glob(
                os.path.join(dir2, pattern), recursive=True)])
    else:
        list1 = sorted(os.listdir(dir1))
        list2 = sorted(os.listdir(dir2))
    for entry in list1:
        name = os.path.join(prefix, entry)
        if ignore(name):
            continue
        if is_tarball == 1:
            name1 = os.path.join(str(dir1).split('.')[0], entry)
            name2 = os.path.join(str(dir2).split('.')[0], entry)
        else:
            name1 = os.path.join(dir1, entry)
            name2 = os.path.join(dir2, entry)
        if entry in list2:
            if diff_meta(name, name1, name2) == 1:
                continue
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
        if ignore(name):
            continue
        if entry not in list1:
            print("%s: Only in %s" % (name, dir2))
            diff_list.append(name)


def gen(diff_list, del_list, permission_list, ugid_list, new_dir):
    """
    Call all generating functions
    """
    if len(diff_list) != 0:
        print("Generating %s ..." % tar_name)
        gen_tar_file(new_dir, diff_list)
    if len(del_list) != 0 or len(permission_list) != 0 or len(ugid_list) != 0:
        print("Generating %s ..." % script_name)
        gen_script(del_list, permission_list, ugid_list)
        os.chmod(script_name, 0o777)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    generate = subparsers.add_parser('generate',
                                     help='generate delta tar file and a script')
    generate.add_argument('--exclude', action='append', nargs='+',
                          help='exclude files matching', metavar='PATTERN')
    generate.add_argument('--include', action='append', nargs='+',
                          help='only including matching files', metavar='PATTERN')

    parser.add_argument('dir1', help='The new target folder')
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

    print("==================================================================")
    print("Number of different or new files/folders: " + str(len(diff_list)))
    print(*diff_list, sep="\n")
    print("==================================================================")
    print("Number of deleted files/folders: " + str(len(del_list)))
    print(*del_list, sep="\n")
    print("==================================================================")
    print("Number of different permission files/folders: " +
          str(len(permission_list.keys())))
    print(*permission_list.keys(), sep="\n")
    print("==================================================================")
    print("Number of different owner/group id files/folders: " +
          str(len(ugid_list.keys())))
    print(*ugid_list.keys(), sep="\n")
    print("==================================================================")

    # Action for positional arguments
    if args.command == 'generate':
        gen(diff_list, del_list, permission_list, ugid_list, args.dir1)
    else:
        print("Unknown argument %s" % args.command)

    print("DONE.")

if __name__ == '__main__':
    main()
