#!/usr/bin/env bash
# Release automation for the claude-mbproj plugin.
#
# Split in two on purpose. `prepare` does everything that can be undone — bump, lint,
# test, changelog, commit, tag — and stops. `publish` is the only step that pushes, and
# the only one whose effects leave this machine. Between the two the release sits on
# disk as an ordinary commit and tag, inspectable for as long as you want.

set -euo pipefail

readonly PLUGIN_NAME="claude-mbproj"
readonly MARKETPLACE_NAME="claude-mbproj"
readonly PLUGIN_MANIFEST=".claude-plugin/plugin.json"
readonly MARKETPLACE_MANIFEST=".claude-plugin/marketplace.json"
readonly SEMVER_RE='^[0-9]+\.[0-9]+\.[0-9]+$'

# Set once prepare has modified the working tree, so a failure past that point knows it
# has something to roll back to.
ROLLBACK_TO=""
ROLLBACK_TAG=""

die() {
    printf 'release: %s\n' "$*" >&2
    exit 1
}

step() {
    printf '\n== %s\n' "$*"
}

repo_root() {
    local root
    root="$(git rev-parse --show-toplevel)"
    printf '%s\n' "${root}"
}

plugins_dir() {
    printf '%s\n' "${CLAUDE_CONFIG_DIR:-${HOME}/.claude}/plugins"
}

tag_for() {
    printf '%s--v%s\n' "${PLUGIN_NAME}" "$1"
}

manifest_version() {
    local version
    version="$(jq -r '.version' "${PLUGIN_MANIFEST}")"
    printf '%s\n' "${version}"
}

marketplace_version() {
    local version
    version="$(jq -r --arg n "${PLUGIN_NAME}" \
        '.plugins[] | select(.name == $n) | .version' "${MARKETPLACE_MANIFEST}")"
    printf '%s\n' "${version}"
}

# Checked up front rather than discovered halfway through a bump. `make check-dev-env`
# covers the linting tools; these are the ones only releasing needs.
require_tools() {
    local tool
    for tool in git-cliff jq claude python3; do
        command -v "${tool}" >/dev/null 2>&1 ||
            die "${tool} not found — see SETUP_ENV.md"
    done
}

require_clean_tree() {
    local dirty
    dirty="$(git status --porcelain)"
    [[ -z "${dirty}" ]] || die "working tree is not clean — commit or stash first"
}

require_branch_main() {
    local branch
    branch="$(git rev-parse --abbrev-ref HEAD)"
    [[ "${branch}" == "main" ]] || die "expected branch main, on ${branch}"
}

# Being ahead of origin is the normal case — the commits being released are usually
# local. Being behind is not: the release would omit what is already on origin, and the
# push would fail or, worse, need a merge nobody reviewed.
require_not_behind() {
    local counts behind
    git fetch --quiet origin main
    counts="$(git rev-list --left-right --count origin/main...HEAD)"
    behind="${counts%%[[:space:]]*}"
    [[ "${behind}" == "0" ]] ||
        die "main is ${behind} commit(s) behind origin/main — reconcile before releasing"
}

rollback() {
    [[ -n "${ROLLBACK_TO}" ]] || return 0
    printf '\nrelease: failed — restoring the tree to %s\n' "${ROLLBACK_TO:0:7}" >&2
    if [[ -n "${ROLLBACK_TAG}" ]] && git rev-parse -q --verify "refs/tags/${ROLLBACK_TAG}" >/dev/null; then
        git tag -d "${ROLLBACK_TAG}" >/dev/null
    fi
    # Safe because prepare refuses to start on a dirty tree: this can only discard what
    # this script itself wrote.
    git reset --hard --quiet "${ROLLBACK_TO}"
}

# Pre-fills the release message with the subject and, as comments, the commits the
# version carries. Abandoning the editor leaves git with nothing to commit, which fails
# the run and triggers the rollback — so quitting really does cancel the release.
write_commit_template() {
    local file="$1" version="$2" previous="$3"
    {
        printf 'chore(release): %s\n\n' "${version}"
        printf '\n'
        printf '# Commits carried by this release'
        if [[ -n "${previous}" ]]; then
            printf ' since %s' "${previous}"
        fi
        printf ':\n'
        if [[ -n "${previous}" ]]; then
            git log --reverse --format='#   %s' "${previous}..HEAD"
        else
            git log --reverse --format='#   %s'
        fi
        printf '#\n'
        printf '# Lines starting with # are dropped. Save an empty message to cancel\n'
        printf '# the release; the tree is restored to where it was.\n'
    } >"${file}"
}

