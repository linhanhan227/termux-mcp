#!/usr/bin/env bash
set -euo pipefail

# GitHub 仓库提交脚本：自动 add、commit、pull --rebase、push。

REMOTE_NAME="${GIT_REMOTE_NAME:-origin}"
REMOTE_URL=""
BRANCH=""
COMMIT_MESSAGE=""
PULL_BEFORE_PUSH=true
ALLOW_EMPTY=false
DRY_RUN=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    cat <<'USAGE'
用法:
  ./1.sh [-m 提交信息] [-r GitHub仓库URL] [-b 分支名] [选项]

常用示例:
  ./1.sh -m "docs: update readme"
  ./1.sh -r git@github.com:用户名/仓库名.git -m "init: first commit"
  ./1.sh -b main -m "chore: sync"

选项:
  -m, --message       提交信息；不传会交互输入
  -r, --remote        GitHub 仓库地址；未配置 origin 时会交互输入
  -b, --branch        推送分支；默认使用当前分支，无法识别时使用 main
      --no-pull       推送前不执行 git pull --rebase
      --allow-empty   没有文件变化时也创建空提交
      --dry-run       只打印将执行的命令，不真正执行
  -h, --help          显示帮助

环境变量:
  GIT_REMOTE_NAME     远程仓库名，默认 origin
USAGE
}

info() {
    printf '\n%b=== %s ===%b\n' "$BLUE" "$1" "$NC"
}

success() {
    printf '%b%s%b\n' "$GREEN" "$1" "$NC"
}

warning() {
    printf '%b%s%b\n' "$YELLOW" "$1" "$NC"
}

die() {
    printf '%b错误：%s%b\n' "$RED" "$1" "$NC" >&2
    exit 1
}

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    if [ "$DRY_RUN" = false ]; then
        "$@"
    fi
}

ask() {
    local prompt="$1"
    local value=""
    read -r -p "$prompt" value
    printf '%s' "$value"
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            -m|--message)
                [ $# -ge 2 ] || die "$1 需要提交信息"
                COMMIT_MESSAGE="$2"
                shift 2
                ;;
            -r|--remote)
                [ $# -ge 2 ] || die "$1 需要 GitHub 仓库地址"
                REMOTE_URL="$2"
                shift 2
                ;;
            -b|--branch)
                [ $# -ge 2 ] || die "$1 需要分支名"
                BRANCH="$2"
                shift 2
                ;;
            --no-pull)
                PULL_BEFORE_PUSH=false
                shift
                ;;
            --allow-empty)
                ALLOW_EMPTY=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                die "未知参数：$1。使用 ./1.sh --help 查看帮助"
                ;;
        esac
    done
}

check_git() {
    command -v git >/dev/null 2>&1 || die "未检测到 git，请先安装 git"
}

ensure_repo() {
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        return
    fi

    warning "当前目录不是 Git 仓库，将执行 git init"
    run git init
}

validate_remote_url() {
    local url="$1"
    if ! printf '%s' "$url" | grep -Eq '^(https://github\.com/|git@github\.com:)'; then
        die "远程地址必须是 GitHub 地址，例如 git@github.com:user/repo.git 或 https://github.com/user/repo.git"
    fi
}

ensure_remote() {
    local current_url=""

    if [ -n "$REMOTE_URL" ]; then
        validate_remote_url "$REMOTE_URL"
        if git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
            current_url=$(git remote get-url "$REMOTE_NAME")
            if [ "$current_url" != "$REMOTE_URL" ]; then
                warning "$REMOTE_NAME 当前地址为：$current_url"
                run git remote set-url "$REMOTE_NAME" "$REMOTE_URL"
            fi
        else
            run git remote add "$REMOTE_NAME" "$REMOTE_URL"
        fi
        return
    fi

    if git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
        current_url=$(git remote get-url "$REMOTE_NAME")
        validate_remote_url "$current_url"
        printf '使用远程仓库：%s -> %s\n' "$REMOTE_NAME" "$current_url"
        return
    fi

    REMOTE_URL=$(ask "请输入 GitHub 仓库地址：")
    [ -n "$REMOTE_URL" ] || die "GitHub 仓库地址不能为空"
    validate_remote_url "$REMOTE_URL"
    run git remote add "$REMOTE_NAME" "$REMOTE_URL"
}

ensure_branch() {
    local current_branch=""

    if [ -n "$BRANCH" ]; then
        if git rev-parse --verify HEAD >/dev/null 2>&1; then
            current_branch=$(git branch --show-current 2>/dev/null || true)
            if [ "$current_branch" = "$BRANCH" ]; then
                return
            fi
            if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
                run git switch "$BRANCH"
            else
                run git switch -c "$BRANCH"
            fi
        else
            run git symbolic-ref HEAD "refs/heads/$BRANCH"
        fi
        return
    fi

    current_branch=$(git branch --show-current 2>/dev/null || true)
    if [ -n "$current_branch" ]; then
        BRANCH="$current_branch"
        return
    fi

    BRANCH="main"
    warning "无法识别当前分支，默认使用 main"
    if git rev-parse --verify HEAD >/dev/null 2>&1; then
        run git switch -c "$BRANCH"
    else
        run git symbolic-ref HEAD "refs/heads/$BRANCH"
    fi
}

ensure_identity_hint() {
    if ! git config user.name >/dev/null || ! git config user.email >/dev/null; then
        warning "当前仓库未完整配置 user.name/user.email；如提交失败，请先配置："
        printf '  git config user.name "你的名字"\n'
        printf '  git config user.email "你的邮箱"\n'
    fi
}

stage_changes() {
    info "暂存文件"
    run git add -A
    git status --short
}

commit_changes() {
    info "提交更改"

    if git diff --cached --quiet; then
        if [ "$ALLOW_EMPTY" = true ]; then
            warning "没有检测到文件变化，将创建空提交"
        else
            warning "没有检测到需要提交的文件变化"
            return
        fi
    fi

    if [ -z "$COMMIT_MESSAGE" ]; then
        COMMIT_MESSAGE=$(ask "请输入提交信息：")
    fi
    [ -n "$COMMIT_MESSAGE" ] || die "提交信息不能为空"

    if [ "$ALLOW_EMPTY" = true ]; then
        run git commit --allow-empty -m "$COMMIT_MESSAGE"
    else
        run git commit -m "$COMMIT_MESSAGE"
    fi
}

pull_remote() {
    if [ "$PULL_BEFORE_PUSH" = false ]; then
        return
    fi

    info "同步远程分支"
    if git ls-remote --exit-code --heads "$REMOTE_NAME" "$BRANCH" >/dev/null 2>&1; then
        run git pull --rebase --autostash "$REMOTE_NAME" "$BRANCH"
    else
        warning "远程分支 $BRANCH 不存在，跳过 pull"
    fi
}

push_remote() {
    info "推送到 GitHub"
    run git push -u "$REMOTE_NAME" "$BRANCH"
    success "已提交并推送到 GitHub：$REMOTE_NAME/$BRANCH"
}

main() {
    parse_args "$@"
    check_git
    ensure_repo
    ensure_remote
    ensure_branch
    ensure_identity_hint
    stage_changes
    commit_changes
    pull_remote
    push_remote
}

main "$@"
