#!/usr/bin/env python3
"""Filter a public ICS feed; preserve source event timing, UIDs and timezone definitions."""
import collections
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 15 * 1024 * 1024
RULES = {
    'inflation': (r'macro_release_(?:cpi|ppi|pce)(?:_.*)?', r'\b(?:CPI|PPI|PCE|consumer price index|producer price index|personal consumption expenditures|personal income (?:&|and) outlays)\b'),
    'employment': (r'macro_release_(?:employment_situation|nonfarm_payrolls|unemployment_rate)', r'\b(?:non[- ]?farm payrolls?|NFP|employment situation|unemployment rate|jobs report)\b'),
    'gdp_retail': (r'macro_release_(?:gdp|retail_sales)(?:_.*)?', r'\b(?:GDP|gross domestic product|retail sales)\b'),
    'ism_pmi': (r'(?:ism_.*pmi|macro_release_(?:ism|pmi).*)', r'\b(?:ISM|PMI|purchasing managers.? index)\b'),
    'treasury_auction': (r'treasury_auction', r'\b(?:US )?treasury\s+auctions?\b'),
    'jobless_claims': (r'macro_release_jobless_claims', r'\b(?:jobless claims|unemployment claims|initial claims|continuing claims)\b'),
    'consumer_confidence': (r'(?:macro_release_)?consumer_confidence', r'\b(?:consumer confidence|CB consumer confidence)\b'),
    'options_expiration': (r'(?:monthly_opex|quarterly_opex|quad_witching|triple_witching|options_expiration|vix_expiration|vix_settlement)', r'\b(?:OPEX|options? expir(?:ation|y|ies|ations|es)|(?:quad(?:ruple)?|triple) witching|VIX (?:settlement|expir(?:ation|y)))\b'),
}
BLOCK_CATEGORY = re.compile(r'^(?:fomc(?:_|$)|fed_(?:speech|chair|minutes|meeting)|market_(?:holiday|early_close)|futures_(?:liquidity_roll|official_roll|expiration))', re.I)
BLOCK_TITLE = re.compile(r'\b(?:FOMC|Federal Reserve (?:Chair|Governor|Speech|Minutes|Interest Rate|Rate Decision)|Fed (?:Speech|Speeches|Chair|Governor|Testimony|Discussion|Minutes|Rate Decision|Press Conference)|Beige Book|Market (?:Closed|Closure|Holiday|Closes Early)|Early Clos(?:e|ing)|(?:Futures|Contract) (?:Liquidity )?Roll|CME Official Roll Date)\b', re.I)

def split_ics(text):
    """Keep folded physical lines intact; identify top-level components safely."""
    physical = text.lstrip('\ufeff').splitlines()
    logical = []
    for line in physical:
        if line.startswith((' ', '\t')) and logical:
            logical[-1].append(line)
        elif line:
            logical.append([line])
    if not logical or logical[0][0].upper() != 'BEGIN:VCALENDAR' or logical[-1][0].upper() != 'END:VCALENDAR':
        raise ValueError('Source is not a complete VCALENDAR')
    props, components, stack, buf = [], [], [], []
    for group in logical[1:-1]:
        line = unfold(group)
        upper = line.upper()
        if upper.startswith('BEGIN:'):
            stack.append(upper[6:]); buf.append(group)
        elif stack:
            buf.append(group)
            if upper.startswith('END:'):
                if stack.pop() != upper[4:]:
                    raise ValueError('Mismatched ICS component')
                if not stack:
                    components.append((unfold(buf[0])[6:].upper(), buf)); buf = []
        elif upper.startswith('END:'):
            raise ValueError('Unexpected END component')
        else:
            props.append(group)
    if stack:
        raise ValueError('Unclosed ICS component')
    return props, components

def unfold(group):
    return group[0] + ''.join(x[1:] for x in group[1:])

def property_pair(group):
    key, sep, value = unfold(group).partition(':')
    return key.split(';', 1)[0].upper(), value if sep else ''

