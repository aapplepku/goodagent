#!/bin/sh
# Image metadata only: network none, read-only, no host/store mounts or credentials.
# Caller must declare and record read permissions (possibly DAC_READ_SEARCH).
# Inventory privileges are NOT normal-entrypoint/runtime privilege evidence.
# No payload reads, writes, package execution, vulnerability decisions or waivers.
# Protocol v1: tab-separated records; paths/targets are base64, diagnostics are hex.
# ROOT: test-mode (0=image, 1=fixture), path. STAT: linux or bsd-test-only.
# ENTRY: source, path, kind, octal permissions, uid, gid, size, device, inode, target.
# MISSING: package source, path. Package lists can outlive removed files.
# FINISHED: complete|incomplete, input records, emitted records, errors, dropped.
# Require exit 0 AND a complete FINISHED record; retain failures and stderr too.
# The caller must impose a wall-clock timeout and bind image/probe/output hashes.
# Package metadata uses a shell/stat/encoding worker per path (costly for Perl).
set -u
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL
root=/
test_mode=0
if [ "$#" -ne 0 ]; then
    if [ "$#" -ne 2 ] || [ "$1" != --test-root ]; then
        printf 'usage: sh probe-image-components.sh [--test-root ISOLATED_DIRECTORY]\n' >&2
        exit 2
    fi
    root=$2
    case "$root" in
        /tmp/image-component-probe.*|/private/tmp/image-component-probe.*) ;;
        *) printf 'unsafe test root\n' >&2; exit 2;;
    esac
    case "${root##*/}" in image-component-probe.?*) ;; *) exit 2;; esac
    physical=$(CDPATH= cd -P "$root" 2>/dev/null && pwd -P) || exit 2
    [ "$physical" = "$root" ] && [ ! -L "$root" ] || exit 2
    # Only a direct child of the temporary directory, never a checkout or store.
    case "${root%/*}" in /tmp|/private/tmp) ;; *) exit 2;; esac
    test_mode=1
fi
for tool in find sh stat readlink base64 tr awk; do
    command -v "$tool" >/dev/null 2>&1 || {
        printf 'ERROR\tmissing-tool-%s\nFINISHED\tincomplete\t0\t0\t1\t0\n' "$tool"
        exit 1
    }
done

