"""Generate the synthetic dataset: data/vocab.json and data/records.csv.

Everything here is invented. Names, sites, and products are fictional, and no real company
data, system names, or quality records are used. The records deliberately mention equipment
and products in different ways (preferred name, abbreviation, slang, typo) because that is the
terminology problem the project demonstrates.
"""

import csv
import json
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

SITES = [("SITE-N", "Plant North"), ("SITE-E", "Plant East"), ("SITE-S", "Plant South")]

PRODUCTS = [
    ("PRD-001", "Cardiostat 20 mg tablet", ["CST-20", "cardiostat 20", "cardiostat tabs"]),
    ("PRD-002", "Cardiostat 40 mg tablet", ["CST-40", "cardiostat 40"]),
    ("PRD-003", "Dermacalm 1% cream", ["DCC-1", "dermacalm cream", "dermacalm 1 percent"]),
    ("PRD-004", "Analgex 25 mcg/h transdermal patch", ["AGX-25", "analgex patch", "analgex 25"]),
    ("PRD-005", "Airvent inhalation aerosol", ["AVT-IA", "airvent inhaler"]),
    ("PRD-006", "Alleject auto-injector", ["ALJ-AI", "alleject pen"]),
]

# id, label, site, type, aliases. The same short names ('press 4', 'mixer 11', 'autoclave 7')
# are used at more than one site on purpose.
EQUIPMENT = [
    ("EQ-N-TP04", "Tablet Press TP-04", "SITE-N", "Tablet press", ["TP-04", "press 4", "tab press 4"]),
    ("EQ-N-CP02", "Coating Pan CP-02", "SITE-N", "Coating pan", ["CP-02", "coat pan 2", "coating pan 2"]),
    ("EQ-N-MV11", "Mixing Vessel MV-11", "SITE-N", "Mixing vessel", ["MV-11", "mixer 11", "cream mixer 11"]),
    ("EQ-E-TP04", "Tablet Press TP-04", "SITE-E", "Tablet press", ["TP-04", "press 4", "tab press 4"]),
    ("EQ-E-PL03", "Patch Coating Line PL-03", "SITE-E", "Patch coating line", ["PL-03", "patch line 3", "coating line 3"]),
    ("EQ-E-AC07", "Autoclave AC-07", "SITE-E", "Autoclave", ["AC-07", "autoclave 7"]),
    ("EQ-S-MV11", "Mixing Vessel MV-11", "SITE-S", "Mixing vessel", ["MV-11", "mixer 11", "cream mixer 11"]),
    ("EQ-S-AC07", "Autoclave AC-07", "SITE-S", "Autoclave", ["AC-07", "autoclave 7"]),
    ("EQ-S-AI01", "Auto-Injector Assembly Line AI-01", "SITE-S", "Assembly line", ["AI-01", "assembly line 1"]),
]

EVENT = {
    "Tablet press": ("Tablet weight drift", "Tablet weight drifted outside the in-process limit during a compression run on {eq}; run paused and samples pulled{prod}."),
    "Coating pan": ("Coating variability", "Coating thickness variability observed in {eq}; spray rate adjusted{prod}."),
    "Mixing vessel": ("Viscosity out of range", "Viscosity was outside specification after mixing in {eq}; batch placed on hold{prod}."),
    "Patch coating line": ("Coat weight variation", "Adhesive coat weight varied along the roll from {eq}; line stopped for inspection{prod}."),
    "Autoclave": ("Cycle did not reach set point", "Load temperature did not reach the set point during a sterilization cycle in {eq}; cycle aborted{prod}."),
    "Assembly line": ("Assembly jam", "Assembly jam on {eq}; operator cleared the jam and logged it{prod}."),
}

EQ_BY_ID = {e[0]: e for e in EQUIPMENT}

