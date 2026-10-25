"""Generate the synthetic Coralline Infusion Network (fictional) universe.

    python foundation/generate.py            # writes foundation/data/*.csv + manifest
    python foundation/generate.py --out DIR  # write somewhere else (used by the reproducibility test)

Standard library only. Same seed + same Python minor version -> byte-identical CSVs.
"""
import argparse
import csv
import hashlib
import json
import platform
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generator import config as C                      # noqa: E402
from generator import defects, dims, extensions, journeys, operations, snapshot  # noqa: E402
from generator.schema import TABLES                    # noqa: E402
from generator.util import fmt                         # noqa: E402

GENERATOR_VERSION = "1.1.0"


def build_tables():
    counties, crosswalk, sites = dims.build_geography()
    umbrellas, plans, umbrella_map, unmapped = dims.build_payers()
    providers, provider_specialties, specialties, profiles = dims.build_providers()

    plan_umbrella = {m["plan_key"]: m["umbrella_key"] for m in umbrella_map}
    plan_name = {p["plan_key"]: p["raw_plan_name"] for p in plans}
    plans_by_umbrella = defaultdict(list)
    for m in umbrella_map:
        weight = dict(C.PAYER_PLANS[m["umbrella_key"]])[plan_name[m["plan_key"]]]
        plans_by_umbrella[m["umbrella_key"]].append((m["plan_key"], weight))

    patients, intakes = journeys.build_intake(profiles)
    coverage = journeys.build_coverage(patients, plans_by_umbrella)
    sim = journeys.Journeys(profiles, journeys.coverage_index(coverage), plan_umbrella)
    sim.run(patients, intakes)

    t = dict(counties=counties, postal_county_crosswalk=crosswalk, sites=sites, specialties=specialties,
             therapies=dims.build_therapies(), payer_umbrellas=umbrellas, payer_plans=plans,
             payer_umbrella_map=umbrella_map, providers=providers, provider_specialties=provider_specialties,
             payer_history=coverage)
    t.update(snapshot.as_of_view(sim, patients))
    t["inventory_transactions"], t["inventory_snapshots"], t["purchase_orders"] = \
        operations.build_inventory(t["appointments"], t["administrations"])

    reg = defects.Register()
    defects.inject_core(t, reg, plan_umbrella, unmapped)
    defects.inject_inventory(t, reg)
    t["reporting_targets"] = operations.build_targets(t["appointments"])
    t["submission_log"] = operations.build_submission_log(t)
    defects.inject_submissions(t, reg)
    (t["synthetic_staff"], t["license_registry"], t["document_index"], t["site_licenses"],
     t["medical_director_assignment"]) = operations.build_licenses()
    defects.inject_licenses(t, reg)
    t["code_catalog"], t["mock_fee_schedule"], t["lookup_requests"] = operations.build_fee_schedule()
    # v1.1.0 extensions: own random streams, read-only over the core tables, register rows appended last.
    t["prescriptions"], t["rx_fills"], t["delivery_tickets"] = extensions.build_pharmacy(t, reg)
    t["accounting_ledger"] = extensions.build_accounting(t, reg)
    t["exceptions_register"] = reg.rows
    return t


def write_csvs(tables, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, spec in TABLES.items():
        cols = [c[0] for c in spec["columns"]]
        rows = tables[name]
        for r in rows:
            if set(r) != set(cols):
                raise ValueError(f"{name}: columns {sorted(set(r) ^ set(cols))} do not match schema")
        rows = sorted(rows, key=lambda r: tuple(fmt(r[k]) for k in spec["pk"]))
        path = out_dir / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(cols)
            for r in rows:
                w.writerow([fmt(r[c]) for c in cols])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(dict(table=name, file=path.name, rows=len(rows), family=spec["family"],
                            grain=spec["grain"], primary_key=spec["pk"], synthetic=True, sha256=digest))
    return entries


def write_manifest(entries, out_dir: Path):
    meta = dict(generator_version=GENERATOR_VERSION, seed=C.SEED, as_of=C.AS_OF.isoformat(),
                data_start=C.DATA_START.isoformat(), future_end=C.FUTURE_END.isoformat(),
                python=platform.python_version(), organization=C.ORG_NAME, disclaimer=C.DISCLAIMER,
                note="All rows are newly generated. Nothing is derived from or calibrated to employer data.",
                tables=entries)
    (out_dir / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "CHECKSUMS.sha256").open("w", encoding="utf-8", newline="\n") as fh:
        for e in entries:
            fh.write(f"{e['sha256']}  {e['file']}\n")


def write_docs(entries, tables, doc_dir: Path):
    rows = {e["table"]: e["rows"] for e in entries}
    lines = ["# Manifest - synthetic data foundation", "",
             f"> **{C.DISCLAIMER}.** Every table below is 100% synthetic, generated by `foundation/generate.py` "
             f"(seed `{C.SEED}`, snapshot as of {C.AS_OF:%B %d, %Y}).", "",
             f"Organization: **{C.ORG_NAME}**. Python {platform.python_version()}, standard library only. "
             "Checksums: `foundation/data/CHECKSUMS.sha256`.", "",
             "| Table | Family | Grain | Primary key | Rows | Brief's suggested volume | Synthetic |",
             "|---|---|---|---|---:|---:|:-:|"]
    for e in entries:
        target = C.VOLUME_TARGETS.get(e["table"])
        lines.append(f"| `{e['table']}` | {e['family']} | {e['grain']} | `{', '.join(e['primary_key'])}` | "
                     f"{e['rows']:,} | {f'{target:,}' if target else '-'} | yes |")
    lines += ["", "## Notes on volumes", "",
              "Appointments and administration lines run above the brief's suggested volumes because every completed "
              "visit carries at least one line and maintenance therapies recur. The brief lists volumes as suggestions; "
              "relationships and rates were kept realistic instead of forcing the totals.", "",
              "## Exceptions register summary", "",
              "| Origin | Defect / edge case | Rows |", "|---|---|---:|"]
    counts = defaultdict(int)
    for r in tables["exceptions_register"]:
        counts[(r["origin"], r["defect_type"])] += 1
    for (origin, dtype), n in sorted(counts.items()):
        lines.append(f"| {origin} | `{dtype}` | {n} |")
    (doc_dir / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    dd = ["# Data dictionary - synthetic data foundation", "",
          f"> {C.DISCLAIMER}. Generated from `foundation/generator/schema.py`; do not edit by hand.", ""]
    for name, spec in TABLES.items():
        dd += [f"## `{name}`", "", f"{spec['description']}", "",
               f"- **Grain:** {spec['grain']}  ", f"- **Primary key:** `{', '.join(spec['pk'])}`  ",
               f"- **Rows:** {rows[name]:,}", "", "| Column | Type | Description | References |", "|---|---|---|---|"]
        for col, typ, desc, fk in spec["columns"]:
            dd.append(f"| `{col}` | {typ} | {desc} | {f'`{fk}`' if fk else ''} |")
        dd.append("")
    (doc_dir / "DATA_DICTIONARY.md").write_text("\n".join(dd), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE / "data")
    parser.add_argument("--no-docs", action="store_true", help="skip MANIFEST.md / DATA_DICTIONARY.md")
    args = parser.parse_args()
    tables = build_tables()
    entries = write_csvs(tables, args.out)
    write_manifest(entries, args.out)
    if not args.no_docs:
        write_docs(entries, tables, HERE)
    total = sum(e["rows"] for e in entries)
    print(f"Wrote {len(entries)} tables, {total:,} rows -> {args.out}")


if __name__ == "__main__":
    main()
