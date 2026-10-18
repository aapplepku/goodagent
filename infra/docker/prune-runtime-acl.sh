#!/bin/sh
# Final-image pruning only; package metadata and licenses are deliberately retained.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
LC_ALL=C
export LC_ALL

fail() { printf 'ACL pruning refused: %s\n' "$1" >&2; exit 1; }

case "${1:-}" in
    --image)
        [ "$#" = 1 ] && [ "$0" = /usr/local/sbin/prune-runtime-acl ] || fail 'image invocation'
        root=/
        architecture=$(dpkg --print-architecture) || fail 'architecture unavailable'
        ;;
    --test-root)
        [ "$#" = 3 ] || fail 'test arguments'
        root=$2
        architecture=$3
        case "$root" in
            /tmp/runtime-acl-prune.?*|/private/tmp/runtime-acl-prune.?*) ;;
            *) fail 'isolated test root required';;
        esac
        case "${root%/*}" in /tmp|/private/tmp) ;; *) fail 'test root must be a direct child';; esac
        [ ! -L "$root" ] || fail 'symlink test root'
        physical=$(CDPATH= cd -P "$root" && pwd -P) || fail 'test root unavailable'
        [ "$physical" = "$root" ] || fail 'noncanonical test root'
        ;;
    *) fail 'explicit --image or --test-root required';;
esac
case "$architecture" in
    arm64) triplet=aarch64-linux-gnu;;
    amd64) triplet=x86_64-linux-gnu;;
    *) fail 'unsupported architecture';;
esac
cd "$root"

# Every deletion parent is a real directory, never a path through a host/test link.
for directory in usr usr/bin usr/sbin usr/lib "usr/lib/$triplet" var var/lib var/lib/dpkg var/lib/dpkg/info; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || fail 'unexpected parent directory'
done
link_target() {
    # The sentinel prevents command substitution from stripping target newlines.
    readlink -n "$1" && printf '.'
}
for directory in bin sbin lib; do
    [ -L "$directory" ] || fail 'usrmerge link missing'
    [ "$(link_target "$directory")" = "usr/$directory." ] || fail 'unexpected usrmerge link'
done

