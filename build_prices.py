"""
J Secretary price data: shrinks KPDN PriceCatcher (open data, data.gov.my, CC BY 4.0) into small files that
Josephine can read quickly. Runs daily on GitHub Actions; standard library only (pyarrow is only a fallback).

Output (folder "out"):
  meta.json            {"updated": "YYYY-MM-DD", "items": N, "premises": N, "rows": N}
  items.json           [[item_code, item, unit, item_group, item_category], ...]
  premises.json        {"premise_code": [premise, address, premise_type, state, district], ...}
  item/<code>.json     [[premise_code, price, "YYYY-MM-DD"], ...]  latest price per shop, last KEEP_DAYS days
"""
import csv, datetime, io, json, os, sys, urllib.request

BASE = os.environ.get('PRICECATCHER_BASE', 'https://storage.data.gov.my/pricecatcher/')
KEEP_DAYS = int(os.environ.get('KEEP_DAYS', '14'))
OUT = os.environ.get('OUT_DIR', 'out')
TODAY = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)  # Malaysia time


def rows(name):
    """Rows of a PriceCatcher table as dicts: CSV first, parquet (needs pyarrow) if the CSV isn't there."""
    try:
        with urllib.request.urlopen(BASE + name + '.csv', timeout=600) as resp:
            with io.TextIOWrapper(resp, encoding='utf-8-sig', newline='') as text:
                yield from csv.DictReader(text)
        return
    except Exception as e:
        print(f'{name}.csv unavailable ({e}), trying parquet', file=sys.stderr)
    import pyarrow.parquet as pq  # noqa: E402 (fallback only)
    with urllib.request.urlopen(BASE + name + '.parquet', timeout=600) as resp:
        data = resp.read()
    yield from pq.read_table(io.BytesIO(data)).to_pylist()


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def main():
    # this month, plus last month early in the month so there are always ~2 weeks of prices
    months = [TODAY.strftime('%Y-%m')]
    if TODAY.day <= KEEP_DAYS + 1:
        months.insert(0, (TODAY.replace(day=1) - datetime.timedelta(days=1)).strftime('%Y-%m'))
    latest = {}  # (item, premise) -> (date, price)
    newest = ''
    count = 0
    for m in months:
        try:
            for r in rows('pricecatcher_' + m):
                item, prem = num(r.get('item_code')), num(r.get('premise_code'))
                d = str(r.get('date') or '')[:10]
                try:
                    price = round(float(r.get('price')), 2)
                except (TypeError, ValueError):
                    continue
                if item is None or prem is None or item < 0 or prem < 0 or price <= 0 or len(d) != 10:
                    continue
                count += 1
                k = (item, prem)
                if k not in latest or d > latest[k][0]:
                    latest[k] = (d, price)
                if d > newest:
                    newest = d
        except Exception as e:
            print(f'month {m} failed: {e}', file=sys.stderr)
    if not latest:
        sys.exit('No PriceCatcher prices could be read; keeping the previous data.')
    cutoff = (datetime.date.fromisoformat(newest) - datetime.timedelta(days=KEEP_DAYS)).isoformat()

    items = {}
    for r in rows('lookup_item'):
        c = num(r.get('item_code'))
        if c is not None and c >= 0 and r.get('item'):
            items[c] = [c, str(r.get('item')).strip(), str(r.get('unit') or '').strip(),
                        str(r.get('item_group') or '').strip(), str(r.get('item_category') or '').strip()]
    premises = {}
    for r in rows('lookup_premise'):
        c = num(r.get('premise_code'))
        if c is not None and c >= 0 and r.get('premise'):
            premises[c] = [str(r.get('premise')).strip(), str(r.get('address') or '').strip(),
                           str(r.get('premise_type') or '').strip(), str(r.get('state') or '').strip(),
                           str(r.get('district') or '').strip()]

    per_item, used = {}, set()
    for (item, prem), (d, price) in latest.items():
        if d < cutoff or item not in items or prem not in premises:
            continue
        per_item.setdefault(item, []).append([prem, price, d])
        used.add(prem)

    os.makedirs(os.path.join(OUT, 'item'), exist_ok=True)
    def dump(path, obj):
        with open(os.path.join(OUT, path), 'w', encoding='utf-8') as f:
            f.write(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
    for item, lst in per_item.items():
        lst.sort(key=lambda x: x[1])
        dump(f'item/{item}.json', lst)
    dump('items.json', sorted((items[c] for c in per_item), key=lambda x: x[0]))
    dump('premises.json', {str(c): premises[c] for c in sorted(used)})
    dump('meta.json', {'updated': newest, 'items': len(per_item), 'premises': len(used), 'rows': count,
                       'source': 'KPDN PriceCatcher via data.gov.my (CC BY 4.0)'})
    with open(os.path.join(OUT, 'updated.txt'), 'w') as f:
        f.write(newest)
    print(f'Prices up to {newest}: {len(per_item)} items at {len(used)} shops ({count} rows read).')


if __name__ == '__main__':
    main()
