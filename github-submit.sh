#!/bin/sh

set -eu

SCRIPT_NAME=${0##*/}
REMOTE_NAME=origin
REMOTE_URL=
BRANCH=
COMMIT_MSG=
DRY_RUN=0
NO_VERIFY=0
ALLOW_EMPTY=0
FORCE_WITH_LEASE=0
PUSH_TAGS=0
TAG_NAME=

usage() {
  cat <<EOF
Usage:
  ./$SCRIPT_NAME -m "commit message" [options]

Options:
  -m, --message MSG        Commit message. If omitted, a timestamp message is used.
  -b, --branch NAME        Branch to push. Defaults to current branch, or main.
  -r, --remote NAME        Git remote name. Defaults to origin.
  -u, --remote-url URL     Add or update the remote URL before pushing.
      --tag NAME           Create or update an annotated tag after commit.
      --push-tags          Push all local tags.
      --allow-empty        Allow an empty commit when there are no file changes.
      --no-verify          Pass --no-verify to git commit.
      --force-with-lease   Push with --force-with-lease.
      --dry-run            Print commands instead of running them.
  -h, --help               Show this help.

Environment:
  GITHUB_REPO_URL          Used as remote URL if -u/--remote-url is not given.
  GIT_COMMIT_MESSAGE       Used as commit message if -m/--message is not given.

Examples:
  ./$SCRIPT_NAME -m "Initial commit" -u git@github.com:USER/REPO.git
  ./$SCRIPT_NAME -m "Update docs"
  GITHUB_REPO_URL=https://github.com/USER/REPO.git ./$SCRIPT_NAME -m "Publish"
EOF
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '+'
    for arg in "$@"; do
      case $arg in
        *[!A-Za-z0-9_./:=@%+-]*|'')
          printf " '%s'" "$(printf "%s" "$arg" | sed "s/'/'\\\\''/g")"
          ;;
        *)
          printf ' %s' "$arg"
          ;;
      esac
    done
    printf '\n'
  else
    "$@"
  fi
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -m|--message)
        [ "$#" -ge 2 ] || die "$1 requires a value"
        COMMIT_MSG=$2
        shift 2
        ;;
      --message=*)
        COMMIT_MSG=${1#*=}
        shift
        ;;
      -b|--branch)
        [ "$#" -ge 2 ] || die "$1 requires a value"
        BRANCH=$2
        shift 2
        ;;
      --branch=*)
        BRANCH=${1#*=}
        shift
        ;;
      -r|--remote)
        [ "$#" -ge 2 ] || die "$1 requires a value"
        REMOTE_NAME=$2
        shift 2
        ;;
      --remote=*)
        REMOTE_NAME=${1#*=}
        shift
        ;;
      -u|--remote-url)
        [ "$#" -ge 2 ] || die "$1 requires a value"
        REMOTE_URL=$2
        shift 2
        ;;
      --remote-url=*)
        REMOTE_URL=${1#*=}
        shift
        ;;
      --tag)
        [ "$#" -ge 2 ] || die "$1 requires a value"
        TAG_NAME=$2
        shift 2
        ;;
      --tag=*)
        TAG_NAME=${1#*=}
        shift
        ;;
      --push-tags)
        PUSH_TAGS=1
        shift
        ;;
      --allow-empty)
        ALLOW_EMPTY=1
        shift
        ;;
      --no-verify)
        NO_VERIFY=1
        shift
        ;;
      --force-with-lease)
        FORCE_WITH_LEASE=1
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      --)
        shift
        break
        ;;
      -*)
        die "unknown option: $1"
        ;;
      *)
        die "unexpected argument: $1"
        ;;
    esac
  done
}

ensure_git_repo() {
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return
  fi

  log "No git repository found. Initializing one in the current directory."
  run git init
}

ensure_identity() {
  name=$(git config user.name || true)
  email=$(git config user.email || true)

  [ -n "$name" ] || die "git user.name is not set. Run: git config --global user.name \"Your Name\""
  [ -n "$email" ] || die "git user.email is not set. Run: git config --global user.email \"you@example.com\""
}

resolve_branch() {
  if [ -n "$BRANCH" ]; then
    return
  fi

  current=$(git branch --show-current 2>/dev/null || true)
  if [ -n "$current" ]; then
    BRANCH=$current
  else
    BRANCH=main
  fi
}