# Physical hierarchy: site > area > line > equipment. Some equipment sits directly under an area.
HIERARCHY_NODES = [   # id, label, kind, parent
    ("AREA-N-SD", "Solid Dose Area", "Area", "SITE-N"),
    ("LINE-N-CMP1", "Compression Line 1", "Line", "AREA-N-SD"),
    ("LINE-N-CT1", "Coating Line 1", "Line", "AREA-N-SD"),
    ("AREA-N-SS", "Semi-Solids Area", "Area", "SITE-N"),
    ("LINE-N-CR1", "Cream Line 1", "Line", "AREA-N-SS"),
    ("AREA-E-SD", "Solid Dose Area", "Area", "SITE-E"),
    ("LINE-E-CMP1", "Compression Line 1", "Line", "AREA-E-SD"),
    ("AREA-E-TD", "Transdermal Area", "Area", "SITE-E"),
    ("AREA-E-ST", "Sterilization Area", "Area", "SITE-E"),
    ("AREA-S-SS", "Semi-Solids Area", "Area", "SITE-S"),
    ("LINE-S-CR1", "Cream Line 1", "Line", "AREA-S-SS"),
    ("AREA-S-ST", "Sterilization Area", "Area", "SITE-S"),
    ("AREA-S-DA", "Device Assembly Area", "Area", "SITE-S"),
]

EQUIPMENT_PARENT = {
    "EQ-N-TP04": "LINE-N-CMP1",
    "EQ-N-CP02": "LINE-N-CT1",
    "EQ-N-MV11": "LINE-N-CR1",
    "EQ-E-TP04": "LINE-E-CMP1",
    "EQ-E-PL03": "AREA-E-TD",
    "EQ-E-AC07": "AREA-E-ST",
    "EQ-S-MV11": "LINE-S-CR1",
    "EQ-S-AC07": "AREA-S-ST",
    "EQ-S-AI01": "AREA-S-DA",
}

# record id, site, equipment id, equipment mention, product mention (or None), opened on
DEVIATIONS = [
    ("DEV-0001", "SITE-N", "EQ-N-TP04", "press 4", "cardiostat 20", "2026-01-12"),
    ("DEV-0002", "SITE-E", "EQ-E-TP04", "press 4", "CST-40", "2026-01-19"),
    ("DEV-0003", "SITE-N", "EQ-N-CP02", "coat pan 2", "Cardiostat 20 mg tablet", "2026-02-03"),
    ("DEV-0004", "SITE-N", "EQ-N-MV11", "mixer 11", "Dermacalm 1% cream", "2026-02-10"),
    ("DEV-0005", "SITE-S", "EQ-S-MV11", "mixer 11", "dermacalm cream", "2026-02-17"),
    ("DEV-0006", "SITE-E", "EQ-E-PL03", "patch line 3", "AGX-25", "2026-02-24"),
    ("DEV-0007", "SITE-E", "EQ-E-AC07", "autoclave 7", None, "2026-03-03"),
    ("DEV-0008", "SITE-S", "EQ-S-AC07", "AC-07", "alleject pen", "2026-03-10"),
    ("DEV-0009", "SITE-S", "EQ-S-AI01", "assembly line 1", "ALJ-AI", "2026-03-17"),
    ("DEV-0010", "SITE-N", "EQ-N-TP04", "tablet pres 4", "cardiostat tabs", "2026-03-24"),   # typo
    ("DEV-0011", "SITE-E", "EQ-E-PL03", "coating line 3", "analgex patch", "2026-04-01"),
    ("DEV-0012", "SITE-N", "EQ-N-CP02", "coatin pan 2", "cardiostat 40", "2026-04-08"),       # typo
    ("DEV-0013", "SITE-E", "EQ-E-TP04", "TP-04", "CST-20", "2026-04-15"),
    ("DEV-0014", "SITE-S", "EQ-S-AC07", "autoclav 7", None, "2026-04-22"),                     # typo
    ("DEV-0015", "SITE-N", "EQ-N-MV11", "cream mixer 11", "DCC-1", "2026-04-29"),
    ("DEV-0016", "SITE-S", "EQ-S-AI01", "assembly line one", None, "2026-05-06"),              # near-miss spelling
]

INVESTIGATIONS = [   # id, parent deviation, equipment mention, finding
    ("INV-0001", "DEV-0001", "tab press 4", "Worn feed frame suspected as the cause of the weight drift."),
    ("INV-0002", "DEV-0002", "TP-04", "Powder flow change in the incoming lot is the leading explanation."),
    ("INV-0003", "DEV-0003", "CP-02", "Spray nozzle partially blocked; cleaning record under review."),
    ("INV-0004", "DEV-0004", "MV-11", "Mixing time was shortened by a recipe edit."),
    ("INV-0005", "DEV-0005", "cream mixer 11", "Temperature probe drift is being checked."),
    ("INV-0006", "DEV-0006", "PL-03", "Coating head gap found outside tolerance."),
    ("INV-0007", "DEV-0008", "autoclave 7", "Steam supply pressure was low during the cycle."),
    ("INV-0008", "DEV-0009", "AI-01", "Feeder bowl vibration setting changed after maintenance."),
    ("INV-0009", "DEV-0010", "press 4", "Same feed frame wear as an earlier investigation."),
    ("INV-0010", "DEV-0012", "coating pan 2", "Air handling unit alarm was active during the run."),
    ("INV-0011", "DEV-0013", "tab press 4", "No equipment fault found; operator setup being reviewed."),
    ("INV-0012", "DEV-0015", "mixer 11", "Paddle speed log shows a setpoint change."),
]

