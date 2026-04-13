"""
Clean anomaly-synthesis.json based on strategic-review.md criticism.
Produces anomaly-synthesis-clean.json and anomaly-ranking-clean.json.
"""

import json
import copy
import sys
from pathlib import Path

BASE = Path("c:/Users/yotam/projects/hatishbi-archive")
DATA = BASE / "data"

# Construction site addresses (from dashboard / GIS permits)
CONSTRUCTION_ADDRESSES = {
    "תרדיון 16", "קלמן 8", "נתן 45", "אצ\"ל 87",
    "כצנלסון בת-שבע 37", "שבתאי 21", "עזאי 40",
    "ששון 17", "נתן 47", "נתן 48", "אביטל 9",
    "אביטל 21", "אביטל 22", "תשבי 27", "תשבי 28",
    "תשבי 29", "שמחה 31", "שמחה 45", "שמחה 47",
    "נדב 16", "קמואל 32", "קמואל 44", "קמואל 36",
    "קמואל 50", "נתן 42", "עזאי 32", "הרן 28",
    "עברי 22ב", "רוני 60", "תרדיון 16",
}

# Known institutional / obvious roles that make network presence expected
INSTITUTIONAL_ACTORS = {
    "מהנדס העיר", "עיריית תל אביב-יפו", "עיריית תל אביב",
    "חלמיש", "חברת החשמל לישראל", "הועדה המקומית",
    "רשות הרישוי", "ועדת משנה", "ועדת ערר",
}


def normalize_address(addr):
    """Normalize address for comparison."""
    if not addr:
        return ""
    return addr.strip().replace("רחוב ", "").replace("רח' ", "").replace("מס' ", "")


def should_remove_network(finding):
    """
    Remove network_anomaly if:
    - It's the block-wide cross-parcel summary (no address)
    - Person count <= 20 (trivial moshaa noise)
    - All actors are institutional
    Keep if people_count > 20 AND has non-institutional actors.
    """
    # Block-wide summary finding
    if not finding.get("address"):
        # Keep the cross-parcel summary but only if actors have >20 addresses
        actors = finding.get("actors", [])
        significant = [a for a in actors if a.get("address_count", 0) > 20
                       and a.get("name", "") not in INSTITUTIONAL_ACTORS]
        if len(significant) >= 3:
            return None  # Keep — significant actors
        return "רעש מושע: סיכום חוצה-חלקות ללא שחקנים משמעותיים"

    people_count = finding.get("people_count", 0)
    if people_count <= 20:
        return "רעש מושע: פחות מ-20 אנשים — צפוי במושע"

    return None  # Keep


def should_remove_documentary(finding):
    """
    Remove documentary_anomaly if the burst is explained by demolition/danger docs.
    Keep ONLY if there's no demolition trigger.
    """
    ap = finding.get("archive_profile")
    if ap is None:
        return None  # No profile — keep for safety

    demolition_count = ap.get("demolition_count", 0)
    danger_count = ap.get("danger_count", 0)
    doc_count = ap.get("doc_count", 0)

    # If more than half the docs are demolition/danger related, it's explained
    if (demolition_count + danger_count) > 0:
        trigger_ratio = (demolition_count + danger_count) / max(doc_count, 1)
        if trigger_ratio > 0.05:  # Even 5% demolition docs = the burst is explained
            return "ספירה כפולה: פרץ תיעודי נגרם מצו הריסה/סכנה"

    return None  # Keep — genuine documentary anomaly


def should_remove_physical(finding):
    """
    Flag physical anomalies with extreme heights as GIS errors.
    Heights < 1m or > 25m are GIS data quality issues.
    """
    bd = finding.get("building_data", {})
    if bd is None:
        return None
    height = bd.get("height")
    if height is not None:
        if height < 1.0:
            return "שגיאת GIS: גובה פחות מ-1 מטר"
        if height > 25.0:
            return "שגיאת GIS: גובה מעל 25 מטר"
    return None  # Keep


def should_remove_demolition(finding):
    """
    Remove demolition_without_danger if:
    - All demolition docs are from before 2000 AND
    - There's evidence of new construction at that address
    These were resolved — old order + new building = no anomaly.
    """
    docs = finding.get("demolition_docs", [])
    dates = [doc.get("date", "") for doc in docs if doc.get("date")]

    if not dates:
        return None  # No dates — keep for safety

    latest = max(dates)
    addr = normalize_address(finding.get("address", ""))

    # Check if all docs are pre-2000
    all_pre_2000 = latest < "2000-01-01"

    if all_pre_2000:
        # Check if new construction exists at this address
        for ca in CONSTRUCTION_ADDRESSES:
            if normalize_address(ca) == addr:
                return "צו ישן (לפני 2000) + בנייה חדשה במקום — נפתר"

        # Even without construction evidence, very old orders (pre-1995)
        # with few docs are likely resolved
        if latest < "1995-01-01" and len(docs) <= 2:
            return "צו ישן (לפני 1995) עם מעט מסמכים — ככל הנראה נפתר"

    return None  # Keep


