"""
Update dashboard.html with clean anomaly data.
- Replace Section 1 master table with new scores
- Replace Section 7 top findings with clean top 20
- Add cleanup note at top
"""

import json
import re
from pathlib import Path

BASE = Path("c:/Users/yotam/projects/hatishbi-archive")
DATA = BASE / "data"


def generate_master_table_rows(ranked):
    """Generate HTML rows for the master table."""
    rows = []
    for e in ranked:
        score = e["composite_score"]
        if score > 50:
            row_class = ' class="row-red"'
        elif score >= 30:
            row_class = ' class="row-orange"'
        else:
            row_class = ""

        # Generate flags HTML
        flags_html = ""
        for flag in e.get("flags", []):
            if flag == "מחזור היתרים-סכנה":
                flags_html += '<span class="flag flag-danger">מחזור היתרים-סכנה</span>\n'
            elif flag == "עסק באזור מגורים":
                flags_html += '<span class="flag flag-biz">עסק באזור מגורים</span>\n'
            elif flag == "ריכוז רשת גבוה":
                flags_html += '<span class="flag flag-net">רשת גבוה</span>\n'
            elif flag == "מבנה רפאים":
                flags_html += '<span class="flag flag-ghost">מבנה רפאים</span>\n'

        addr_escaped = e["address"].replace('"', "&quot;")

        row = f"""            <tr{row_class}>
              <td>{e['rank']}</td>
              <td>{addr_escaped}</td>
              <td>{e['chelka']}</td>
              <td>{score}</td>
              <td>{e['physical_anomaly_count']}</td>
              <td>{e['documentary_anomaly_count']}</td>
              <td>{e['network_centrality']}</td>
              <td>{e['zoning_gap']}</td>
              <td>{e['danger_status']}</td>
              <td>{e['demolition_docs']}</td>
              <td>{flags_html.strip()}</td>
            </tr>"""
        rows.append(row)

    return "\n".join(rows)


def generate_top20_section(ranking_data):
    """Generate the top 20 findings HTML for Section 7."""
    top20 = ranking_data["top_20_report"]

    rows = []
    for entry in top20:
        score = entry["score"]
        if score > 50:
            row_class = ' class="row-red"'
        elif score >= 30:
            row_class = ' class="row-orange"'
        else:
            row_class = ""

        flags_html = ""
        for flag in entry.get("flags", []):
            if "עסק" in flag:
                flags_html += f'<span class="flag flag-biz">{flag}</span> '
            elif "סכנה" in flag or "מחזור" in flag:
                flags_html += f'<span class="flag flag-danger">{flag}</span> '
            elif "רשת" in flag:
                flags_html += f'<span class="flag flag-net">{flag}</span> '
            elif "רפאים" in flag:
                flags_html += f'<span class="flag flag-ghost">{flag}</span> '

        sources_str = ", ".join(entry.get("sources", []))

        row = f"""          <tr{row_class}>
            <td>{entry['rank']}</td>
            <td>{entry['address']}</td>
            <td>{entry['chelka']}</td>
            <td>{entry['score']}</td>
            <td>{entry['description']}</td>
            <td>{entry['planning_question']}</td>
            <td style="font-size:10px">{sources_str}</td>
            <td style="font-size:10px">{entry['why_it_matters']}</td>
            <td>{flags_html.strip()}</td>
          </tr>"""
        rows.append(row)

    return "\n".join(rows)


