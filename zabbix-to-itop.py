#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import os
from typing import Dict, List, Tuple, Any
import logging

import jinja2
import tqdm
import yaml
from zabbix_utils import ZabbixAPI  # type: ignore
from zabbixhost import ZabbixHost

def get_output_columns(cfg):
    columns = []
    for c in cfg["columns"]:
        if c.get("static"):
            columns.append(c.get("static")["itop"])
        elif c.get("map"):
            columns.append(c.get("map")["itop"])
        elif c.get("template"):
            columns.append(c.get("template")["itop"])
    if len(list(set(columns))) != len(columns):
        raise Exception("Destination itop attributes are not unique!")
    return columns

def build_row_for_host(h: ZabbixHost, cfg) -> Dict[str, str]:
    """
    Build output row for this host based on structured YAML column list.
    columns is a list of dict entries, each in one of forms:

      - static:
          itop: "Organization->Name"
          value: "Org1"

      - template:
          itop: "Description"
          value: "{{ h.host() }} {{ h.inv('os') }}"

      - map:
          zabbix: "inventory.os"
          itop: "OS family->Name"
    """
    row: Dict[str, str] = {}

    for entry in cfg["columns"]:
        if "static" in entry:
            spec = entry["static"]
            itop_attr = spec["itop"]
            value = spec.get("value", "") or ""
            row[itop_attr] = value

        elif "template" in entry:
            spec = entry["template"]
            itop_attr = spec["itop"]
            tmpl = spec.get("value","") or ""
            row[itop_attr] = h._expand_macros(tmpl)

        elif "map" in entry:
            spec = entry["map"]
            itop_attr = spec["itop"]
            zpath = spec["zabbix"]
            if "." in zpath:
                prefix, key = zpath.split(".", 1)
                # fallback for future prefixes / direct macro
                fn = getattr(h, prefix, None)
                args = key
                if callable(fn):
                    row[itop_attr] = fn(args)
                else:
                    row[itop_attr] = ""
            else:
                # direct macro like "host" → h.host()
                fn = getattr(h, zpath, None)
                if callable(fn):
                    row[itop_attr] = fn()
                else:
                    row[itop_attr] = ""

    return row


def write_csv(outfile: str, rows: List[Dict[str, str]], columns) -> None:
    if not rows:
        # still create an empty CSV with just headers? We'll skip to be explicit.
        print("No rows to write; skipping CSV.")
        return
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ Wrote {len(rows)} rows to {outfile}")


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


# -------------------------
# Main
# -------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Zabbix hosts to iTop-compatible CSV (filters + Zabbix→iTop mapping)."
    )
    parser.add_argument("--config", required=True, help="Config file")
    parser.add_argument("--debug", action="store_true", help="Enable debugging")
    parser.add_argument("--skip-existing", action="store_true", help="Skip existing output files")
    gargs = parser.parse_args()

    with open(gargs.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if gargs.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        zlog = logging.getLogger('pyzabbix')
        zlog.setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel("WARNING")

    args = cfg.get("options")

    for output in tqdm.tqdm(cfg.get("outputs").keys()):

        ocfg = cfg.get("outputs")[output]
        if gargs.skip_existing and os.path.exists(ocfg.get("outfile")):
            logging.warning("Skipping output %s (file already exists)" % output)
            continue

        logging.warning("Processing output %s" % output)
        columns = get_output_columns(ocfg)

        # Connect to Zabbix
        zapi = ZabbixAPI(args.get("url"))
        zapi.login(user=args.get("user"), password=args.get("password"))

        # Fetch hosts with all the extended info we need
        zargs = {
            output: ["hostid"]
        }
        if ocfg.get("required_groups"):
            zargs["groupids"] = zapi.hostgroup.get(
                output=["groupid"],
                filter={"name": ocfg.get("required_groups")}
            )
        if ocfg.get("required_templates"):
            zargs["templateids"] = zapi.hostgroup.get(
                output=["templateid"],
                filter={"name": ocfg.get("required_templates")}
            )
        if ocfg.get("required_tags"):
            zargs["tags"] = []
            for tag in ocfg.get("required_tags"):
                (name, value) = tag.split("=")
                zargs["tags"].append({
                    "tag": name,
                    "value": value,
                    "operator": 0
                })

        hostids: List[Dict[str, Any]] = zapi.host.get(**zargs)

        # Filter + build rows
        rows: List[Dict[str, str]] = []
        uniqueset = []
        for batch in tqdm.tqdm(list(chunks(hostids, ocfg.get("batch_size", 100))), unit="host", unit_scale=ocfg.get("batch_size", 100)):
            hostids = []
            for h in batch:
                hostids.append(h["hostid"])
            zbatch = zapi.host.get(
                hostids=hostids,
                selectInventory="extend",
                selectHostGroups="extend",
                selectTags="extend",
                selectParentTemplates=[
                    "templateid",
                    "name"
                ],
                selectInterfaces="extend",
                selectInheritedTags="extend"
            )

            for h in zbatch:
                zh = ZabbixHost(h, ocfg)
                if not zh._matches():
                    logging.info("Skipping host %s (did not pass filters)" % h)
                    continue
                row = build_row_for_host(zh, ocfg)
                # Optional: warn if unique path was provided but not present/mapped (soft check)
                if ocfg.get("unique"):
                    # try to see if at least one column maps the unique path
                    # (not enforced; only a heads-up for the operator)
                    rowid = []
                    for u in ocfg.get("unique"):
                        rowid.append(row[u])
                    if rowid in uniqueset:
                        logging.debug("Rowid %s already reported as unique. Skipping" % rowid)
                    else:
                        uniqueset.append(rowid)
                        rows.append(row)
                else:
                    rows.append(row)
        if len(rows) > 0:
            write_csv(ocfg.get("outfile"), rows, columns)
            cmd = ocfg.get("import_cmd", "")
            if cmd:
                env = jinja2.Environment(
                    loader=jinja2.BaseLoader(),
                    autoescape=False,
                    trim_blocks=True,
                    lstrip_blocks=True,
                )
                tmpl = env.from_string(cmd)
                cmd = tmpl.render(outfile=ocfg.get("outfile"))
                os.system(cmd)

        else:
            logging.warning("Zero rows for %s" % ocfg.get("outfile"))


if __name__ == "__main__":
    main()
