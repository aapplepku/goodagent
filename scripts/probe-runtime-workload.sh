#!/bin/sh
# Metadata only. Never read environ, cmdline, descriptor contents, or service data.
set -eu
printf 'VERSION\t1\nSELF\t%s\n' "$$"
observer_uid=$(id -u)
printf 'OBSERVER_UID\t%s\n' "$observer_uid"
case "$observer_uid" in 0|''|*[!0-9]*) printf 'ERROR\tobserver-must-be-nonroot\n'; exit 1;; esac
printf 'KERNEL\t%s\n' "$(uname -r)"
encode() { base64 | tr -d '\n'; printf '\n'; }
printf 'MOUNTS\t'
encode < /proc/1/mountinfo
count=0
observed=
for directory in /proc/[0-9]*; do
    pid=${directory##*/}
    [ "$pid" = "$$" ] && continue
    count=$((count + 1))
    if [ "$count" -gt 256 ]; then printf 'ERROR\tprocess-limit\n'; exit 1; fi
    [ -r "$directory/stat" ] || { printf 'ERROR\tstat-unreadable-%s\n' "$pid"; continue; }
    printf 'BEGIN\t%s\t' "$pid"
    encode < "$directory/stat"
    observed="$observed $pid"
    state=
    while IFS= read -r line; do
        case "$line" in
            State:*) state=${line#State:};;
            Uid:*|Gid:*|PPid:*|CapInh:*|CapEff:*|CapPrm:*|CapBnd:*|CapAmb:*|NoNewPrivs:*|Seccomp:*)
                printf 'STATUS\t%s\t%s\n' "$pid" "$line";;
        esac
    done < "$directory/status"
    case "$state" in
        *Z*) printf 'END\t%s\t' "$pid"; encode < "$directory/stat"; continue;;
    esac
    if target=$(readlink "$directory/exe"); then
        printf 'EXE\t%s\t' "$pid"; printf '%s' "$target" | encode
    else
        printf 'ERROR\texe-unreadable-%s\n' "$pid"
    fi
    if [ -r "$directory/maps" ]; then
        printf 'MAPS\t%s\t' "$pid"; head -c 1048577 "$directory/maps" | encode
    else
        printf 'ERROR\tmaps-unreadable-%s\n' "$pid"
    fi
    if [ ! -r "$directory/fd" ] || [ ! -x "$directory/fd" ]; then
        printf 'ERROR\tdescriptors-unreadable-%s\n' "$pid"
    else
        descriptors=0
        for descriptor in "$directory"/fd/*; do
            [ "$descriptor" = "$directory/fd/*" ] && break
            [ -L "$descriptor" ] || { printf 'ERROR\tdescriptor-raced-%s\n' "$pid"; continue; }
            descriptors=$((descriptors + 1))
            if [ "$descriptors" -gt 512 ]; then printf 'ERROR\tdescriptor-limit-%s\n' "$pid"; break; fi
            fd=${descriptor##*/}
            if target=$(readlink "$descriptor"); then
                printf 'FD\t%s\t%s\t' "$pid" "$fd"; printf '%s' "$target" | encode
                while IFS= read -r line; do
                    case "$line" in flags:*|mnt_id:*|ino:*) printf 'FDINFO\t%s\t%s\t%s\n' "$pid" "$fd" "$line";; esac
                done < "$directory/fdinfo/$fd"
                if target=$(readlink "$descriptor"); then
                    printf 'FDVERIFY\t%s\t%s\t' "$pid" "$fd"; printf '%s' "$target" | encode
                    while IFS= read -r line; do
                        case "$line" in flags:*|mnt_id:*|ino:*) printf 'FDINFOVERIFY\t%s\t%s\t%s\n' "$pid" "$fd" "$line";; esac
                    done < "$directory/fdinfo/$fd"
                else
                    printf 'ERROR\tdescriptor-raced-%s-%s\n' "$pid" "$fd"
                fi
            else
                printf 'ERROR\tdescriptor-raced-%s-%s\n' "$pid" "$fd"
            fi
        done
    fi
    if [ -r "$directory/stat" ]; then
        printf 'END\t%s\t' "$pid"; encode < "$directory/stat"
    else
        printf 'ERROR\tprocess-exited-%s\n' "$pid"
    fi
done
for pid in $observed; do
    if [ -r "/proc/$pid/stat" ]; then
        printf 'FINAL\t%s\t' "$pid"; encode < "/proc/$pid/stat"
    else
        printf 'ERROR\tfinal-process-missing-%s\n' "$pid"
    fi
done
printf 'FINISHED\n'
