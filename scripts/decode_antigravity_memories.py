#!/usr/bin/env python3
"""
decode_antigravity_memories.py
-------------------------------
Decodes Antigravity's implicit memory files (~/.gemini/antigravity/implicit/*.pb)
without needing the AmpAI server running.

Usage:
    python3 decode_antigravity_memories.py
    python3 decode_antigravity_memories.py --dir /custom/path
    python3 decode_antigravity_memories.py --json          # output JSON
"""

import os
import sys
import json
import glob
import struct
import argparse


# ── Protocol Buffer decoder (schemaless) ──────────────────────────────────────

def read_varint(data: bytes, pos: int):
    result, shift = 0, 0
    while pos < len(data):
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def parse_pb(data: bytes, depth: int = 0) -> list:
    """Recursively decode a Protocol Buffer blob without a schema."""
    results = []
    pos = 0
    max_depth = 6

    while pos < len(data):
        try:
            tag_wire, pos = read_varint(data, pos)
            field_num = tag_wire >> 3
            wire_type = tag_wire & 0x7

            if wire_type == 0:            # varint
                val, pos = read_varint(data, pos)
                results.append({"field": field_num, "type": "varint", "value": val})

            elif wire_type == 1:          # 64-bit
                val = struct.unpack("<Q", data[pos:pos + 8])[0]
                pos += 8
                results.append({"field": field_num, "type": "int64", "value": val})

            elif wire_type == 5:          # 32-bit
                val = struct.unpack("<I", data[pos:pos + 4])[0]
                pos += 4
                results.append({"field": field_num, "type": "int32", "value": val})

            elif wire_type == 2:          # length-delimited (string / bytes / nested msg)
                length, pos = read_varint(data, pos)
                raw = data[pos:pos + length]
                pos += length

                try:
                    text = raw.decode("utf-8")
                    # Also try nested parse
                    nested = parse_pb(raw, depth + 1) if depth < max_depth else []
                    if nested:
                        results.append({"field": field_num, "type": "message", "value": nested, "as_string": text})
                    else:
                        results.append({"field": field_num, "type": "string", "value": text})
                except UnicodeDecodeError:
                    nested = parse_pb(raw, depth + 1) if depth < max_depth else []
                    if nested:
                        results.append({"field": field_num, "type": "message", "value": nested})
                    else:
                        results.append({"field": field_num, "type": "bytes", "value": raw.hex()})
            else:
                break   # unknown wire type — stop parsing this level

        except Exception:
            break

    return results


def extract_strings(parsed: list, min_len: int = 15) -> list:
    """Flatten parsed fields into readable strings only."""
    out = []
    for item in parsed:
        if item["type"] in ("string", "message"):
            if item["type"] == "string":
                t = item["value"].strip()
                if len(t) >= min_len:
                    out.append({"field": item["field"], "text": t})
            if item["type"] == "message":
                # check as_string too
                if "as_string" in item:
                    t = item["as_string"].strip()
                    if len(t) >= min_len:
                        out.append({"field": item["field"], "text": t})
                # recurse into nested
                out.extend(extract_strings(item["value"], min_len))
    return out


def dedupe(strings: list) -> list:
    seen, result = set(), []
    for s in strings:
        t = s["text"]
        if t not in seen:
            seen.add(t)
            result.append(s)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def decode_directory(pb_dir: str, as_json: bool = False, min_len: int = 15):
    if not os.path.isdir(pb_dir):
        print(f"[ERROR] Directory not found: {pb_dir}")
        sys.exit(1)

    pb_files = sorted(glob.glob(os.path.join(pb_dir, "*.pb")))
    if not pb_files:
        print(f"No .pb files found in: {pb_dir}")
        return

    all_results = []

    for fpath in pb_files:
        fname = os.path.basename(fpath)
        try:
            with open(fpath, "rb") as f:
                raw = f.read()
        except PermissionError:
            entry = {"file": fname, "error": "permission_denied", "strings": []}
            all_results.append(entry)
            if not as_json:
                print(f"\n{'='*60}")
                print(f"FILE: {fname}  ({len(raw) if 'raw' in dir() else '?'} bytes)")
                print("  ⚠️  macOS PERMISSION DENIED")
                print("  Fix: System Preferences → Privacy & Security → Full Disk Access")
            continue
        except Exception as e:
            entry = {"file": fname, "error": str(e), "strings": []}
            all_results.append(entry)
            continue

        parsed  = parse_pb(raw)
        strings = dedupe(extract_strings(parsed, min_len))
        entry   = {"file": fname, "size_bytes": len(raw), "strings": strings}
        all_results.append(entry)

        if not as_json:
            print(f"\n{'='*60}")
            print(f"FILE: {fname}  ({len(raw)} bytes)  — {len(strings)} string(s) decoded")
            print("-" * 60)
            if strings:
                for s in strings:
                    label = f"[f{s['field']}]"
                    print(f"  {label:<8} {s['text']}")
            else:
                print("  (no readable strings found)")

    if as_json:
        print(json.dumps(all_results, indent=2, ensure_ascii=False))
    else:
        total = sum(len(r.get("strings", [])) for r in all_results)
        print(f"\n{'='*60}")
        print(f"SUMMARY: {len(pb_files)} file(s) · {total} total string(s) decoded")
        print(f"PB directory: {pb_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decode Antigravity implicit memory .pb files")
    parser.add_argument("--dir",     default=os.path.expanduser("~/.gemini/antigravity/implicit"),
                        help="Path to the .pb directory (default: ~/.gemini/antigravity/implicit)")
    parser.add_argument("--json",    action="store_true", help="Output raw JSON")
    parser.add_argument("--min-len", type=int, default=15, help="Minimum string length to show (default: 15)")
    args = parser.parse_args()

    decode_directory(args.dir, as_json=args.json, min_len=args.min_len)
