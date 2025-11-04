#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zabbix → iTop CSV exporter (simple & pragmatic)
- Filters: required tags, groups, templates (all ANDed). If none provided → export all.
- Column mapping: Zabbix → iTop (e.g., "host:name,inventory.os:os,tags.location:location,zabbix_id:id")
- Dry-run prints a table preview instead of writing CSV.

Usage example:
  python zabbix_to_itop.py \
    --url https://zabbix.example.com \
    --user Admin --pass secret \
    --required_tags sync=itop,env=prod \
    --required_groups Linux,Production \
    --required_templates "Template OS Linux,Template App" \
    --columns host:name,inventory.os:os,tags.location:location,hostid:zabbix_id \
    --outfile Server.csv \
    --dry-run
"""

from __future__ import annotations

import argparse
import csv
import sys
from typing import Dict, List, Tuple, Any
import logging
import tqdm

try:
    from pyzabbix import ZabbixAPI  # type: ignore
except Exception as e:  # pragma: no cover
    print("ERROR: pyzabbix is required. Install with: pip install pyzabbix", file=sys.stderr)
    raise


# -------------------------
# Parsing helpers
# -------------------------

def parse_required_tags(s: str) -> Dict[str, str]:
    """
    Parse "k=v,k2=v2" into dict. Empty -> {}.
    """
    result: Dict[str, str] = {}
    s = (s or "").strip()
    if not s:
        return result
    parts = [p.strip() for p in s.split(",") if p.strip()]
    for p in parts:
        if "=" not in p:
            raise ValueError(f"Invalid required_tags entry (expected key=value): {p}")
        k, v = p.split("=", 1)
        result[k.strip()] = v.strip()
    return result


def parse_csv_list(s: str) -> List[str]:
    """
    Parse "a,b,c" → ["a","b","c"]. Empty -> [].
    Note: values with commas inside themselves are NOT supported by design.
    """
    s = (s or "").strip()
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def parse_columns_mapping(s: str) -> List[Tuple[str, str]]:
    """
    Parse "zbx_path:itop_field, zbx2:itop2" -> [(zbx_path, itop_field), ...]
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("--columns is required and cannot be empty")
    mapping: List[Tuple[str, str]] = []
    pairs = [p.strip() for p in s.split(",") if p.strip()]
    for pair in pairs:
        if ":" in pair:
            left, right = pair.split(":", 1)
            zbx_path = left.strip()
            itop_field = right.strip()
            if not zbx_path or not itop_field:
                raise ValueError(f"Invalid columns mapping entry (empty side): {pair}")
            mapping.append((zbx_path, itop_field))
        elif "=" in pair:
            left, right = pair.split("=", 1)
            itop_field = left.strip()
            itop_value = right.strip()
            if not itop_field or not itop_value:
                raise ValueError(f"Invalid columns mapping entry (empty side): {pair}")
            mapping.append(("itop:%s" % itop_field, itop_value))
        else:
            raise ValueError(f"Invalid columns mapping entry (expected zbx:itop): {pair}")
    return mapping


# -------------------------
# Zabbix helpers
# -------------------------

def host_matches_filters(
    host: Dict[str, Any],
    req_tags: Dict[str, str],
    req_groups: List[str],
    req_templates: List[str],
) -> bool:
    """
    Return True if host satisfies all provided filters.
    If all filter sets are empty, return True (export all).
    """
    if not req_tags and not req_groups and not req_templates:
        return True

    # Tags: build dict {tag: value}
    if req_tags:
        tag_map = {t.get("tag", ""): t.get("value", "") for t in host.get("tags", [])}
        for k, v in req_tags.items():
            if tag_map.get(k) != v:
                return False

    # Groups: list of names
    if req_groups:
        group_names = {g.get("name", "") for g in host.get("hostgroups", [])}
        for g in req_groups:
            if g not in group_names:
                return False

    # Templates: list of names
    if req_templates:
        tmpl_names = {t.get("name", "") for t in host.get("parentTemplates", [])}
        for t in req_templates:
            if t not in tmpl_names:
                return False

    return True


