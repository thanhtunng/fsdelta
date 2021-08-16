# fsdelta
- A tool to generate file system deltas

## Overview
Creating reproducible RAW images can be difficult. When doing and rdiff between 2 RAW images, the delta files can become very big because of that lack of reproducibility. \
Instead of using RAW images, we could work at the file-level. Rdiff can work on files, but only one by one, and the binary deltas can become very big due to metadata. \
This tool is a simple tool that does not binary deltas, only file-level deltas (e.g.: add or remove files/links/metadata). This will make it easier to have a single tarball with all the updates (new files, modified files, new links) and a simple script to remove files/folders that do not exist anymore and change metadata of files according to new update

## Usage
- Generate the delta file with arguments are directories or tarballs (currently support gzip - .gz, bzip2 - bz2, lzma - .xz)
```
$ sudo python3 fsdelta.py old.tar.gz new.tar.gz [OPTIONS]
$ sudo python3 fsdelta.py oldfs/ newfs/ [OPTIONS]
  delta.tar.gz <-- tarball with new or modified files
  delta.sh <-- script that deletes files and changes file metadata if necessary
```
- Options:
```
    --exclude PATTERN PATTERN ...      (exclude files matching PATTERN <-- used when we don't want to update specific files)
    --include PATTERN PATTERN ...       (only include files matching PATTERN <-- used when we only want to update specific files)
```
For PATTERN we can use asteriscs or use complete paths (not only filename), which follows the rules used by the Unix shell (refer to <a href="https://docs.python.org/3/library/glob.html">glob</a> or <a href="https://docs.python.org/3/library/fnmatch.html">fnmatch</a> for more detail) \
Patterns can be separated by space or repeat options
- Example:
```
$ sudo python3 fsdelta.py oldfs/ newfs/ --exclude 'dev' 'tmp/a.*' --include 'tmp/**' 'opt'
$ sudo python3 fsdelta.py old.tar.gz new.tar.gz --include 'opt/**' 'tmp/*' --exclude 'opt/*.txt'
```
- Apply the delta
```
$ sudo tar zxvfp delta.tar.gz -C old/ <-- it will overwrite old files, and create new files, folders or links
$ sudo ./delta.sh old/ <-- it will delete or change the metadata of some files/folders
```
- Generate and apply using Makefile:
```
$ sudo make generate OLD=oldfs/ NEW=newfs/ EXTRA="[OPTIONS]"
$ sudo make generate OLD=old.tar.gz NEW=new.tar.gz EXTRA="[OPTIONS]"
$ sudo make apply OLD=old.tar.gz

e.g: sudo make generate OLD=old.tar.gz NEW=new.tar.gz EXTRA='--include "opt/**" "tmp/*"
--exclude "opt/*.txt"'
```
