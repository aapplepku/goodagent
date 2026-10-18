#!/bin/sh
set -eu

# Refresh distribution security fixes before removing unused entrypoints.
apt-get update
apt-get upgrade -y
rm -rf /var/lib/apt/lists/*

# Account creation and package scripts must finish before this final-runtime step.
sh /usr/local/sbin/prune-runtime-acl --image
rm /usr/local/sbin/prune-runtime-acl

# These service images do not mount filesystems, interpret Perl, or unpack LZH.
# Keep package metadata for transparent scanner/SBOM reporting, not hidden findings.
rm -f /usr/bin/perl /usr/bin/perl5.* /usr/bin/infocmp /usr/bin/gzip \
    /usr/bin/mount /usr/bin/umount /usr/bin/nsenter /usr/bin/unshare \
    /usr/sbin/mount /usr/sbin/umount /usr/sbin/nsenter /usr/sbin/unshare
find / -xdev -type f \( -perm -4000 -o -perm -2000 \) -exec chmod a-s {} +