# A constant worker, passed paths as arguments, not interpolated shell source.
metadata='
set -u
root=$1; style=$2; source=$3; shift 3
encode() {
    encoded=$(printf "%s" "$1" | base64) || return "$?"
    printf "%s" "$encoded" | tr -d "\n"
}
for path do
    relative=${path#"$root"}; [ "$root" = / ] && relative=$path
    encoded_path=$(encode "$relative") || {
        printf "ERROR\tpath-encoding-failed\n"; continue;
    }
    [ -n "$encoded_path" ] || { printf "ERROR\tpath-encoding-empty\n"; continue; }
    case "$source" in package:*)
        case "$relative" in
            /*) ;; *) printf "ERROR\tinvalid-package-path\n"; continue;;
        esac
        case "$relative/" in
            *//*|*/../*|*/./*|/proc/*|/sys/*|/dev/*|/run/*)
                printf "ERROR\tunsafe-package-path\n"; continue;;
        esac
        ancestor=${path%/*}; [ -n "$ancestor" ] || ancestor=/
        while [ ! -e "$ancestor" ] && [ ! -L "$ancestor" ]; do
            ancestor=${ancestor%/*}; [ -n "$ancestor" ] || ancestor=/
        done
        physical=$(CDPATH= cd -P "$ancestor" && pwd -P) || {
            printf "ERROR\tpackage-parent-unreadable\n"; continue;
        }
        case "$physical/" in /proc/*|/sys/*|/dev/*|/run/*)
            printf "ERROR\tpackage-parent-excluded\n"; continue;;
        esac
        if [ "$root" != / ]; then
            case "$physical/" in "$root/"*) ;;
                *) printf "ERROR\tpackage-parent-escaped\n"; continue;;
            esac
        fi
        if [ ! -e "$path" ] && [ ! -L "$path" ]; then
            printf "MISSING\t%s\t%s\n" "$source" "$encoded_path"
            continue
        fi;;
    esac
    if [ "$style" = linux ]; then
        facts=$(stat -c "%a %u %g %s %d %i" "$path")
    else
        facts=$(stat -f "%Lp %u %g %z %d %i" "$path")
    fi
    if [ "$?" -ne 0 ]; then printf "ERROR\tstat-failed\n"; continue; fi
    kind=other; target=-
    if [ -L "$path" ]; then
        kind=symlink
        # The sentinel preserves trailing newlines through command substitution.
        if target=$(readlink -n "$path" && printf .); then
            target=${target%.}
            target=$(encode "$target") || {
                printf "ERROR\ttarget-encoding-failed\n"; continue;
            }
            [ -n "$target" ] || { printf "ERROR\ttarget-encoding-empty\n"; continue; }
        else printf "ERROR\treadlink-failed\n"; continue; fi
    elif [ -f "$path" ]; then kind=file
    elif [ -d "$path" ]; then kind=directory
    fi
    facts=$(printf "%s" "$facts" | tr " " "\t") || {
        printf "ERROR\tmetadata-formatting-failed\n"; continue;
    }
    printf "ENTRY\t%s\t%s\t%s\t%s\t%s\n" "$source" "$encoded_path" "$kind" "$facts" "$target"
done
'

package_path() {
    package=$1; path=$2
    [ "$path" != /. ] && [ "$path" != / ] || return 0
    case "$path" in /*) ;; *) printf 'ERROR\tinvalid-package-path\n'; return 0;; esac
    case "$path/" in *//*|*/../*|*/./*|/proc/*|/sys/*|/dev/*|/run/*)
        printf 'ERROR\tunsafe-package-path\n'; return 0;;
    esac
    prefix=$root; [ "$root" != / ] || prefix=
    sh -c "$metadata" component-meta "$root" "$style" "package:$package" "$prefix$path" ||
        printf 'ERROR\tpackage-metadata-worker-failed\n'
}

packages() {
    info=${root%/}/var/lib/dpkg/info
    if [ -d "$info" ] || [ -L "$info" ]; then
        printf 'BACKEND\tdpkg-path-lists\n'
        physical=$(CDPATH= cd -P "$info" && pwd -P) || return 1
        if [ "$physical" != "$info" ] || [ ! -r "$info" ] || [ ! -x "$info" ]; then
            printf 'ERROR\tunsafe-or-unreadable-package-directory\n'; return 1
        fi
        for list in "$info"/*.list; do
            package=${list##*/}; package=${package%.list}
            case "$package" in
                ncurses*|libncurses*|libtinfo*|perl*|libperl*|libarchive-tar-perl*|systemd*|libsystemd*|libudev*|libacl*|mount*|libmount*|libblkid*|libsmartcols*|util-linux*|busybox*) ;;
                *) continue;;
            esac
            case "$package" in *[!a-zA-Z0-9+._:-]*)
                printf 'ERROR\tinvalid-package-name\n'; continue;;
            esac
            if [ ! -f "$list" ] || [ -L "$list" ] || [ ! -r "$list" ]; then
                printf 'ERROR\tunsafe-or-unreadable-package-list\n'; continue
            fi
            printf 'PACKAGE\tdpkg\t%s\n' "$package"
            while IFS= read -r path || [ -n "$path" ]; do
                package_path "$package" "$path"
            done < "$list" || printf 'ERROR\tpackage-list-read-failed\n'
        done
    elif [ "$test_mode" = 0 ] && command -v apk >/dev/null 2>&1; then
        printf 'BACKEND\tapk-path-lists\n'
        # Query only the installed database, without opening repository indexes.
        names=$(apk --no-network --repositories-file /dev/null info) || {
            printf 'ERROR\tapk-info-failed\n'; return 1;
        }
        # apk package names cannot contain whitespace or shell metacharacters.
        printf '%s\n' "$names" | while IFS= read -r package; do
            case "$package" in
                ncurses*|libncurses*|libtinfo*|perl*|libperl*|libarchive-tar-perl*|systemd*|libsystemd*|libudev*|libacl*|mount*|libmount*|libblkid*|libsmartcols*|util-linux*|busybox*) ;;
                *) continue;;
            esac
            case "$package" in *[!a-zA-Z0-9+._-]*)
                printf 'ERROR\tinvalid-apk-package-name\n'; continue;;
            esac
            printf 'PACKAGE\tapk\t%s\n' "$package"
            if paths=$(apk --no-network --repositories-file /dev/null info -L "$package"); then
                printf '%s\n' "$paths" | (
                    IFS= read -r header || exit 1
                    case "$header" in "$package"-*' contains:') ;;
                        *) printf 'ERROR\tunsupported-apk-list-format\n'; exit 1;;
                    esac
                    while IFS= read -r path || [ -n "$path" ]; do
                        [ -n "$path" ] || continue
                        package_path "$package" "/$path"
                    done
                ) || printf 'ERROR\tapk-list-parse-failed\n'
            else printf 'ERROR\tapk-list-failed\n'
            fi
        done
    else
        printf 'ERROR\tpackage-path-inspection-unsupported\n'
    fi
}