package="var/lib/dpkg/info/libacl1:$architecture.list"
set -- var/lib/dpkg/info/libacl1*.list
[ "$#" = 1 ] && [ "$1" = "$package" ] || fail 'foreign or unexpected package list'
[ -f "$package" ] && [ ! -L "$package" ] || fail 'package list unavailable'
[ "$(wc -c < "$package")" -le 65536 ] || fail 'package list too large'
library=$(awk -v prefix="/usr/lib/$triplet/" '
    seen[$0]++ { bad=1 }
    $0 == "/." || $0 == "/" { next }
    $0 == prefix "libacl.so.1" { soname++; next }
    index($0, prefix "libacl.so.1.") == 1 {
        name=substr($0, length(prefix)+1)
        if (name !~ /^libacl\.so\.1\.[0-9]+(\.[0-9]+)*$/) bad=1
        real++; file=name; next
    }
    $0 == "/usr" || $0 == "/usr/lib" || $0 == substr(prefix,1,length(prefix)-1) { next }
    $0 == "/usr/share" || $0 == "/usr/share/doc" || $0 == "/usr/share/doc/libacl1" { next }
    /^\/usr\/share\/doc\/libacl1\/[A-Za-z0-9_.+-]+$/ { next }
    $0 == "/usr/share/lintian" || $0 == "/usr/share/lintian/overrides" { next }
    $0 == "/usr/share/lintian/overrides/libacl1" { next }
    { bad=1 }
    END { if (bad || soname != 1 || real != 1) exit 1; print file }
' "$package") || fail 'unexpected package-owned paths'
soname="usr/lib/$triplet/libacl.so.1"
regular="usr/lib/$triplet/$library"
[ -L "$soname" ] && [ "$(link_target "$soname")" = "$library." ] || fail 'unexpected SONAME link'

consumers='usr/bin/cp usr/bin/install usr/bin/mv usr/bin/sed usr/bin/tar usr/sbin/useradd usr/sbin/usermod'
if stat -c '%h' "$package" >/dev/null 2>&1; then
    stat_style=gnu
else
    stat_style=bsd
fi
for path in $consumers "$regular"; do
    [ -f "$path" ] && [ ! -L "$path" ] || fail 'missing or nonregular removal target'
done
for path in $consumers "$regular" "$soname"; do
    if [ "$stat_style" = gnu ]; then
        links=$(stat -c '%h' "$path") || fail 'target metadata unavailable'
    else
        links=$(stat -f '%l' "$path") || fail 'target metadata unavailable'
    fi
    [ "$links" = 1 ] || fail 'hardlinked removal target'
done

work=$(mktemp -d /tmp/runtime-acl-check.XXXXXXXX) || fail 'temporary inventory unavailable'
trap 'rm -rf -- "$work"' 0
trap 'exit 1' HUP INT TERM
# Physical traversal: link targets are metadata, never followed or executed.
find . -xdev \( -type l -o -name 'libacl.so*' -o -name 'libacl-*.so*' -o -name libacl.a \) \
    -exec sh -c '
        set -eu
        newline="
"
        tab=$(printf "\t")
        for path do
            case "$path" in *"$newline"*|*"$tab"*) exit 1;; esac
            if [ -L "$path" ]; then
                target=$(readlink -n "$path" && printf ".") || exit 1
                target=${target%.}
                case "$target" in ""|*"$newline"*|*"$tab"*) exit 1;; esac
                printf "L\t%s\t%s\n" "${path#./}" "$target"
            else
                printf "F\t%s\t-\n" "${path#./}"
            fi
        done
    ' sh {} + > "$work/paths" || fail 'filesystem inventory failed'
[ "$(wc -c < "$work/paths")" -le 2097152 ] || fail 'link inventory too large'
awk -F '\t' -v regular="$regular" -v soname="$soname" -v consumers="$consumers" '
    # Resolve archive-style image paths, including .. after a directory symlink.
    # No filesystem reads or host-path resolution occur inside this check.
    function resolve(path, pending, current, slash, part, hops, target) {
        pending=path; current=""; hops=0
        while (pending != "") {
            slash=index(pending,"/")
            if (slash) { part=substr(pending,1,slash-1); pending=substr(pending,slash+1) }
            else { part=pending; pending="" }
            if (part == "" || part == ".") continue
            if (part == "..") { sub(/\/?[^\/]+$/,"",current); continue }
            current=(current == "" ? part : current "/" part)
            if (current in links) {
                if (++hops > 64) { bad=1; return "" }
                target=links[current]
                sub(/\/?[^\/]+$/,"",current)
                if (substr(target,1,1) == "/") current=""
                pending=target (pending == "" ? "" : "/" pending)
            }
        }
        return current
    }
    NF != 3 || seen[$2]++ { bad=1; next }
    $1 == "L" { links[$2]=$3; next }
    $1 != "F" || $2 != regular { bad=1 }
    END {
        count=split(consumers, names, " ")
        for (i=1; i<=count; i++) removed[names[i]]=1
        removed[regular]=1
        for (name in links) {
            destination=resolve(name)
            if (name == "bin" || name == "sbin" || name == "lib" || name == soname) continue
            for (path in removed)
                if (destination == "" || destination == path || index(path,destination "/") == 1) bad=1
            if (name ~ /(^|\/)libacl(\.so|\.a$|-[^\/]*\.so)/) bad=1
        }
        if (!(regular in seen) || !(soname in links) || bad) exit 1
    }
' "$work/paths" || fail 'unexpected library copy or alias'

# Validation is complete before the first removal. Build roots must not mutate concurrently.
for path in $consumers "$soname" "$regular"; do
    rm -- "$path"
done
printf 'ACL runtime pruning complete (seven consumers and libacl; package metadata retained).\n'
