#!/usr/bin/env bash
# 맥 준비 점검: 엔진을 받기 전에도 돈다. 이미 설치된 것과 빠진 것을 보여 준다.
# 읽기만 한다. 아무것도 설치하거나 바꾸지 않는다. 빠진 것의 설치 명령을 마지막에 모아 보여 준다.
#
# 쓰는 법:
#   bash scripts/check-mac.sh                 # 엔진 리포 안에서
#   bash check-mac.sh ~/code/product-forge-with-ai   # 엔진 리포 위치를 직접 줄 때
#
# 결과: 빠진 것이 없으면 종료 코드 0, 있으면 1.
set -u

S1_COMMIT="513ec5891c7fdea0ae01c9cec14505c3103e8e09"  # tests/s1_adapter.py와 같다
UV_MIN="0.13.6"

pass=0
fail=0
todo=()

ok() { echo "✅ $1"; pass=$((pass + 1)); }
no() { echo "❌ $1"; fail=$((fail + 1)); todo+=("$2"); }
note() { echo "ℹ️  $1"; }

# 버전 출력에서 첫 'N.N(.N…)'
version_of() { "$@" 2>/dev/null | grep -Eo '[0-9]+(\.[0-9]+)+' | head -n 1; }

# a >= b (점으로 나뉜 숫자 비교)
version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -t. -k1,1n -k2,2n -k3,3n | head -n 1)" = "$2" ]; }

check_system() {
  if [ "$(uname -s)" = "Darwin" ]; then ok "macOS"; else no "macOS가 아님($(uname -s)) — 플레이는 맥에서" "맥에서 다시 실행"; fi
  if [ "$(uname -m)" = "arm64" ]; then ok "Apple Silicon"; else note "Apple Silicon이 아님($(uname -m)). OrbStack 랩은 동작하지만 확인한 환경은 아니다"; fi
  if xcode-select -p >/dev/null 2>&1; then
    ok "Xcode Command Line Tools"
  else
    no "Xcode Command Line Tools 없음" "xcode-select --install"
    # CLT가 없는 맥의 /usr/bin/git은 실행만 해도 설치 창을 띄운다. 이 스크립트는 읽기만 하므로 부르지 않는다.
    [ "$(uname -s)" = "Darwin" ] && NO_CLT=1
  fi
}

check_tool() {  # check_tool <이름> <설치 명령> <버전 명령...>
  local name=$1 install=$2
  shift 2
  if ! command -v "$1" >/dev/null 2>&1; then
    no "$name 없음" "$install"
    return
  fi
  ok "$name $(version_of "$@")"
}

brew_on_path() {  # 애플 실리콘은 설치 직후 brew가 PATH에 없다. 있으면 이 점검 안에서만 PATH에 더한다
  command -v brew >/dev/null 2>&1 && return
  local b
  for b in ${BREW_PATHS:-/opt/homebrew/bin/brew /usr/local/bin/brew}; do
    if [ -x "$b" ]; then
      no "Homebrew는 있지만 PATH에 없음($b)" "echo 'eval \"\$($b shellenv)\"' >> ~/.zprofile && eval \"\$($b shellenv)\""
      eval "$("$b" shellenv)"
      return
    fi
  done
}

check_tools() {
  brew_on_path
  check_tool "Homebrew" '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"' brew --version
  if [ -n "${NO_CLT:-}" ] && [ "$(command -v git)" = "/usr/bin/git" ]; then
    note "git은 Xcode Command Line Tools를 설치한 뒤에 점검한다"
  else
    check_tool "git" "brew install git" git --version
  fi
  check_tool "gh" "brew install gh" gh --version
  if command -v gh >/dev/null 2>&1; then
    if gh auth status >/dev/null 2>&1; then ok "gh 로그인"; else no "gh 로그인 안 됨" "gh auth login"; fi
  fi
  if command -v uv >/dev/null 2>&1; then
    local found
    found=$(version_of uv --version)
    if version_ge "$found" "$UV_MIN"; then ok "uv $found"; else no "uv $found (필요: $UV_MIN 이상)" "uv self update"; fi
    if uv python find 3.14 >/dev/null 2>&1; then ok "Python 3.14(uv)"; else no "Python 3.14 없음" "uv python install 3.14.10  (uv sync가 알아서 받기도 한다)"; fi
  else
    no "uv 없음" "brew install uv"
  fi
  check_tool "OrbStack(orb)" "brew install --cask orbstack" orb version
}