{
    printf 'VERSION\t1\n'
    if encoded_root=$(printf '%s' "$root" | base64) &&
        encoded_root=$(printf '%s' "$encoded_root" | tr -d '\n') && [ -n "$encoded_root" ]; then
        printf 'ROOT\t%s\t%s\n' "$test_mode" "$encoded_root"
    else printf 'ERROR\troot-encoding-failed\n'; exit 1
    fi
    printf 'SCOPE\tphysical-root-xdev-no-symlink-traversal\n'
    printf 'LIMITATION\tproc-sys-dev-run-and-other-filesystem-descent-excluded\n'
    printf 'LIMITATION\tall-symlink-edges-not-resolved-target-identity\n'
    printf 'LIMITATION\tno-renamed-inlined-static-code-or-hardlink-alias-absence-proof\n'
    printf 'LIMITATION\tmetadata-not-file-content-or-package-integrity-verification\n'
    printf 'LIMITATION\tcaller-must-bind-isolation-image-identity-and-timeout\n'
    printf 'LIMITATION\tcaller-must-record-inventory-read-permissions-not-runtime-privilege-proof\n'
    printf 'LIMITATION\tpackage-path-metadata-uses-per-path-subprocesses\n'
    printf 'LIMITS\t10000\t2097152\t16384\n'
    if stat -c '%a %u %g %s %d %i' "$root" >/dev/null 2>&1; then
        style=linux
    elif [ "$test_mode" = 1 ] && stat -f '%Lp %u %g %z %d %i' "$root" >/dev/null 2>&1; then
        style=bsd-test-only
    else printf 'ERROR\tstat-inspection-unsupported\n'; exit 1
    fi
    printf 'STAT\t%s\n' "$style"
    prefix=${root%/}
    if ! find "$root" -xdev \
        \( -path "$prefix/proc" -o -path "$prefix/sys" -o -path "$prefix/dev" -o -path "$prefix/run" \) -prune -o \
        \( -name 'infocmp*' -o -name 'perl*' -o -name 'miniperl*' -o -name 'libperl*' \
        -o -name 'libacl*' -o -name 'libmount*' \
        -o -path '*/Archive/Tar.pm' -o -path '*/Archive/Tar/*' \
        -o -name 'systemd-homed*' -o -name 'mount*' -o -name 'umount*' -o -name 'nsenter*' -o -name 'unshare*' \
        -o -type l -o \( -type f \( -perm -4000 -o -perm -2000 \) \) \) \
        -exec sh -c "$metadata" component-meta "$root" "$style" filesystem {} +; then
        printf 'ERROR\tfilesystem-traversal-failed\n'
    fi
    packages || printf 'ERROR\tpackage-inspection-failed\n'
    printf 'PRODUCER_FINISHED\n'
} 2>&1 | awk '
    BEGIN { for (i=1; i<256; i++) ord[sprintf("%c", i)]=i }
    function diagnostic(s, out, i) {
        out=""; for (i=1; i<=length(s); i++) out=out sprintf("%02x", ord[substr(s,i,1)])
        return "DIAGNOSTIC_HEX\t" out
    }
    {
        seen++
        if ($0 == "PRODUCER_FINISHED") { finished++; next }
        line=$0; split(line, field, "\t")
        if (field[1] == "ERROR") errors++
        else if (field[1] !~ /^(VERSION|ROOT|SCOPE|LIMITATION|LIMITS|STAT|BACKEND|PACKAGE|ENTRY|MISSING)$/) {
            if (length(line)>4096) dropped++
            errors++; line=diagnostic(substr(line,1,4096))
        }
        if (seen>10000 || length(line)>16384 || bytes+length(line)+1>2097152) { dropped++; next }
        print line; emitted++; bytes+=length(line)+1
    }
    END {
        if (finished != 1) { print "ERROR\tproducer-incomplete"; errors++ }
        if (dropped) { print "ERROR\toutput-limit-exceeded"; errors++ }
        status=(errors ? "incomplete" : "complete")
        printf "FINISHED\t%s\t%d\t%d\t%d\t%d\n", status, seen, emitted, errors, dropped
        exit (errors ? 1 : 0)
    }
'
