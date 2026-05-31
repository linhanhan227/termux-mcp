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
用法：
  ./$SCRIPT_NAME -m "提交说明" [选项]

选项：
  -m, --message MSG        提交说明。未填写时使用带时间的默认说明。
  -b, --branch NAME        要推送的分支。默认使用当前分支，没有当前分支时使用 main。
  -r, --remote NAME        Git 远程名称。默认是 origin。
  -u, --remote-url URL     推送前添加或更新远程仓库地址。
      --tag NAME           提交后创建或更新一个附注标签。
      --push-tags          推送所有本地标签。
      --allow-empty        没有文件变更时也允许创建空提交。
      --no-verify          提交时跳过 Git hooks 检查。
      --force-with-lease   使用 --force-with-lease 推送。
      --dry-run            只打印将要执行的命令，不实际执行。
  -h, --help               显示帮助。

环境变量：
  GITHUB_REPO_URL          未传入 -u/--remote-url 时用作远程仓库地址。
  GIT_COMMIT_MESSAGE       未传入 -m/--message 时用作提交说明。

示例：
  ./$SCRIPT_NAME -m "初始化提交" -u git@github.com:USER/REPO.git
  ./$SCRIPT_NAME -m "更新文档"
  GITHUB_REPO_URL=https://github.com/USER/REPO.git ./$SCRIPT_NAME -m "发布更新"
EOF
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf '错误：%s\n' "$*" >&2
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
        [ "$#" -ge 2 ] || die "$1 需要一个值"
        COMMIT_MSG=$2
        shift 2
        ;;
      --message=*)
        COMMIT_MSG=${1#*=}
        shift
        ;;
      -b|--branch)
        [ "$#" -ge 2 ] || die "$1 需要一个值"
        BRANCH=$2
        shift 2
        ;;
      --branch=*)
        BRANCH=${1#*=}
        shift
        ;;
      -r|--remote)
        [ "$#" -ge 2 ] || die "$1 需要一个值"
        REMOTE_NAME=$2
        shift 2
        ;;
      --remote=*)
        REMOTE_NAME=${1#*=}
        shift
        ;;
      -u|--remote-url)
        [ "$#" -ge 2 ] || die "$1 需要一个值"
        REMOTE_URL=$2
        shift 2
        ;;
      --remote-url=*)
        REMOTE_URL=${1#*=}
        shift
        ;;
      --tag)
        [ "$#" -ge 2 ] || die "$1 需要一个值"
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
        die "未知选项：$1"
        ;;
      *)
        die "不支持的位置参数：$1"
        ;;
    esac
  done
}

ensure_git_repo() {
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return
  fi

  log "未发现 Git 仓库，正在当前目录初始化。"
  run git init
}

ensure_identity() {
  name=$(git config user.name || true)
  email=$(git config user.email || true)

  [ -n "$name" ] || die "未设置 git user.name。请执行：git config --global user.name \"你的名字\""
  [ -n "$email" ] || die "未设置 git user.email。请执行：git config --global user.email \"you@example.com\""
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

  [ -n "$REMOTE_URL" ] || die "远程 '$REMOTE_NAME' 不存在。请传入 -u URL，或设置 GITHUB_REPO_URL。"
  run git remote add "$REMOTE_NAME" "$REMOTE_URL"
}

default_commit_message() {
  if [ -n "$COMMIT_MSG" ]; then
    return
  fi

  if [ -n "${GIT_COMMIT_MESSAGE:-}" ]; then
    COMMIT_MSG=$GIT_COMMIT_MESSAGE
  else
    COMMIT_MSG="更新仓库 $(date '+%Y-%m-%d %H:%M:%S')"
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
    printf '拒绝提交可能包含敏感信息的文件：\n%s\n' "$blocked" >&2
    die "请先从暂存区移除这些文件，或在提交前更新 .gitignore"
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

  have_cmd git || die "未安装 git"

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
    log "没有需要提交的变更。"
  fi

  push_changes
  log "完成。已将分支 '$BRANCH' 推送到远程 '$REMOTE_NAME'。"
}

main "$@"