cmd_prepare() {
    local version="${1:-}"
    [[ -n "${version}" ]] || die "usage: make release VERSION=X.Y.Z"
    [[ "${version}" =~ ${SEMVER_RE} ]] || die "'${version}' is not a X.Y.Z version"

    local root
    root="$(repo_root)"
    cd "${root}"

    local tag current market
    tag="$(tag_for "${version}")"

    step "Checking preconditions"
    require_tools
    require_branch_main
    require_clean_tree
    require_not_behind

    current="$(manifest_version)"
    market="$(marketplace_version)"
    [[ "${current}" == "${market}" ]] ||
        die "manifests already disagree: plugin.json ${current}, marketplace.json ${market}"
    # `sort -V` puts the lower version first, so the new one only moves forward when the
    # current one sorts below it. Equality sorts as "already ordered" and is ruled out
    # separately. This is what stops a release from serving an older plugin than a
    # project already has.
    local lowest
    lowest="$(printf '%s\n%s\n' "${version}" "${current}" | sort -V | head -n1)"
    if [[ "${version}" == "${current}" || "${lowest}" != "${current}" ]]; then
        die "${version} does not move forward from ${current} — a release must not regress"
    fi

    if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
        die "tag ${tag} already exists locally"
    fi
    if git ls-remote --exit-code --tags origin "refs/tags/${tag}" >/dev/null 2>&1; then
        die "tag ${tag} already exists on origin — ${version} is published"
    fi
    printf '  %s -> %s, working tree clean, nothing missing from origin\n' "${current}" "${version}"

    local previous
    previous="$(git describe --tags --abbrev=0 --match "${PLUGIN_NAME}--v*" 2>/dev/null || true)"

    ROLLBACK_TO="$(git rev-parse HEAD)"
    trap rollback ERR

    step "Bumping both manifests"
    local tmp
    tmp="$(mktemp)"
    jq --arg v "${version}" '.version = $v' "${PLUGIN_MANIFEST}" >"${tmp}"
    mv "${tmp}" "${PLUGIN_MANIFEST}"
    tmp="$(mktemp)"
    jq --arg n "${PLUGIN_NAME}" --arg v "${version}" \
        '(.plugins[] | select(.name == $n) | .version) = $v' "${MARKETPLACE_MANIFEST}" >"${tmp}"
    mv "${tmp}" "${MARKETPLACE_MANIFEST}"
    claude plugin validate .

    # This repository is scaffolded by the skill it ships, so its own generated files
    # carry the plugin version and have to be rewritten by the new one.
    step "Re-applying the scaffold to this repository"
    CLAUDE_PLUGIN_ROOT="${PWD}" python3 skills/mbproj-scaffold/scripts/mbproj_apply.py . \
        --layer lint_format --layer guards --layer changelog \
        --project-name "${PLUGIN_NAME}" \
        --vendored-dir skills/mbproj-scaffold/templates >/dev/null

    # git-cliff is invoked directly rather than through `make changelog`: the Makefile
    # rules forbid recursive make, and this script runs from a make target. Linting is
    # covered twice over — the `release` target depends on `lint`, and the pre-commit
    # hook lints again below, on the bumped and regenerated tree.
    step "Regenerating the changelog as ${version}"
    git-cliff --tag "${tag}" -o CHANGELOG.md

    step "Committing"
    local template
    template="$(mktemp)"
    write_commit_template "${template}" "${version}" "${previous}"
    git add -A
    git commit --edit --file "${template}"
    rm -f "${template}"

    step "Tagging"
    ROLLBACK_TAG="${tag}"
    claude plugin tag .

    trap - ERR
    ROLLBACK_TO=""

    cat <<EOF

Ready to publish: ${tag}
Nothing has been pushed.

  inspect  git show HEAD
  cancel   make release-abort
  publish  make publish
EOF
}

# Brings every recorded installation of the plugin up to the published version. This is
# the step whose absence let two releases reach no project at all: pushing updates the
# repository, not the copies Claude Code actually reads.
refresh_installations() {
    local version="$1" registry key
    registry="$(plugins_dir)/installed_plugins.json"
    key="${PLUGIN_NAME}@${MARKETPLACE_NAME}"

    if [[ ! -f "${registry}" ]]; then
        printf '  no installation registry at %s — nothing to refresh\n' "${registry}"
        return 0
    fi

    local rows
    rows="$(jq -r --arg k "${key}" \
        '.plugins[$k] // [] | .[] | [.scope, (.projectPath // ""), .version] | @tsv' \
        "${registry}")"
    if [[ -z "${rows}" ]]; then
        printf '  the plugin is not installed anywhere — nothing to refresh\n'
        return 0
    fi

    local scope project installed target_dir
    while IFS=$'\t' read -r scope project installed; do
        [[ -n "${scope}" ]] || continue
        if [[ "${installed}" == "${version}" ]]; then
            printf '  %-8s %-45s already %s\n' "${scope}" "${project:-(user)}" "${version}"
            continue
        fi
        target_dir="${project:-${HOME}}"
        if [[ ! -d "${target_dir}" ]]; then
            printf '  %-8s %-45s SKIPPED (path is gone)\n' "${scope}" "${project}"
            continue
        fi
        printf '  %-8s %-45s %s -> %s\n' "${scope}" "${project:-(user)}" "${installed}" "${version}"
        (cd "${target_dir}" && claude plugin update "${key}" --scope "${scope}")
    done <<<"${rows}"
}

