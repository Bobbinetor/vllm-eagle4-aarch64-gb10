#!/usr/bin/env bash
# Prepare and (only with --publish) create a GitHub Release.
#
# Dry run is the default: it runs every check, prints the exact commands, and
# changes nothing. Nothing is pushed, tagged remotely, or published unless you
# pass --publish.
#
# Usage:
#   ./scripts/release.sh                          # dry run for v0.1.0
#   ./scripts/release.sh --version v0.1.0 --wheel vllm-*.whl
#   ./scripts/release.sh --version v0.1.0 --publish            # draft release
#   ./scripts/release.sh --version v0.1.0 --publish --no-draft # public release
#
# Requirements: git, gh (authenticated), python3, the wheel, and a notes file
# at docs/releases/<version>.md.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

VERSION="v0.1.0"
WHEEL=""
NOTES=""
REPO=""
TITLE=""
PUBLISH=0
DRAFT=1
ALLOW_DIRTY=0

usage() {
  cat <<'EOF'
Usage: ./scripts/release.sh [options]

Dry run is the default: it runs every check, prints the exact commands, and
changes nothing. Nothing is pushed, tagged remotely, or published unless you
pass --publish.

Options:
  --version v0.1.0     Release tag (default: v0.1.0)
  --wheel PATH         Wheel to attach (default: the only vllm-*.whl in the root)
  --notes PATH         Release notes (default: docs/releases/<version>.md)
  --repo OWNER/NAME    GitHub repo (default: detected with gh)
  --title TEXT         Release title
  --publish            Actually create the release (default: dry run)
  --draft              Create a draft release (default when publishing)
  --no-draft           Publish immediately (use after a successful draft review)
  --allow-dirty        Skip the clean-working-tree check (dry run only)
  -h, --help           Show this help

Examples:
  ./scripts/release.sh
  ./scripts/release.sh --version v0.1.0 --publish
  ./scripts/release.sh --version v0.1.0 --publish --no-draft
EOF
  exit "${1:-0}"
}

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
step() { printf '\n== %s\n' "$*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="${2:?}"; shift 2 ;;
    --wheel) WHEEL="${2:?}"; shift 2 ;;
    --notes) NOTES="${2:?}"; shift 2 ;;
    --repo) REPO="${2:?}"; shift 2 ;;
    --title) TITLE="${2:?}"; shift 2 ;;
    --publish) PUBLISH=1; shift ;;
    --draft) DRAFT=1; shift ;;
    --no-draft) DRAFT=0; shift ;;
    --allow-dirty) ALLOW_DIRTY=1; shift ;;
    -h|--help) usage 0 ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
done

[[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.]+)?$ ]] \
  || die "version must look like v0.1.0 (got: $VERSION)"

WHEEL="${WHEEL:-$(ls -1 vllm-*.whl 2>/dev/null | head -1 || true)}"
[[ -n "$WHEEL" && -f "$WHEEL" ]] || die "wheel not found; pass --wheel PATH"
NOTES="${NOTES:-docs/releases/$VERSION.md}"
[[ -f "$NOTES" ]] || die "release notes not found: $NOTES"
[[ -s "$NOTES" ]] || die "release notes are empty: $NOTES"

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

step "Repository state"
git rev-parse --git-dir >/dev/null 2>&1 || die "not a git repository"
if [[ "$ALLOW_DIRTY" -eq 0 && -n "$(git status --porcelain)" ]]; then
  die "working tree is not clean; commit or stash first (or pass --allow-dirty for a dry run)"
fi
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[[ "$BRANCH" == "main" ]] || printf 'warning: on branch %s, not main\n' "$BRANCH"
HEAD_SHA="$(git rev-parse HEAD)"
printf '  commit: %s (%s)\n' "${HEAD_SHA:0:12}" "$BRANCH"

step "Wheel"
SIZE="$(wc -c < "$WHEEL" | tr -d ' ')"
HASH="$(sha256_file "$WHEEL")"
printf '  file:   %s\n' "$WHEEL"
printf '  size:   %s bytes\n' "$SIZE"
printf '  sha256: %s\n' "$HASH"
[[ "$SIZE" -eq 494300662 ]] || printf 'warning: expected 494300662 bytes\n'
grep -qF "$HASH" SHA256SUMS || die "wheel hash is not listed in SHA256SUMS"
grep -qF "$HASH  $WHEEL" SHA256SUMS || printf 'warning: SHA256SUMS line format differs from "<hash>  <file>"\n'
python3 scripts/audit_hooks.py "$WHEEL" >/dev/null || die "static hook audit failed"

step "Repository checks"
python3 scripts/check_repo.py

step "GitHub"
command -v gh >/dev/null 2>&1 || die "gh CLI not installed"
gh auth status >/dev/null 2>&1 || die "gh is not authenticated (run: gh auth login)"
if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
fi
[[ -n "$REPO" ]] || die "cannot resolve the GitHub repo; pass --repo owner/name"
printf '  repo: %s\n' "$REPO"
if git remote get-url origin >/dev/null 2>&1; then
  printf '  remote: %s\n' "$(git remote get-url origin)"
else
  printf '  remote: (none yet)\n'
fi
TAG_EXISTS=0
if git ls-remote --exit-code --tags origin "$VERSION" >/dev/null 2>&1; then
  TAG_EXISTS=1
  printf '  tag:    %s already exists on the remote; will attach the release to it\n' "$VERSION"
  if gh release view "$VERSION" --repo "$REPO" >/dev/null 2>&1; then
    die "a release for $VERSION already exists on the remote ($REPO)"
  fi
fi

[[ -n "$TITLE" ]] || TITLE="$VERSION — vLLM 0.32.0rc1.dev283+eagle.3 for aarch64 / GB10"

step "Plan"
printf '  tag:    %s\n' "$VERSION"
printf '  target: %s\n' "$HEAD_SHA"
printf '  title:  %s\n' "$TITLE"
printf '  notes:  %s\n' "$NOTES"
printf '  assets: %s\n' "$WHEEL"
printf '          SHA256SUMS'
printf '\n  draft:  %s\n' "$([[ "$DRAFT" -eq 1 ]] && echo yes || echo no)"

release_args=(
  "$VERSION" "$WHEEL" SHA256SUMS
  --repo "$REPO"
  --title "$TITLE"
  --notes-file "$NOTES"
)
[[ "$TAG_EXISTS" -eq 0 ]] && release_args+=(--target "$HEAD_SHA")
[[ "$DRAFT" -eq 1 ]] && release_args+=(--draft)
[[ "$DRAFT" -eq 0 ]] && release_args+=(--latest)

python3 -c 'import shlex, sys; print("\n  " + shlex.join(sys.argv[1:]))' \
  gh release create "${release_args[@]}"

if [[ "$PUBLISH" -eq 0 ]]; then
  step "Dry run"
  echo "  No tag, no release, no upload. Re-run with --publish to create it."
  exit 0
fi

step "Publishing"
gh release create "${release_args[@]}"
git fetch --tags >/dev/null 2>&1 || true
printf '\nRelease created: https://github.com/%s/releases/tag/%s\n' "$REPO" "$VERSION"
if [[ "$DRAFT" -eq 1 ]]; then
  echo "It is a draft: review it on GitHub, then publish it from the Releases page."
fi
echo "After publishing, the release-verify workflow re-downloads and checks the asset."