def extract_value_from_host(host: Dict[str, Any], zbx_path: str) -> str:
    """
    Extract a value from the Zabbix 'host' dict using simple path semantics:

    Supported prefixes:
      - "host"         -> host["host"] (technical name)
      - "name"         -> host["name"] (visible name)
      - "hostid"       -> host["hostid"]
      - "inventory.X"  -> host["inventory"]["X"]
      - "tags.T"       -> value for tag "T" (string)
      - "groups"       -> comma-joined list of group names
      - "templates"    -> comma-joined list of parent template names
      - fqdn           ->interfaces[0][dns]
      - ip             ->interfaces[0][ip]

    Otherwise, try host[zbx_path] (best-effort).
    Missing values -> "".
    """
    # Common short paths
    if zbx_path == "host":
        return str(host.get("host", "") or "")
    if zbx_path == "name":
        return str(host.get("name", "") or "")
    if zbx_path == "hostid":
        return str(host.get("hostid", "") or "")
    if zbx_path == "fqdn":
        return str(host.get("interfaces", "")[0]['dns'] or "")
    if zbx_path == "ip":
        return str(host.get("interfaces", "")[0]['ip'] or "")

    # inventory.foo
    if zbx_path.startswith("inventory."):
        key = zbx_path.split(".", 1)[1]
        try:
            return str(host.get("inventory", {}).get(key, ""))
        except Exception:
            return ""

    # tags.X -> value of tag X
    if zbx_path.startswith("tags."):
        tag_key = zbx_path.split(".", 1)[1]
        for t in host.get("tags", []):
            if t.get("tag") == tag_key:
                return str(t.get("value", "") or "")
        return ""

    # groups -> "g1,g2,..."
    if zbx_path == "groups":
        names = [g.get("name", "") for g in host.get("groups", []) if g.get("name")]
        return ",".join(names)

    # templates -> "t1,t2,..."
    if zbx_path in ("templates", "parentTemplates"):
        names = [t.get("name", "") for t in host.get("parentTemplates", []) if t.get("name")]
        return ",".join(names)

    # Fallback: top-level key
    val = host.get(zbx_path)
    if val is None:
        return ""
    if isinstance(val, (dict, list)):
        # best-effort stringify
        return str(val)
    return str(val)


def build_row_for_host(host: Dict[str, Any], mapping: List[Tuple[str, str]]) -> Dict[str, str]:
    """
    Build output row {itop_field: value} for the given host based on mapping (zbx_path -> itop_field).
    """
    row: Dict[str, str] = {}
    for zbx_path, itop_field in mapping:
        if ":" in zbx_path:
            # Static value itop:attribute
            field_name = zbx_path.split(":")[1]
            row[field_name] = itop_field
        else:
            row[itop_field] = extract_value_from_host(host, zbx_path)
    return row


# -------------------------
# I/O
# -------------------------

def print_table_preview(rows: List[Dict[str, str]], max_rows: int = 20) -> None:
    """
    Pretty-print a small table of the first N rows without external deps.
    """
    if not rows:
        print("(no rows)")
        return

    headers = list(rows[0].keys())
    sample = rows[:max_rows]

    # compute column widths
    widths = {h: len(h) for h in headers}
    for r in sample:
        for h in headers:
            widths[h] = max(widths[h], len(str(r.get(h, ""))))

    # header
    header_line = " | ".join(h.ljust(widths[h]) for h in headers)
    sep_line = "-+-".join("-" * widths[h] for h in headers)
    print(header_line)
    print(sep_line)

    # rows
    for r in sample:
        print(" | ".join(str(r.get(h, "")).ljust(widths[h]) for h in headers))

    if len(rows) > max_rows:
        print(f"... ({len(rows) - max_rows} more rows)")