# Compares what the installed plugin would hand to a scaffolded project against what
# this repository holds. The version number alone proves nothing about file contents,
# and file contents are the whole point of a release.
verify_installed_templates() {
    local version="$1" cache
    cache="$(plugins_dir)/cache/${MARKETPLACE_NAME}/${PLUGIN_NAME}/${version}"

    if [[ ! -d "${cache}" ]]; then
        printf '  no cache at %s — nothing installed to verify\n' "${cache}"
        return 0
    fi
    if diff -r "${cache}/skills/mbproj-scaffold/templates" \
        "skills/mbproj-scaffold/templates" >/dev/null; then
        printf '  templates in the installed %s are identical to this repository\n' "${version}"
    else
        die "installed templates differ from this repository — the release did not land intact"
    fi
}

cmd_publish() {
    local root
    root="$(repo_root)"
    cd "${root}"

    step "Checking the prepared release"
    require_branch_main
    require_clean_tree

    local subject version tag
    subject="$(git log -1 --format=%s)"
    [[ "${subject}" =~ ^chore\(release\):\ ([0-9]+\.[0-9]+\.[0-9]+)$ ]] ||
        die "HEAD is not a release commit ('${subject}') — run make release first"
    version="${BASH_REMATCH[1]}"
    tag="$(tag_for "${version}")"

    local tagged head
    git rev-parse -q --verify "refs/tags/${tag}" >/dev/null ||
        die "no tag ${tag} — run make release first"
    tagged="$(git rev-parse "${tag}^{commit}")"
    head="$(git rev-parse HEAD)"
    [[ "${tagged}" == "${head}" ]] || die "tag ${tag} does not point at HEAD"

    local declared market
    declared="$(manifest_version)"
    market="$(marketplace_version)"
    [[ "${declared}" == "${version}" && "${market}" == "${version}" ]] ||
        die "manifests say ${declared}/${market}, the release commit says ${version}"

    if git ls-remote --exit-code --tags origin "refs/tags/${tag}" >/dev/null 2>&1; then
        die "${tag} is already on origin — ${version} is published"
    fi
    printf '  %s at %s, manifests agree\n' "${tag}" "${head:0:7}"

    step "Pushing branch and tag"
    git push origin main
    git push origin "refs/tags/${tag}"

    step "Refreshing the marketplace clone"
    claude plugin marketplace update "${MARKETPLACE_NAME}"
    local served clone
    clone="$(plugins_dir)/marketplaces/${MARKETPLACE_NAME}/${PLUGIN_MANIFEST}"
    served="$(jq -r '.version' "${clone}")"
    [[ "${served}" == "${version}" ]] ||
        die "the marketplace clone still serves ${served} after an update"
    printf '  the clone now serves %s\n' "${version}"

    step "Updating installed copies"
    refresh_installations "${version}"

    step "Verifying what a scaffolded project would receive"
    verify_installed_templates "${version}"

    cat <<EOF

Published ${version}.
Updated plugins apply to the next Claude Code session, not this one.
EOF
}

cmd_abort() {
    local root
    root="$(repo_root)"
    cd "${root}"
    require_branch_main

    local subject version tag
    subject="$(git log -1 --format=%s)"
    [[ "${subject}" =~ ^chore\(release\):\ ([0-9]+\.[0-9]+\.[0-9]+)$ ]] ||
        die "HEAD is not a release commit ('${subject}') — nothing to abort"
    version="${BASH_REMATCH[1]}"
    tag="$(tag_for "${version}")"

    if git ls-remote --exit-code --tags origin "refs/tags/${tag}" >/dev/null 2>&1; then
        die "${version} is already published — aborting would rewrite pushed history"
    fi

    git reset --hard --quiet HEAD~1
    if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
        git tag -d "${tag}" >/dev/null
    fi
    printf 'Aborted %s. The tree is back to where it was.\n' "${version}"
}

main() {
    local command="${1:-}"
    shift || true
    case "${command}" in
        prepare) cmd_prepare "${@}" ;;
        publish) cmd_publish "${@}" ;;
        abort) cmd_abort "${@}" ;;
        *) die "usage: ${0##*/} {prepare X.Y.Z|publish|abort}" ;;
    esac
}

main "${@}"