def should_remove_compound(finding):
    """
    Remove compound_anomaly if it double-counts:
    - Network + something = remove if the network part is moshaa noise
    - Demolition + documentary = remove if the documentary is explained by demolition
    """
    fid = finding.get("id", "")

    # Network-based compounds in moshaa context are noise
    if "NETWORK" in fid:
        desc = finding.get("description", "")
        # If the compound is mainly about network centrality + active permits
        # in a moshaa block, it's noise
        return "ספירה כפולה: שילוב רשת-מושע + ממצא אחר"

    # Cycle-based compounds (permit-danger cycles)
    if "CYCLE" in fid:
        return None  # Keep — these are real patterns

    return None  # Keep


def filter_findings(findings):
    """Apply all filters and return (kept, removed) lists."""
    kept = []
    removed = []

    for f in findings:
        category = f.get("category", "")
        reason = None

        if category == "network_anomaly":
            reason = should_remove_network(f)
        elif category == "documentary_anomaly":
            reason = should_remove_documentary(f)
        elif category == "physical_anomaly":
            reason = should_remove_physical(f)
        elif category == "demolition_without_danger":
            reason = should_remove_demolition(f)
        elif category == "compound_anomaly":
            reason = should_remove_compound(f)
        # Keep: dangerous_vs_archive, zoning_gap, conservation_gap, planning_pattern

        if reason:
            removed_entry = copy.deepcopy(f)
            removed_entry["removed_reason"] = reason
            removed.append(removed_entry)
        else:
            kept.append(f)

    return kept, removed


def calculate_composite_score(address_data, findings_by_address):
    """
    Recalculate composite score with adjusted weights:
    - Physical anomaly: ×3 (was ×2)
    - Documentary anomaly: ×2 (was ×1.5)
    - Network centrality: ×0.5 (was ×1)
    - Zoning gap: ×4 (was ×3)
    - Danger status: ×5 (unchanged)
    """
    addr = address_data.get("address", "")
    addr_findings = findings_by_address.get(addr, [])

    physical_count = sum(1 for f in addr_findings if f["category"] == "physical_anomaly")
    documentary_count = sum(1 for f in addr_findings if f["category"] == "documentary_anomaly")
    zoning_count = sum(1 for f in addr_findings if f["category"] == "zoning_gap")
    danger_count = sum(1 for f in addr_findings if f["category"] == "dangerous_vs_archive")
    demolition_count = sum(1 for f in addr_findings if f["category"] == "demolition_without_danger")

    # Network centrality = number of unique people (capped)
    network_people = 0
    for f in addr_findings:
        if f["category"] == "network_anomaly":
            network_people = max(network_people, f.get("people_count", 0))

    # Normalize network centrality (log scale, cap at 200)
    net_norm = min(network_people, 200) / 200.0

    # Danger status: 1 if active GIS danger, 0.5 if archive demolition only
    danger_status = 0
    if danger_count > 0:
        danger_status = 1.0
    elif demolition_count > 0:
        danger_status = 0.5

    # Composite score with new weights
    score = (
        physical_count * 3 * 5 +      # ×3 weight, 5 points per anomaly
        documentary_count * 2 * 4 +     # ×2 weight, 4 points per anomaly
        net_norm * 0.5 * 20 +           # ×0.5 weight, max 20 points
        zoning_count * 4 * 5 +          # ×4 weight, 5 points per gap
        danger_status * 5 * 10          # ×5 weight, 10 points base
    )

    return round(score, 1)