def write_csv(outfile: str, rows: List[Dict[str, str]]) -> None:
    if not rows:
        # still create an empty CSV with just headers? We'll skip to be explicit.
        print("No rows to write; skipping CSV.")
        return
    headers = list(rows[0].keys())
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ Wrote {len(rows)} rows to {outfile}")


# -------------------------
# Main
# -------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Zabbix hosts to iTop-compatible CSV (filters + Zabbix→iTop mapping)."
    )
    parser.add_argument("--url", required=True, help="Zabbix API URL, e.g., https://zabbix.example.com")
    parser.add_argument("--user", required=True, help="Zabbix username")
    parser.add_argument("--pass", dest="password", required=True, help="Zabbix password")

    parser.add_argument("--required_tags", default="", help="Comma list of tag=value pairs, e.g., sync=itop,env=prod")
    parser.add_argument("--required_groups", default="", help="Comma list of group names, e.g., Linux,Production")
    parser.add_argument("--required_templates", default="", help='Comma list of template names, e.g., "Template OS Linux,Template App"')

    parser.add_argument("--columns", required=True, help="Mapping Zabbix→iTop, e.g., host:name,inventory.os:os,tags.location:location,hostid:zabbix_id,org=org")
    parser.add_argument("--unique", required=False, default="", help="Zabbix unique path (for logging/validation); not enforced in CSV")

    parser.add_argument("--outfile", default="output.csv", help="Output CSV file path (default: output.csv)")
    parser.add_argument("--dry-run", action="store_true", help="Print a table preview instead of writing CSV")
    parser.add_argument("--debug", action="store_true", help="Enable debugging")
    parser.add_argument("--perhost", action="store_true", help="If set to true, iterate calls host by host, not to fetch everything at once.")

    args = parser.parse_args()

    try:
        req_tags = parse_required_tags(args.required_tags)
        req_groups = parse_csv_list(args.required_groups)
        req_templates = parse_csv_list(args.required_templates)
        mapping = parse_columns_mapping(args.columns)
        if args.unique:
            unique = args.unique.split(",")
        else:
            unique = False
    except ValueError as ve:
        print(f"Argument error: {ve}", file=sys.stderr)
        sys.exit(2)

    if args.debug:
        logging.getLogger().setLevel("DEBUG")
    else:
        logging.getLogger().setLevel("WARNING")

    # Connect to Zabbix
    zapi = ZabbixAPI(args.url)
    zapi.login(args.user, args.password)

    # Fetch hosts with all the extended info we need
    if args.perhost:
        hosts: List[Dict[str, Any]] = zapi.host.get(
            output=["hostid"]
        )
    else:
        hosts: List[Dict[str, Any]] = zapi.host.get(
            selectInventory="extend",
            selectHostGroups="extend",
            selectTags="extend",
            selectParentTemplates="extend",
            selectInterfaces="extend"
        )

    # Filter + build rows
    rows: List[Dict[str, str]] = []
    uniqueset = []
    for h in tqdm.tqdm(hosts):
        if args.perhost:
            h = zapi.host.get(
                hostids=h["hostid"],
                selectInventory="extend",
                selectHostGroups="extend",
                selectTags="extend",
                selectParentTemplates="extend",
                selectInterfaces="extend"
            )[0]
        if not host_matches_filters(h, req_tags, req_groups, req_templates):
            logging.info("Skipping host %s (did not pass filters)" % h)
            continue
        row = build_row_for_host(h, mapping)
        # Optional: warn if unique path was provided but not present/mapped (soft check)
        if unique:
            # try to see if at least one column maps the unique path
            # (not enforced; only a heads-up for the operator)
            rowid = []
            for u in unique:
                rowid.append(row[u])
            if rowid in uniqueset:
                logging.debug("Rowid %s already reported as unique. Skipping" % rowid)
            else:
                uniqueset.append(rowid)
        rows.append(row)



    if args.dry_run:
        print(f"Matched hosts: {len(rows)} (dry-run)")
        print_table_preview(rows)
    else:
        write_csv(args.outfile, rows)


if __name__ == "__main__":
    main()
