import json
from reports.dashboard_builder import build_dashboard
def load_json_safe(path):
    try:
        with open(path) as f: return json.load(f)
    except:
        return {}

rank = load_json_safe('docs/assets/data/rank.json')
rep = load_json_safe('docs/assets/data/reports.json')
news = load_json_safe('docs/assets/data/news.json')
arch = load_json_safe('docs/assets/data/weekly_archive.json')

build_dashboard(rank, rep.get('reports', []), news, {}, arch, "NORMAL")
print("Render successful.")
