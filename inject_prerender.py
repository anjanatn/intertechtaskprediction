import os
from build_full_prerender import build_prerender

pr = build_prerender()

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update task-table-body
html = html.replace(
    '<tbody id="task-table-body">\n <!-- Rendered by JS -->\n </tbody>',
    f'<tbody id="task-table-body">{pr["tasks_html"]}</tbody>'
)

# 2. Update models-table-body
html = html.replace(
    '<tbody id="models-table-body">\n <!-- JS -->\n </tbody>',
    f'<tbody id="models-table-body">{pr["models_html"]}</tbody>'
)

# 3. Update ai-models-table-body
html = html.replace(
    '<tbody id="ai-models-table-body">\n <!-- JS -->\n </tbody>',
    f'<tbody id="ai-models-table-body">{pr["models_html"]}</tbody>'
)

# 4. Update disc-bar-container
html = html.replace(
    '<div class="stat-list" id="disc-bar-container">\n <!-- Rendered by JS -->\n </div>',
    f'<div class="stat-list" id="disc-bar-container">{pr["disc_html"]}</div>'
)

# 5. Update cause-list-container
html = html.replace(
    '<div class="stat-list" id="cause-list-container">\n <!-- Rendered by JS -->\n </div>',
    f'<div class="stat-list" id="cause-list-container">{pr["cause_html"]}</div>'
)

# 6. Update feat-list-container
html = html.replace(
    '<div class="stat-list" id="feat-list-container">\n <!-- JS -->\n </div>',
    f'<div class="stat-list" id="feat-list-container">{pr["feat_html"]}</div>'
)

# 7. Update ai-feat-list-container
html = html.replace(
    '<div id="ai-feat-list-container" style="font-size: 11px;">\n <!-- JS -->\n </div>',
    f'<div id="ai-feat-list-container" style="font-size: 11px;">{pr["feat_html"]}</div>'
)

# 8. Update high-risk-alerts-container
html = html.replace(
    '<div class="mit-grid" id="high-risk-alerts-container">\n <!-- Rendered by JS -->\n </div>',
    f'<div class="mit-grid" id="high-risk-alerts-container">{pr["high_alerts_html"]}</div>'
)

# 9. Update mit-list-high and mit-list-med
html = html.replace(
    '<div class="mit-grid" id="mit-list-high">\n <!-- JS -->\n </div>',
    f'<div class="mit-grid" id="mit-list-high">{pr["mit_high_html"]}</div>'
)

html = html.replace(
    '<div class="mit-grid" id="mit-list-med">\n <!-- JS -->\n </div>',
    f'<div class="mit-grid" id="mit-list-med">{pr["mit_med_html"]}</div>'
)

# 10. Update static text "Showing 0 of 1000 tasks" -> "Showing 50 of 1000 tasks"
html = html.replace('Showing 0 of 1000 tasks', 'Showing 50 of 1000 tasks')

# 11. Add drawer-assigned element to drawer HTML
drawer_grid_old = """ <div class="detail-grid">
 <div class="detail-item">
 <span class="detail-label">Discipline</span>
 <span class="detail-val" id="drawer-disc">-</span>
 </div>
 <div class="detail-item">
 <span class="detail-label">Location</span>
 <span class="detail-val" id="drawer-loc">-</span>
 </div>
 <div class="detail-item">
 <span class="detail-label">Status</span>
 <span class="detail-val" id="drawer-status">-</span>
 </div>"""

drawer_grid_new = """ <div class="detail-grid">
 <div class="detail-item">
 <span class="detail-label">Discipline</span>
 <span class="detail-val" id="drawer-disc">-</span>
 </div>
 <div class="detail-item">
 <span class="detail-label">Location</span>
 <span class="detail-val" id="drawer-loc">-</span>
 </div>
 <div class="detail-item">
 <span class="detail-label">Assigned Employee</span>
 <span class="detail-val" id="drawer-assigned" style="font-weight:700; color:var(--brand-primary);">-</span>
 </div>
 <div class="detail-item">
 <span class="detail-label">Status</span>
 <span class="detail-val" id="drawer-status">-</span>
 </div>"""

html = html.replace(drawer_grid_old, drawer_grid_new)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Injected pre-rendered HTML into index.html successfully.")