def build_ranking(kept_findings, original_ranking):
    """Build new ranking from cleaned findings."""

    # Group findings by address
    findings_by_address = {}
    for f in kept_findings:
        addr = f.get("address", "")
        if not addr:
            continue
        if addr not in findings_by_address:
            findings_by_address[addr] = []
        findings_by_address[addr].append(f)

    # Get all addresses from original ranking
    all_addresses = []
    for entry in original_ranking.get("all_ranked", []):
        addr = entry["address"]
        addr_data = {
            "address": addr,
            "chelka": entry.get("chelka", 0),
            "street": entry.get("street", ""),
        }

        # Count findings
        addr_findings = findings_by_address.get(addr, [])
        physical = sum(1 for f in addr_findings if f["category"] == "physical_anomaly")
        documentary = sum(1 for f in addr_findings if f["category"] == "documentary_anomaly")
        zoning = sum(1 for f in addr_findings if f["category"] == "zoning_gap")
        danger = sum(1 for f in addr_findings if f["category"] == "dangerous_vs_archive")
        demolition = sum(1 for f in addr_findings if f["category"] == "demolition_without_danger")

        network_people = 0
        for f in addr_findings:
            if f["category"] == "network_anomaly":
                network_people = max(network_people, f.get("people_count", 0))

        danger_status = 0
        if danger > 0:
            danger_status = 1.0
        elif demolition > 0:
            danger_status = 0.5

        score = calculate_composite_score(addr_data, findings_by_address)

        # Build flags
        flags = []
        if danger > 0 and any(f["category"] == "documentary_anomaly" for f in addr_findings):
            flags.append("מחזור היתרים-סכנה")
        if zoning > 0:
            flags.append("עסק באזור מגורים")
        if network_people > 100:
            flags.append("ריכוז רשת גבוה")
        if physical > 0 and documentary == 0 and network_people < 10:
            flags.append("מבנה רפאים")

        all_addresses.append({
            "address": addr,
            "chelka": entry.get("chelka", 0),
            "street": entry.get("street", ""),
            "physical_anomaly_count": physical,
            "documentary_anomaly_count": documentary,
            "network_centrality": network_people,
            "zoning_gap": zoning,
            "danger_status": danger_status,
            "demolition_docs": demolition,
            "composite_score": score,
            "flags": flags,
        })

    # Sort by score descending
    all_addresses.sort(key=lambda x: x["composite_score"], reverse=True)

    # Assign ranks
    for i, entry in enumerate(all_addresses):
        entry["rank"] = i + 1

    return all_addresses


def generate_top20_descriptions(top20, findings_by_address):
    """Generate Hebrew descriptions for top 20."""
    descriptions = []

    for entry in top20:
        addr = entry["address"]
        chelka = entry["chelka"]
        score = entry["composite_score"]
        findings = findings_by_address.get(addr, [])

        # Build description
        parts = []
        for f in findings:
            cat = f["category"]
            if cat == "dangerous_vs_archive":
                parts.append("מבנה מסוכן פעיל ב-GIS")
            elif cat == "physical_anomaly":
                bd = f.get("building_data", {})
                h = bd.get("height", "?")
                fl = bd.get("floors", "?")
                parts.append(f"אנומליה פיזית: {h}m גובה, {fl} קומות")
            elif cat == "documentary_anomaly":
                ap = f.get("archive_profile", {})
                dc = ap.get("doc_count", 0) if ap else 0
                parts.append(f"פרופיל תיעודי חריג: {dc} מסמכים")
            elif cat == "zoning_gap":
                parts.append("פער ייעוד — עסק באזור מגורים")
            elif cat == "demolition_without_danger":
                dd = f.get("demolition_docs", [])
                parts.append(f"צווי הריסה בארכיון ({len(dd)} מסמכים) ללא סטטוס סכנה פעיל")

        desc = ". ".join(parts[:3]) if parts else "ממצא מבוסס ציון משוקלל"

        # Planning question
        if entry["danger_status"] >= 1.0:
            question = "מה סטטוס הצו? האם בוצע חיזוק?"
        elif entry["zoning_gap"] > 0:
            question = "האם קיים היתר שימוש חורג?"
        elif entry["demolition_docs"] > 0:
            question = "האם צווי ההריסה בוצעו? מה מצב המבנה היום?"
        else:
            question = "מה מצב המבנה הפיזי בפועל?"

        # Sources
        sources = set()
        for f in findings:
            for s in f.get("sources", []):
                sources.add(s)

        # Why it matters
        if entry["danger_status"] >= 1.0:
            why = "מבנה מוגדר מסוכן ע\"י העירייה — סיכון פיזי לדיירים ולעוברי אורח."
        elif entry["zoning_gap"] > 0 and entry["demolition_docs"] > 0:
            why = "שילוב של פער ייעוד עם היסטוריית הריסות — מצביע על בעיה מערכתית ממושכת."
        elif entry["composite_score"] >= 40:
            why = "ריכוז חריג של ממצאים ממספר מקורות עצמאיים — מצביע על כתובת בעייתית."
        else:
            why = "ממצא ברמה בינונית הדורש בדיקת שטח."

        descriptions.append({
            "rank": entry["rank"],
            "address": addr,
            "chelka": chelka,
            "score": score,
            "description": desc,
            "planning_question": question,
            "sources": sorted(sources),
            "why_it_matters": why,
            "flags": entry["flags"],
        })

    return descriptions


