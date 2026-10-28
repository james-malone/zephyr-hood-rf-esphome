#!/bin/bash
# zephyr-rf-capture.sh
# Find and capture the Zephyr range hood remote's RF signal on macOS using an RTL-SDR + rtl_433.
#
# Usage:
#   ./zephyr-rf-capture.sh scan              # step 1: find which band the remote transmits on
#   ./zephyr-rf-capture.sh buttons 433.92M   # step 2: capture each button twice at that frequency
#
# Optional env overrides:
#   FREQS="315M 433.92M"     bands to scan (default covers common remote bands)
#   BUTTONS="power light"    button names to capture in step 2
#   SCAN_SECS=10             seconds per quiet/press window in scan mode
#   BTN_SECS=6               seconds per button capture window
#   GAIN=40                  fixed tuner gain in dB (default: auto)
#   DEVICE=0                 RTL-SDR device index
#   OUT_ROOT=~/zephyr-rf     where results are written
#
# Requires bash 3.2+ (stock macOS bash is fine). RTL-SDR is receive-only; replay is done later
# from an ESP32+CC1101 or Broadlink using the timings this script extracts.

set -euo pipefail

FREQS="${FREQS:-303.875M 315M 390M 418M 433.92M 915M}"
BUTTONS="${BUTTONS:-power light speed_up speed_down delay_off}"
SCAN_SECS="${SCAN_SECS:-10}"
BTN_SECS="${BTN_SECS:-6}"
GAIN="${GAIN:-}"
DEVICE="${DEVICE:-0}"
OUT_ROOT="${OUT_ROOT:-$HOME/zephyr-rf}"
RUN_DIR="$OUT_ROOT/$(date +%Y%m%d-%H%M%S)"

die() { echo "ERROR: $*" >&2; exit 1; }

preflight() {
  [ "$(uname -s)" = "Darwin" ] || echo "Note: written for macOS; continuing anyway."
  if ! command -v rtl_433 >/dev/null 2>&1 || ! command -v rtl_test >/dev/null 2>&1; then
    command -v brew >/dev/null 2>&1 || die "Homebrew not found. Install it from https://brew.sh and re-run."
    echo "Installing rtl_433 and librtlsdr via Homebrew..."
    brew install rtl_433 librtlsdr
  fi
  echo "Checking for an RTL-SDR dongle..."
  local probe
  probe="$(rtl_test -d "$DEVICE" -t 2>&1 || true)"
  case "$probe" in
    *"No supported devices"*) die "No RTL-SDR found. Plug one in (not the one feeding ADS-B) and re-run." ;;
  esac
  mkdir -p "$RUN_DIR"
  echo "Results: $RUN_DIR"
}

# run_rtl <freq> <seconds> <outdir> <label>
# Runs rtl_433 in pulse-analyzer mode, saves undecoded signals as .cu8, logs everything.
run_rtl() {
  local freq="$1" secs="$2" dir="$3" label="$4"
  local gain_args=()
  [ -n "$GAIN" ] && gain_args=(-g "$GAIN")
  mkdir -p "$dir"
  (
    cd "$dir"
    rtl_433 -d "$DEVICE" -f "$freq" -s 250k ${gain_args[@]+"${gain_args[@]}"} \
      -A -S unknown -M time:iso -M level \
      -F "json:${label}.json" -T "$secs" >"${label}.log" 2>&1 || true
  )
}

count_packages() { grep -cE 'Detected (OOK|FSK) package' "$1" 2>/dev/null || true; }

# Most frequent demodulated bit rows, e.g. "{25} a5 d5 b8 00"
top_codes() {
  grep -Eo '^\[[0-9]+\] \{[0-9]+\} [0-9a-f ]+' "$1" 2>/dev/null \
    | sed -E 's/^\[[0-9]+\] //; s/ +$//' | sort | uniq -c | sort -rn | head -n "${2:-3}" || true
}

top_flex() {
  grep -Eo "Use a flex decoder with -X '[^']+'" "$1" 2>/dev/null \
    | sed -E "s/^Use a flex decoder with -X //" | sort | uniq -c | sort -rn | head -n 1 || true
}

countdown_prompt() {
  local msg="$1"
  echo
  read -r -p "$msg  Press Enter, then act when recording starts..." _
  echo "Recording..."
}

scan() {
  local summary="$RUN_DIR/scan-summary.txt"
  printf "%-10s %8s %8s %8s\n" "FREQ" "QUIET" "PRESS" "DELTA" | tee "$summary"
  for f in $FREQS; do
    local dir="$RUN_DIR/scan/$f"
    countdown_prompt "[$f] QUIET baseline (${SCAN_SECS}s): do NOT touch the remote."
    run_rtl "$f" "$SCAN_SECS" "$dir" quiet
    countdown_prompt "[$f] PRESS window (${SCAN_SECS}s): tap the LIGHT button ~5 times, 1 s apart."
    run_rtl "$f" "$SCAN_SECS" "$dir" press
    local q p
    q="$(count_packages "$dir/quiet.log")"; q="${q:-0}"
    p="$(count_packages "$dir/press.log")"; p="${p:-0}"
    printf "%-10s %8s %8s %8s\n" "$f" "$q" "$p" "$((p - q))" | tee -a "$summary"
  done
  echo
  echo "The band with the largest positive DELTA is the remote. Next:"
  echo "  $0 buttons <that-freq>"
  echo "Summary saved to $summary"
}

buttons() {
  local freq="${1:-}"
  [ -n "$freq" ] || die "Give the frequency found in scan mode, e.g. $0 buttons 433.92M"
  local summary="$RUN_DIR/buttons-summary.txt"
  echo "Button capture at $freq ($(date))" > "$summary"
  for b in $BUTTONS; do
    for attempt in 1 2; do
      countdown_prompt "[$b] attempt $attempt (${BTN_SECS}s): press $b ONCE."
      run_rtl "$freq" "$BTN_SECS" "$RUN_DIR/buttons/$b" "try$attempt"
    done
    local d="$RUN_DIR/buttons/$b" c1 c2 verdict
    c1="$(top_codes "$d/try1.log" 1 | awk '{$1=""; sub(/^ /,""); print}')"
    c2="$(top_codes "$d/try2.log" 1 | awk '{$1=""; sub(/^ /,""); print}')"
    if [ -z "$c1" ] || [ -z "$c2" ]; then
      verdict="NO DECODE (check .cu8 files in URH, or adjust GAIN)"
    elif [ "$c1" = "$c2" ]; then
      verdict="FIXED CODE (replayable)"
    else
      verdict="DIFFERENT (rolling code or noisy capture; retry once)"
    fi
    {
      echo
      echo "== $b =="
      echo "packages: try1=$(count_packages "$d/try1.log") try2=$(count_packages "$d/try2.log")"
      echo "top code try1: ${c1:-none}"
      echo "top code try2: ${c2:-none}"
      echo "verdict: $verdict"
      echo "flex timing: $(top_flex "$d/try1.log" | sed -E 's/^ *[0-9]+ //')"
    } | tee -a "$summary"
  done
  echo
  echo "Summary saved to $summary"
  echo "Raw .cu8 captures are under $RUN_DIR/buttons/<button>/ for Universal Radio Hacker."
}

main() {
  local mode="${1:-}"
  case "$mode" in
    scan)    preflight; scan ;;
    buttons) preflight; buttons "${2:-}" ;;
    *) echo "Usage: $0 scan | $0 buttons <freq, e.g. 433.92M>"; exit 1 ;;
  esac
}

main "$@"