def event_props(groups):
    result = collections.defaultdict(list)
    depth = 0
    for group in groups:
        key, value = property_pair(group)
        if key == 'BEGIN': depth += 1
        elif key == 'END': depth -= 1
        elif depth == 1: result[key].append(value)
    return result

def classify(title, categories):
    cats = [c.strip().lower() for v in categories for c in v.split(',')]
    # Deny first, even if another category or title would match.
    if any(BLOCK_CATEGORY.search(c) for c in cats) or BLOCK_TITLE.search(title):
        return None
    if re.search(r'\b(?:state|county|metro(?:politan)? area|regional)\b', title, re.I):
        return None  # national macro data only
    for name, (category, title_pattern) in RULES.items():
        if any(re.fullmatch(category, c, re.I) for c in cats):
            return name
    for name, (_, title_pattern) in RULES.items():
        if re.search(title_pattern, title, re.I):
            return name
    return None

def ics_text(value):
    return value.replace('\\', '\\\\').replace('\r','').replace('\n','\\n').replace(';','\\;').replace(',','\\,')

def fold(line):
    lines, part = [], ''
    for ch in line:
        if len((part + ch).encode('utf-8')) > 75:
            lines.append(part); part = ' ' + ch
        else:
            part += ch
    lines.append(part)
    return lines

def filter_ics(text, cfg):
    props, components = split_ics(text)
    if not any(property_pair(g) == ('VERSION', '2.0') for g in props):
        raise ValueError('ICS version 2.0 required')
    selected, counts, skipped = [], collections.Counter(), collections.Counter()
    total = 0
    for kind, groups in components:
        if kind == 'VTIMEZONE':
            selected.append(groups); continue
        if kind != 'VEVENT': continue
        total += 1
        event = event_props(groups)
        title = (event['SUMMARY'] or [''])[0]
        category = classify(title, event['CATEGORIES'])
        if not category or not cfg['keep'].get(category, False):
            skipped[title] += 1; continue
        if not event['UID'] or not event['DTSTART'] or not event['DTSTAMP']:
            raise ValueError('Selected event missing UID, DTSTART or DTSTAMP: ' + title)
        counts[category] += 1
        selected.append(groups)
    if not total or not sum(counts.values()):
        raise ValueError('No matching events; refusing to replace the previous calendar')
    # Keep source metadata (including timezone) but replace the display name and description.
    header = [g for g in props if property_pair(g)[0] not in {'X-WR-CALNAME','X-WR-CALDESC','NAME','DESCRIPTION','X-WR-RELCALID'}]
    header.append(fold('X-WR-CALNAME:' + ics_text(cfg['calendar_name'])))
    header.append(fold('X-WR-CALDESC:' + ics_text('Filtered US economic and options events. Source: ' + cfg['source_url'] + '. Verify release times with official sources.')))
    lines = ['BEGIN:VCALENDAR']
    for g in header: lines.extend(g)
    for component in selected:
        for g in component: lines.extend(g)
    lines.append('END:VCALENDAR')
    return ('\r\n'.join(lines) + '\r\n').encode('utf-8'), total, counts, skipped

def main():
    cfg = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    url = cfg['source_url']
    if urlparse(url).scheme != 'https': raise ValueError('Public HTTPS ICS URL required')
    request = Request(url, headers={'User-Agent':'EconomicCalendarFilter/1.0','Accept':'text/calendar, */*'})
    with urlopen(request, timeout=45) as response:
        raw = response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES: raise ValueError('Source exceeded maximum download size')
    data,total,counts,skipped = filter_ics(raw.decode('utf-8-sig'),cfg)
    for name in RULES:
        print(f'{name}: {counts[name]}' + (' (not present in source)' if cfg['keep'].get(name) and not counts[name] else ''))
    print(f'Source: {total}; kept: {sum(counts.values())}; excluded: {sum(skipped.values())}')
    path=ROOT/cfg['output']
    if path.exists() and path.read_bytes()==data:
        print('No calendar changes.'); return
    tmp=path.with_suffix('.tmp'); tmp.write_bytes(data); tmp.replace(path)
    print('Published file:',path.name)

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(f'ERROR: {exc}',file=sys.stderr); sys.exit(1)