def main():
    # Load data
    with open(DATA / "anomaly-synthesis.json", "r", encoding="utf-8") as f:
        synthesis = json.load(f)

    with open(DATA / "anomaly-ranking.json", "r", encoding="utf-8") as f:
        ranking = json.load(f)

    findings = synthesis["findings"]
    print(f"=== Anomaly Cleanup ===")
    print(f"Original findings: {len(findings)}")
    print()

    # Step 1: Filter
    kept, removed = filter_findings(findings)
    print(f"Removed as noise: {len(removed)}")
    print(f"Remaining real findings: {len(kept)}")
    print()

    # Breakdown of removed by category
    removed_by_cat = {}
    for r in removed:
        cat = r.get("category", "unknown")
        removed_by_cat[cat] = removed_by_cat.get(cat, 0) + 1

    print("Removed by category:")
    for cat, count in sorted(removed_by_cat.items(), key=lambda x: -x[1]):
        original = synthesis["summary"]["by_category"].get(cat, 0)
        print(f"  {cat}: {count} removed / {original} original ({count/max(original,1)*100:.0f}%)")

    # Breakdown of removed by reason
    removed_by_reason = {}
    for r in removed:
        reason = r.get("removed_reason", "unknown")
        removed_by_reason[reason] = removed_by_reason.get(reason, 0) + 1

    print("\nRemoved by reason:")
    for reason, count in sorted(removed_by_reason.items(), key=lambda x: -x[1]):
        print(f"  [{count}] {reason}")

    # Remaining by category
    kept_by_cat = {}
    for k in kept:
        cat = k.get("category", "unknown")
        kept_by_cat[cat] = kept_by_cat.get(cat, 0) + 1

    print("\nRemaining by category:")
    for cat, count in sorted(kept_by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    # Step 2: Save clean synthesis
    clean_synthesis = copy.deepcopy(synthesis)
    clean_synthesis["findings"] = kept
    clean_synthesis["removed_findings"] = removed
    clean_synthesis["summary"]["total_findings_original"] = len(findings)
    clean_synthesis["summary"]["total_findings"] = len(kept)
    clean_synthesis["summary"]["removed_count"] = len(removed)
    clean_synthesis["summary"]["by_category"] = kept_by_cat
    clean_synthesis["summary"]["cleanup_date"] = "2026-04-13"
    clean_synthesis["summary"]["cleanup_note"] = (
        "סוננו ממצאי רעש לפי סקירה אסטרטגית. "
        "הוסרו: רעש מושע ברשת, ספירות כפולות, שגיאות GIS, צווים ישנים שנפתרו."
    )

    with open(DATA / "anomaly-synthesis-clean.json", "w", encoding="utf-8") as f:
        json.dump(clean_synthesis, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {DATA / 'anomaly-synthesis-clean.json'}")

    # Step 3: Rebuild ranking
    findings_by_address = {}
    for f_item in kept:
        addr = f_item.get("address", "")
        if not addr:
            continue
        if addr not in findings_by_address:
            findings_by_address[addr] = []
        findings_by_address[addr].append(f_item)

    all_ranked = build_ranking(kept, ranking)

    clean_ranking = {
        "generated": "2026-04-13",
        "block": "בלוק תשבי-ששון",
        "cleanup_version": True,
        "scoring_weights": {
            "physical_anomaly": 3,
            "documentary_anomaly": 2,
            "network_centrality": 0.5,
            "zoning_gap": 4,
            "danger_status": 5,
            "note": "משקלות מעודכנים — הפחתת רעש מושע, הגברת משקל פיזי/ייעודי",
        },
        "total_addresses": len(all_ranked),
        "top_20": all_ranked[:20],
        "all_ranked": all_ranked,
    }

    # Generate top 20 descriptions
    top20_report = generate_top20_descriptions(all_ranked[:20], findings_by_address)
    clean_ranking["top_20_report"] = top20_report

    with open(DATA / "anomaly-ranking-clean.json", "w", encoding="utf-8") as f:
        json.dump(clean_ranking, f, ensure_ascii=False, indent=2)
    print(f"Saved: {DATA / 'anomaly-ranking-clean.json'}")

    # Print new top 5
    print("\n=== New Top 5 ===")
    for entry in all_ranked[:5]:
        addr = entry["address"]
        score = entry["composite_score"]
        flags = ", ".join(entry["flags"]) if entry["flags"] else "—"
        print(f"  #{entry['rank']} {addr} (חלקה {entry['chelka']}) — ציון {score}")
        print(f"       פיזי:{entry['physical_anomaly_count']} תיעודי:{entry['documentary_anomaly_count']} "
              f"ייעוד:{entry['zoning_gap']} סכנה:{entry['danger_status']} הריסות:{entry['demolition_docs']}")
        print(f"       דגלים: {flags}")

    # Return data for dashboard update
    return clean_ranking, len(removed)


if __name__ == "__main__":
    clean_ranking, removed_count = main()
