import json
import os

def build_prerender():
    json_path = "dashboard_data.json"
    with open(json_path, "r", encoding="utf-8") as f:
        d = json.load(f)

    tasks = d.get("tasks", [])
    emp_map = d.get("employeeMap", {})

    def get_realloc_candidates(high_risk_task):
        today_ms = 1723872000000
        assigned_to = high_risk_task.get("assigned_to")
        candidates = []
        for name, emp in emp_map.items():
            if assigned_to and name == assigned_to:
                continue
            headroom = emp["capacity"] - emp["openHours"]
            if headroom <= 0:
                continue
            qualifies = (emp["closedHours"] > 0) or emp.get("hasMediumOpenTask", False)
            if not qualifies:
                continue
            days_ago = None
            if emp.get("lastClosedMs", 0) > 0:
                days_ago = round((today_ms - emp["lastClosedMs"]) / 86400000)
                if days_ago < 0:
                    days_ago = 2
            rank_score = headroom
            if days_ago is not None:
                if days_ago <= 7:
                    rank_score += 10
                elif days_ago <= 14:
                    rank_score += 5
            candidates.append({
                "name": name,
                "capacity": emp["capacity"],
                "openHours": round(emp["openHours"]),
                "headroom": round(headroom),
                "lastClosedDateStr": emp.get("lastClosedDateStr"),
                "daysAgoLastClosed": days_ago if days_ago is not None else 2,
                "hasMediumOpenTask": emp.get("hasMediumOpenTask", False),
                "rankScore": rank_score
            })
        candidates.sort(key=lambda x: x["rankScore"], reverse=True)
        return candidates

    def build_realloc_html(candidates, max_show=3):
        if not candidates:
            return ""
        show = candidates[:max_show]
        rows = []
        for idx, c in enumerate(show):
            pct = min(round((c["openHours"] / c["capacity"]) * 100), 100)
            bar_color = "#dc2626" if pct >= 80 else ("#d97706" if pct >= 55 else "#16a34a")
            closed_label = f"last task closed <strong>{c['daysAgoLastClosed']}d ago</strong>" if c["daysAgoLastClosed"] is not None else "<em>medium-risk task winding down</em>"
            rows.append(f"""<div style="display:flex; align-items:center; gap:10px; padding:7px 10px; border-radius:8px; background:rgba(255,255,255,0.07); margin-bottom:5px;">
  <span style="font-size:11px; font-weight:800; color:#94a3b8; min-width:18px;">#{idx+1}</span>
  <div style="flex:1; min-width:0;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
      <span style="font-size:12px; font-weight:700; color:var(--text-main); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{c['name']}</span>
      <span style="font-size:11px; font-family:'JetBrains Mono',monospace; font-weight:700; color:{'#dc2626' if pct >= 80 else '#16a34a'}; white-space:nowrap; margin-left:8px;">{c['openHours']}/{c['capacity']}h</span>
    </div>
    <div style="display:flex; align-items:center; gap:6px;">
      <div style="flex:1; height:4px; background:var(--border-light); border-radius:2px; overflow:hidden;">
        <div style="width:{pct}%; height:100%; background:{bar_color}; border-radius:2px;"></div>
      </div>
      <span style="font-size:10px; color:var(--text-subtle);">{closed_label}</span>
    </div>
  </div>
  <span style="font-size:10px; font-weight:700; background:#dcfce7; color:#16a34a; padding:2px 7px; border-radius:99px; white-space:nowrap;">+{c['headroom']}h free</span>
</div>""")
        more_label = f'<div style="font-size:11px; color:var(--text-subtle); text-align:right; margin-top:2px;">{len(candidates) - max_show} more candidate(s) available</div>' if len(candidates) > max_show else ""
        return f"""<div style="margin-top:10px; border-top:1px solid var(--border-light); padding-top:8px;">
  <div style="font-size:11px; font-weight:700; color:var(--text-subtle); letter-spacing:0.04em; margin-bottom:6px;">SUGGESTED REALLOCATION — RANKED BY AVAILABILITY</div>
  {''.join(rows)}
  {more_label}
</div>"""

    # 1. Disc Stats
    disc_html = ""
    for disc, stats in d.get("disc_stats", {}).items():
        rate = stats.get("rate", 0)
        delayed = stats.get("delayed", 0)
        total = stats.get("total", 0)
        color = "danger" if rate > 40 else "warning"
        disc_html += f"""<div class="stat-row">
  <div class="stat-meta">
    <span class="stat-name">{disc}</span>
    <span class="stat-val">{delayed} / {total} Delayed ({rate:.1f}%)</span>
  </div>
  <div class="bar-bg">
    <div class="bar-fill {color}" style="width: {min(rate, 100)}%;"></div>
  </div>
</div>"""

    # 2. Root Causes
    cause_html = ""
    root_causes = d.get("root_causes", {})
    max_cause = max(root_causes.values()) if root_causes else 1
    for cause, count in root_causes.items():
        pct = round((count / max_cause) * 100)
        cause_html += f"""<div class="stat-row">
  <div class="stat-meta">
    <span class="stat-name">{cause}</span>
    <span class="stat-val">{count} Incident(s)</span>
  </div>
  <div class="bar-bg">
    <div class="bar-fill" style="width: {pct}%;"></div>
  </div>
</div>"""

    # 3. Models Leaderboard
    models_html = ""
    cv_acc = d.get("meta", {}).get("cv_accuracy", {})
    champion_name = d.get("meta", {}).get("champion", "Random Forest")
    for model_name, m in cv_acc.items():
        is_champ = (model_name == champion_name)
        mean_val = m.get("mean", m.get("acc", 0))
        prec_val = m.get("precision", 0)
        rec_val = m.get("recall", 0)
        f1_val = m.get("f1", 0)
        auc_val = m.get("auc", m.get("auc_roc", 0))
        mcc_val = m.get("mcc", 0)
        champ_pill = '<span class="pill pill-low" style="margin-left:4px; font-size:10px;">CHAMPION</span>' if is_champ else ''
        models_html += f"""<tr>
  <td><strong>{model_name}</strong> {champ_pill}</td>
  <td>{mean_val:.1f}%</td>
  <td>{prec_val:.1f}%</td>
  <td>{rec_val:.1f}%</td>
  <td>{f1_val:.1f}%</td>
  <td>{auc_val:.1f}%</td>
  <td>{mcc_val:.1f}</td>
</tr>"""

    # 4. Feature Importance
    feat_html = ""
    feat_imp = d.get("feat_importance", {})
    sorted_feat = sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)
    max_feat = sorted_feat[0][1] if sorted_feat else 1
    for feat, val in sorted_feat:
        if val <= 0:
            continue
        pct = round((val / max_feat) * 100)
        feat_html += f"""<div class="stat-row">
  <div class="stat-meta">
    <span class="stat-name">{feat}</span>
    <span class="stat-val">{val:.2f}% Impact</span>
  </div>
  <div class="bar-bg">
    <div class="bar-fill" style="width: {pct}%;"></div>
  </div>
</div>"""

    # 5. Task Table (Top 50) using openDrawerById
    tasks_html = ""
    for t in tasks[:50]:
        cat = t.get("cat", "LOW")
        score = float(t.get("score", 0))
        risk_pill = "pill-high" if cat == "HIGH" else ("pill-med" if cat == "MEDIUM" else "pill-low")
        score_color = "danger" if score > 60 else ("warning" if score > 35 else "")
        status_pill = "pill-closed" if t.get("status") == "Closed" else risk_pill
        hours_str = f"{round(t.get('hours', 0))}h" if t.get('hours') else "-"
        tasks_html += f"""<tr onclick="openDrawerById('{t['id']}')">
  <td><span class="task-id-code">{t['id']}</span></td>
  <td style="font-weight:600;">{t['desc']}</td>
  <td>{t['disc']}</td>
  <td>{t.get('location', 'Site')}</td>
  <td><span class="pill {status_pill}">{t.get('status', 'Open')}</span></td>
  <td>{t.get('priority', 'Medium')}</td>
  <td>{hours_str}</td>
  <td>
    <div style="display:flex; align-items:center; gap:8px;">
      <div class="bar-bg" style="width:60px;">
        <div class="bar-fill {score_color}" style="width:{min(score, 100)}%;"></div>
      </div>
      <span style="font-family:'JetBrains Mono', monospace; font-weight:600;">{score:.0f}%</span>
    </div>
  </td>
  <td style="color:var(--text-subtle);">{t.get('root_cause') or 'Pre-execution'}</td>
  <td><button class="btn btn-outline" style="padding:2px 8px; font-size:11px;">Inspect</button></td>
</tr>"""

    # 6. High Risk Alert Cards (Top 3)
    high_risk_tasks = [t for t in tasks if t.get("cat") == "HIGH" and t.get("status") == "Open"][:3]
    high_alerts_html = ""
    for t in high_risk_tasks:
        cands = get_realloc_candidates(t)
        realloc_html = build_realloc_html(cands, 3)
        score = float(t.get("score", 0))
        high_alerts_html += f"""<div class="mit-card high">
  <div class="mit-card-header">
    <div>
      <span class="pill pill-high">{t['disc']}</span>
      <div class="mit-card-title" style="margin-top:4px;">{t['id']}: {t['desc']}</div>
    </div>
    <span style="font-family:'Plus Jakarta Sans', sans-serif; font-size:18px; font-weight:800; color:var(--high-text);">{score:.0f}%</span>
  </div>
  <div class="mit-action-box" style="padding-bottom:{'6px' if realloc_html else ''}">
    <span style="font-weight:700;">ACTION: NOTIFY PM + REALLOCATE RESOURCE</span>
    {realloc_html}
  </div>
  <button class="btn btn-outline" style="width:100%; justify-content:center;" onclick="openDrawerById('{t['id']}')">Inspect Task & Plan &rarr;</button>
</div>"""

    # 7. Mitigation Hub High / Med
    mit_high_html = ""
    open_high = [t for t in tasks if t.get("cat") == "HIGH" and t.get("status") == "Open"][:6]
    for t in open_high:
        cands = get_realloc_candidates(t)
        realloc_html = build_realloc_html(cands, 3)
        score = float(t.get("score", 0))
        assigned = t.get("assigned_to", "Unassigned")
        mit_high_html += f"""<div class="mit-card high" style="margin-bottom:10px;">
  <div class="mit-card-header">
    <div style="display:flex; flex-direction:column; gap:2px;">
      <div><span class="task-id-code">{t['id']}</span> — <strong>{t['desc']}</strong></div>
      <span style="font-size:11px; color:var(--text-subtle);">Assigned: <strong style="color:var(--text-main);">{assigned}</strong></span>
    </div>
    <span class="pill pill-high">{score:.0f}% Risk</span>
  </div>
  <div class="mit-action-box">
    <div style="font-weight:700; margin-bottom:{'2px' if realloc_html else '0'};">PM Alert Issued</div>
    {realloc_html}
  </div>
</div>"""

    mit_med_html = ""
    open_med = [t for t in tasks if t.get("cat") == "MEDIUM" and t.get("status") == "Open"][:6]
    for t in open_med:
        score = float(t.get("score", 0))
        assigned = t.get("assigned_to", "Unassigned")
        mit_med_html += f"""<div class="mit-card med" style="margin-bottom:10px;">
  <div class="mit-card-header">
    <div style="display:flex; flex-direction:column; gap:2px;">
      <div><span class="task-id-code">{t['id']}</span> — <strong>{t['desc']}</strong></div>
      <span style="font-size:11px; color:var(--text-subtle);">Assigned: <strong style="color:var(--text-main);">{assigned}</strong></span>
    </div>
    <span class="pill pill-med">{score:.0f}% Risk</span>
  </div>
  <div class="mit-action-box">Weekly Sync • Verify Sub-contractor Deliverables</div>
</div>"""

    return {
        "disc_html": disc_html,
        "cause_html": cause_html,
        "models_html": models_html,
        "feat_html": feat_html,
        "tasks_html": tasks_html,
        "high_alerts_html": high_alerts_html,
        "mit_high_html": mit_high_html,
        "mit_med_html": mit_med_html
    }

if __name__ == "__main__":
    res = build_prerender()
    print(f"Task HTML length: {len(res['tasks_html'])}, Models HTML length: {len(res['models_html'])}")