check_engine_repo() {  # check_engine_repo <위치>
  local repo=$1
  if [ -n "${NO_CLT:-}" ] && [ "$(command -v git)" = "/usr/bin/git" ]; then
    note "엔진 리포는 Xcode Command Line Tools를 설치한 뒤에 점검한다"
    return
  fi
  if [ ! -d "$repo/.git" ] || [ ! -f "$repo/pyproject.toml" ]; then
    no "엔진 리포 없음($repo)" "git clone https://github.com/sikomar00/product-forge-with-ai.git"
    return
  fi
  ok "엔진 리포($repo)"
  local branch
  branch=$(git -C "$repo" symbolic-ref --short -q HEAD)
  case "$branch" in
    main | engine/*) ok "브랜치 $branch" ;;
    *) no "브랜치가 $branch" "git -C $repo switch main" ;;
  esac
  if [ -d "$repo/.venv" ]; then ok "엔진 의존성(.venv)"; else no "엔진 의존성 설치 전" "cd $repo && uv sync"; fi
}

check_s1() {
  local s1=${QUEST_S1_REPO:-}
  if [ -n "${NO_CLT:-}" ] && [ "$(command -v git)" = "/usr/bin/git" ]; then
    note "S1 리포는 Xcode Command Line Tools를 설치한 뒤에 점검한다"
    return
  fi
  if [ -z "$s1" ]; then
    no "QUEST_S1_REPO 없음(S1 회귀 시험용)" "git clone https://github.com/sikomar00/sailingstone-quest.git ~/s1-sailingstone-quest && export QUEST_S1_REPO=~/s1-sailingstone-quest  (~/.zshrc에도)"
    return
  fi
  if [ ! -d "$s1/.git" ]; then
    no "QUEST_S1_REPO가 가리키는 곳에 리포 없음($s1)" "git clone https://github.com/sikomar00/sailingstone-quest.git $s1"
    return
  fi
  if [ "$(git -C "$s1" rev-parse HEAD)" = "$S1_COMMIT" ]; then ok "S1 리포(고정 커밋)"; else no "S1 리포 커밋이 다름" "git -C $s1 checkout $S1_COMMIT"; fi
}

check_game_files() {
  local cfg=${QUEST_CONFIG:-$HOME/.config/quest/config.toml}
  local content="$HOME/.local/share/quest/content"  # 엔진의 기본 설정과 같은 곳
  if [ -f "$cfg" ]; then
    ok "게임 설정 파일($cfg)"
    local found  # 엔진은 설정의 [content] path에서만 콘텐츠를 읽는다
    found=$(awk -F'"' '/^\[/ { s = ($1 == "[content]") } s && /^path[ \t]*=/ { print $2; exit }' "$cfg")
    if [ -n "$found" ]; then content=${found/#\~/$HOME}; fi
  else
    note "게임 설정 파일은 아직 없다. 처음 quest를 실행하면 만든다"
  fi
  if [ -d "$content/.git" ]; then ok "콘텐츠($content)"; else note "콘텐츠는 아직 없다($content). 콘텐츠 리포를 만든 뒤 quest update"; fi
}

script_dir=$(cd "$(dirname "$0")" && pwd)
repo=${1:-$(cd "$script_dir/.." && pwd)}

echo "맥 준비 점검(읽기만 한다)"
echo
check_system
check_tools
check_engine_repo "$repo"
check_s1
check_game_files
echo
echo "점검 $((pass + fail))개 중 ${pass}개 준비됨"
if [ "$fail" -gt 0 ]; then
  echo
  echo "필요한 것(위에서부터 차례로):"
  for step in "${todo[@]}"; do echo "  $step"; done
  exit 1
fi
echo "모두 준비됐습니다. 엔진 리포에서: uv run quest doctor"