def main():
    # Load ranking
    with open(DATA / "anomaly-ranking-clean.json", "r", encoding="utf-8") as f:
        ranking = json.load(f)

    # Load synthesis for stats
    with open(DATA / "anomaly-synthesis-clean.json", "r", encoding="utf-8") as f:
        synthesis = json.load(f)

    removed_count = synthesis["summary"]["removed_count"]
    remaining = synthesis["summary"]["total_findings"]

    # Read dashboard
    with open(BASE / "dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # === 1. Add cleanup note after summary-bar ===
    cleanup_note = f"""      <div class="missing-note" style="background:#d1fae5;border-color:#16a34a;color:#065f46;">
        <strong>גרסה מנוקה — 13/04/2026.</strong>
        סוננו {removed_count} ממצאי רעש מתוך 332 מקוריים.
        נותרו {remaining} ממצאים אמיתיים.
        הוסרו: רעש מושע ברשת, ספירות כפולות של צווים+מסמכים, צווי הריסה ישנים שנפתרו.
        משקלות עודכנו: פיזי ×3, תיעודי ×2, רשת ×0.5, ייעוד ×4, סכנה ×5.
      </div>"""

    # Insert after the summary-bar closing div
    summary_bar_end = '</div>\n      <p style="font-size: 11px; color: #64748b">'
    if summary_bar_end in html:
        html = html.replace(summary_bar_end, '</div>\n' + cleanup_note + '\n      <p style="font-size: 11px; color: #64748b">')

    # === 2. Update summary numbers ===
    # Update "332 ממצאים" to new count
    html = html.replace(
        '<div class="num">332</div>\n          <div class="lbl">ממצאים</div>',
        f'<div class="num">{remaining}</div>\n          <div class="lbl">ממצאים (מנוקה)</div>'
    )

    # === 3. Replace Section 1 master table ===
    # Generate new master table rows
    master_rows = generate_master_table_rows(ranking["all_ranked"])

    # Replace master table header to include demolition column
    old_header = """            <tr>
              <th>#</th>
              <th>כתובת</th>
              <th>חלקה</th>
              <th>ציון אנומליה</th>
              <th>אנומליות פיזיות</th>
              <th>אנומליות תיעודיות</th>
              <th>מרכזיות רשת</th>
              <th>פער ייעוד</th>
              <th>סטטוס סכנה</th>
              <th>דגלים</th>
            </tr>"""

    new_header = """            <tr>
              <th>#</th>
              <th>כתובת</th>
              <th>חלקה</th>
              <th>ציון (מנוקה)</th>
              <th>פיזי</th>
              <th>תיעודי</th>
              <th>רשת</th>
              <th>ייעוד</th>
              <th>סכנה</th>
              <th>הריסות</th>
              <th>דגלים</th>
            </tr>"""

    html = html.replace(old_header, new_header)

    # Find and replace the tbody content of section 1
    # The master table starts after the header and ends at </tbody></table>
    # We need to find the specific tbody
    sec1_start = html.find('<section id="sec1">')
    sec1_end = html.find('</section>', sec1_start)
    sec1_html = html[sec1_start:sec1_end]

    # Find tbody in section 1
    tbody_start_rel = sec1_html.find('<tbody>')
    tbody_end_rel = sec1_html.find('</tbody>')

    if tbody_start_rel >= 0 and tbody_end_rel >= 0:
        abs_tbody_start = sec1_start + tbody_start_rel + len('<tbody>')
        abs_tbody_end = sec1_start + tbody_end_rel
        html = html[:abs_tbody_start] + '\n' + master_rows + '\n          ' + html[abs_tbody_end:]

    # Update section 1 description
    html = html.replace(
        'ממוין לפי ציון אנומליה (גבוה ראשון). צבע שורה:',
        'ממוין לפי ציון מנוקה (גבוה ראשון). משקלות: פיזי ×3, תיעודי ×2, רשת ×0.5, ייעוד ×4, סכנה ×5. צבע שורה:'
    )
    html = html.replace('ציון &gt;50', 'ציון &gt;50 (מנוקה)')

    # === 4. Replace Section 7 top findings ===
    # Find section 7 and add the clean top 20 table after the header
    sec7_marker = '<section id="sec7">'
    sec7_start = html.find(sec7_marker)

    if sec7_start >= 0:
        sec7_end = html.find('</section>', sec7_start)

        # Build new section 7
        top20_rows = generate_top20_section(ranking)

        new_sec7 = f"""{sec7_marker}
      <h2>7. ממצאים מובילים (מנוקה)</h2>

      <div class="missing-note" style="background:#eff6ff;border-color:#93c5fd;color:#1e40af;">
        <strong>טבלה זו מבוססת על נתונים מנוקים.</strong>
        הוסרו {removed_count} ממצאי רעש (רעש מושע, ספירות כפולות, שגיאות GIS, צווים ישנים).
        משקלות חדשים: פיזי ×3 | תיעודי ×2 | רשת ×0.5 | ייעוד ×4 | סכנה ×5
      </div>

      <h3>20 כתובות מובילות — דירוג מנוקה</h3>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>כתובת</th>
            <th>חלקה</th>
            <th>ציון</th>
            <th>תיאור</th>
            <th>שאלה תכנונית</th>
            <th>מקורות</th>
            <th>למה זה חשוב</th>
            <th>דגלים</th>
          </tr>
        </thead>
        <tbody>
{top20_rows}
        </tbody>
      </table>

      <h3>מבנים מסוכנים — GIS פעיל</h3>"""

        # Find where the dangerous buildings section starts in old sec7
        dangerous_start = html.find('<h3>מבנים מסוכנים — GIS פעיל</h3>', sec7_start)
        if dangerous_start >= 0:
            # Keep everything from dangerous buildings onwards until end of section
            remaining_sec7 = html[dangerous_start + len('<h3>מבנים מסוכנים — GIS פעיל</h3>'):sec7_end]
            html = html[:sec7_start] + new_sec7 + remaining_sec7 + "\n    </section>"
            # Fix the rest after section 7
            html = html[:html.find('</section>', sec7_start) + len('</section>')] + html[sec7_end + len('</section>'):]

    # === 5. Update Section 8 summary stats ===
    old_stats_note = "סה\"כ ממצאים: 332"
    if old_stats_note in html:
        html = html.replace(old_stats_note, f"סה\"כ ממצאים: {remaining} (מנוקה, מתוך 332 מקוריים)")

    # Write updated dashboard
    with open(BASE / "dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard updated: {BASE / 'dashboard.html'}")
    print(f"  - Added cleanup note")
    print(f"  - Updated summary: 332 -> {remaining}")
    print(f"  - Replaced master table with {len(ranking['all_ranked'])} rows")
    print(f"  - Replaced Section 7 top findings with clean top 20")


if __name__ == "__main__":
    main()