ensure_branch() {
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    current=$(git branch --show-current 2>/dev/null || true)
    if [ "$current" != "$BRANCH" ]; then
      if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
        run git checkout "$BRANCH"
      else
        run git checkout -b "$BRANCH"
      fi
    fi
  else
    current=$(git branch --show-current 2>/dev/null || true)
    if [ "$current" != "$BRANCH" ]; then
      run git checkout -B "$BRANCH"
    fi
  fi
}

ensure_remote() {
  if [ -z "$REMOTE_URL" ] && [ -n "${GITHUB_REPO_URL:-}" ]; then
    REMOTE_URL=$GITHUB_REPO_URL
  fi

  if git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
    if [ -n "$REMOTE_URL" ]; then
      run git remote set-url "$REMOTE_NAME" "$REMOTE_URL"
    fi
    return
  fi

  [ -n "$REMOTE_URL" ] || die "remote '$REMOTE_NAME' does not exist. Provide -u URL or set GITHUB_REPO_URL."
  run git remote add "$REMOTE_NAME" "$REMOTE_URL"
}

default_commit_message() {
  if [ -n "$COMMIT_MSG" ]; then
    return
  fi

  if [ -n "${GIT_COMMIT_MESSAGE:-}" ]; then
    COMMIT_MSG=$GIT_COMMIT_MESSAGE
  else
    COMMIT_MSG="Update repository $(date '+%Y-%m-%d %H:%M:%S')"
  fi
}

stage_changes() {
  run git add -A
}

check_sensitive_files() {
  if [ "$DRY_RUN" -eq 1 ]; then
    paths=$(
      {
        git diff --name-only
        git diff --cached --name-only
        git ls-files --others --exclude-standard
      } | sort -u
    )
  else
    paths=$(git diff --cached --name-only)
  fi

  [ -n "$paths" ] || return 0

  blocked=
  while IFS= read -r file; do
    case "$file" in
      .env|*/.env|.env.*|*/.env.*|id_rsa|*/id_rsa|id_ed25519|*/id_ed25519|*.pem|*.key)
        blocked=${blocked}${file}'
'
        ;;
    esac
  done <<EOF
$paths
EOF

  if [ -n "$blocked" ]; then
    printf 'Refusing to commit possible secret files:\n%s\n' "$blocked" >&2
    die "remove these files from staging or update .gitignore before committing"
  fi
}

has_changes_to_commit() {
  if [ "$DRY_RUN" -eq 1 ]; then
    [ -n "$(git status --porcelain)" ]
  else
    ! git diff --cached --quiet
  fi
}

commit_changes() {
  commit_args="commit"

  if [ "$NO_VERIFY" -eq 1 ]; then
    commit_args="$commit_args --no-verify"
  fi

  if [ "$ALLOW_EMPTY" -eq 1 ]; then
    commit_args="$commit_args --allow-empty"
  fi

  # shellcheck disable=SC2086
  run git $commit_args -m "$COMMIT_MSG"
}

create_tag() {
  [ -n "$TAG_NAME" ] || return 0
  run git tag -f -a "$TAG_NAME" -m "$TAG_NAME"
}

push_changes() {
  push_args="push -u"

  if [ "$FORCE_WITH_LEASE" -eq 1 ]; then
    push_args="$push_args --force-with-lease"
  fi

  # shellcheck disable=SC2086
  run git $push_args "$REMOTE_NAME" "$BRANCH"

  if [ -n "$TAG_NAME" ]; then
    run git push "$REMOTE_NAME" "$TAG_NAME" --force
  elif [ "$PUSH_TAGS" -eq 1 ]; then
    run git push "$REMOTE_NAME" --tags
  fi
}

main() {
  parse_args "$@"

  have_cmd git || die "git is not installed"

  ensure_git_repo
  ensure_identity
  resolve_branch
  default_commit_message
  ensure_branch
  ensure_remote
  stage_changes
  check_sensitive_files

  if has_changes_to_commit || [ "$ALLOW_EMPTY" -eq 1 ]; then
    commit_changes
    create_tag
  else
    log "No changes to commit."
  fi

  push_changes
  log "Done. Pushed '$BRANCH' to '$REMOTE_NAME'."
}

main "$@"