CAPAS = [   # id, parent investigation, action. CAPA-0008 points at an investigation that does not exist
    ("CAPA-0001", "INV-0001", "Replace the feed frame and add it to the preventive maintenance schedule."),
    ("CAPA-0002", "INV-0002", "Add an incoming powder flow check before compression."),
    ("CAPA-0003", "INV-0004", "Lock the mixing time in the recipe so edits need approval."),
    ("CAPA-0004", "INV-0006", "Reset the coating head gap and add a gap check to line startup."),
    ("CAPA-0005", "INV-0007", "Add a steam pressure check before each sterilization cycle."),
    ("CAPA-0006", "INV-0008", "Add a vibration setting check to the post-maintenance checklist."),
    ("CAPA-0007", "INV-0010", "Service the air handling unit and review the alarm response procedure."),
    ("CAPA-0008", "INV-9999", "Review the training record for the line operators."),   # planted defect
]

# A record at Plant East that refers to equipment at Plant North: a cross-site reference, not the equipment involved.
EXTRA = [
    ("DEV-0017", "SITE-E", "2026-05-13", "Coating variability (reference)",
     "Coating thickness variability seen on a small batch at Plant East. A similar issue was reported earlier on coat pan 2 at Plant North for cardiostat 20."),
]


def main() -> None:
    DATA.mkdir(exist_ok=True)
    vocab = {
        "sites": [{"id": i, "label": l} for i, l in SITES],
        "products": [{"id": i, "label": l, "aliases": a} for i, l, a in PRODUCTS],
        "equipment": [{"id": i, "label": l, "site": s, "type": t, "aliases": a} for i, l, s, t, a in EQUIPMENT],
    }
    (DATA / "vocab.json").write_text(json.dumps(vocab, indent=2) + "\n", encoding="utf-8")

    hierarchy = {
        "nodes": [{"id": i, "label": l, "kind": k, "parent": p} for i, l, k, p in HIERARCHY_NODES],
        "equipment_parent": EQUIPMENT_PARENT,
    }
    (DATA / "hierarchy.json").write_text(json.dumps(hierarchy, indent=2) + "\n", encoding="utf-8")

    rows = []
    dev_site, dev_date = {}, {}
    for rid, site, eq_id, eq_mention, prod_mention, opened in DEVIATIONS:
        etype = EQ_BY_ID[eq_id][3]
        title, template = EVENT[etype]
        prod = f" for {prod_mention}" if prod_mention else ""
        rows.append([rid, "Deviation", site, opened, title, template.format(eq=eq_mention, prod=prod), ""])
        dev_site[rid], dev_date[rid] = site, date.fromisoformat(opened)
    for rid, site, opened, title, desc in EXTRA:
        rows.append([rid, "Deviation", site, opened, title, desc, ""])
    inv_site, inv_date = {}, {}
    for rid, parent, eq_mention, finding in INVESTIGATIONS:
        opened = dev_date[parent] + timedelta(days=7)
        rows.append([rid, "Investigation", dev_site[parent], opened.isoformat(),
                     f"Investigation of {parent}", f"Findings on {eq_mention}: {finding}", parent])
        inv_site[rid], inv_date[rid] = dev_site[parent], opened
    for rid, parent, action in CAPAS:
        site = inv_site.get(parent, "SITE-E")
        opened = inv_date.get(parent, date(2026, 5, 20)) + timedelta(days=14)
        rows.append([rid, "CAPA", site, opened.isoformat(), "Corrective action", action, parent])

    with (DATA / "records.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record_id", "record_type", "site_id", "opened_on", "title", "description", "parent_id"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} records and a vocabulary with {len(PRODUCTS)} products and {len(EQUIPMENT)} equipment items.")


if __name__ == "__main__":
    main()
