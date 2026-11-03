#!/usr/bin/env python3
"""Fill assets/template.html with the muscle model, the week's data and the targets.

Usage:
  python3 scripts/build_page.py --week week.json --targets targets.json --body female --out page.html
  python3 scripts/build_page.py --week week.json --month month.json --body female --out page.html

week.json    {"label": "...", "days": [{"date","kcal","sets","minutes","sets_by_muscle":{key: sets}}]}
month.json   {"label": "...", "weeks": [week, ...]}   optional, adds the "This month" view
targets.json {key: [min, target, max, note]}   (defaults: references/default-targets.json)
--body       female or male: uses assets/muscles-<body>.bin, made once by scripts/build_model.py
"""
import argparse
import base64
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', required=True)
    ap.add_argument('--month')
    ap.add_argument('--targets', default=os.path.join(ROOT, 'references', 'default-targets.json'))
    ap.add_argument('--body', choices=['female', 'male'], required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    week = json.load(open(a.week))
    if not week.get('days'):
        raise SystemExit('week.json needs at least one day')
    targets = json.load(open(a.targets))
    for k, v in targets.items():
        if len(v) != 4 or not (v[0] <= v[1] <= v[2]):
            raise SystemExit('bad target for %s: expected [min, target, max, note]' % k)
    month = json.load(open(a.month)) if a.month else None
    if month is not None and not month.get('weeks'):
        raise SystemExit('month.json needs at least one week')
    days = week['days'] + ([d for w in month['weeks'] for d in w['days']] if month else [])
    for d in days:
        for k in d['sets_by_muscle']:
            if k not in targets:
                raise SystemExit('unknown muscle key: %s' % k)

    model_path = os.path.join(ROOT, 'assets', 'muscles-%s.bin' % a.body)
    if not os.path.exists(model_path):
        raise SystemExit('missing %s: run python3 scripts/build_model.py --body %s --download' % (model_path, a.body))

    html = open(os.path.join(ROOT, 'assets', 'template.html')).read()
    model = base64.b64encode(open(model_path, 'rb').read()).decode()
    html = html.replace('__MODEL_B64__', model)
    html = html.replace('__WEEK_JSON__', json.dumps(week))
    html = html.replace('__MONTH_JSON__', json.dumps(month))
    html = html.replace('__TARGETS_JSON__', json.dumps(targets))
    open(a.out, 'w').write(html)
    print('wrote', a.out, len(html), 'bytes')


if __name__ == '__main__':
    main()
