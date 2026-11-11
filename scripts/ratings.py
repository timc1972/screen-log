#!/usr/bin/env python3
"""Conservative ratings enrichment for ScreenLog.

- Restore the last known good ratings if this is the first cached run.
- Cache ratings across GitHub Actions runs.
- Never erase a cached rating on API failure or quota exhaustion.
- Obtain exact Rotten Tomatoes page identifiers from Wikidata by IMDb ID.
"""
import io
import json
import os
import re
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

CACHE = Path(__file__).resolve().parent / 'ratings-cache.json'
GOOD_ARTIFACT = 'https://api.github.com/repos/timc1972/screen-log/actions/artifacts/13876352870/zip'
FIELDS = ('imdbRating', 'rottenTomatoes', 'rottenTomatoesUrl')
UA = 'ScreenLog/1.0 (https://github.com/timc1972/screen-log)'
TODAY = date.today().isoformat()


def fetch_good_ratings():
    """Recover ratings from the successful Nov 11 deployment artifact, once."""
    token = os.getenv('GH_TOKEN', '').strip()
    if not token:
        print('Ratings recovery: GitHub token missing.')
        return {}
    req = urllib.request.Request(GOOD_ARTIFACT, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'User-Agent': UA,
    })
    try:
        local_archive = Path(__file__).resolve().parent.parent / '.ratings-bootstrap' / 'artifact.tar'
        if local_archive.is_file():
            print('Ratings recovery: using downloaded GitHub Actions artifact.')
            with tarfile.open(local_archive, mode='r:*') as bundle:
                member = next(m for m in bundle.getmembers()
                              if m.name.lstrip('./') == 'data.js' and m.isfile())
                raw = bundle.extractfile(member).read().decode('utf-8')
        else:
            with urllib.request.urlopen(req, timeout=45) as response:
                blob = response.read(45_000_001)
            if len(blob) > 45_000_000:
                raise ValueError('GitHub Pages artifact too large to restore')
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                tar_name = next(n for n in archive.namelist() if n.endswith('artifact.tar'))
                with tarfile.open(fileobj=io.BytesIO(archive.read(tar_name)), mode='r:*') as bundle:
                    member = next(m for m in bundle.getmembers()
                                  if m.name.lstrip('./') == 'data.js' and m.isfile())
                    raw = bundle.extractfile(member).read().decode('utf-8')
        prefix = 'window.SCREENLOG_DATA = '
        if not raw.startswith(prefix):
            raise ValueError('Unexpected ScreenLog Pages data format')
        payload = json.loads(raw[len(prefix):].strip().rstrip(';'))
        restored = {}
        for kind in ('movies', 'shows'):
            for item in payload.get(kind, []):
                ident = item.get('id')
                if not re.fullmatch(r'tt\d+', str(ident)):
                    continue
                values = {k: item[k] for k in FIELDS if item.get(k)}
                if values:
                    values['omdbCheckedOn'] = TODAY
                    restored[ident] = values
        print(f'Ratings recovery: restored {len(restored)} titles from successful earlier deployment.')
        return restored
    except (urllib.error.URLError, OSError, ValueError, KeyError, StopIteration, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f'Ratings recovery unavailable: {type(exc).__name__}: {str(exc)[:120]}')
        return {}


def load_cache():
    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                print(f'Ratings cache loaded: {len(data)} titles')
                if not any(isinstance(v, dict) and (v.get('imdbRating') or v.get('rottenTomatoes'))
                           for v in data.values()):
                    restored = fetch_good_ratings()
                    for ident, fields in restored.items():
                        data.setdefault(ident, {}).update(fields)
                return data
        except (OSError, ValueError):
            print('Ratings cache unreadable; attempting recovery.')
    return fetch_good_ratings()


def within_days(value, days):
    if not value:
        return False
    try:
        return (datetime.now(timezone.utc).date() - date.fromisoformat(value)).days < days
    except ValueError:
        return False


def add_omdb(snapshot, cache, key):
    if not key:
        print('OMDb key unavailable; preserving cached ratings.')
        return
    attempted = 0
    for kind in ('movies', 'shows'):
        for item in snapshot[kind]:
            imdb = str(item.get('id') or '')
            if not re.fullmatch(r'tt\d+', imdb):
                continue
            record = cache.setdefault(imdb, {})
            if within_days(record.get('omdbCheckedOn'), 30):
                continue
            if attempted >= 450:
                print('OMDb safe request budget reached; remaining cached scores retained.')
                return
            attempted += 1
            query = urllib.parse.urlencode({'apikey': key, 'i': imdb})
            try:
                request = urllib.request.Request('https://www.omdbapi.com/?' + query,
                                                 headers={'User-Agent': UA})
                with urllib.request.urlopen(request, timeout=15) as response:
                    info = json.loads(response.read(100000))
                if info.get('Response') != 'True':
                    reason = str(info.get('Error') or '')
                    if 'limit' in reason.lower() or 'key' in reason.lower():
                        print('OMDb declined more requests: ' + reason[:80])
                        return
                    record['omdbCheckedOn'] = TODAY
                    continue
                score = str(info.get('imdbRating') or '')
                if re.fullmatch(r'\d+(?:\.\d+)?', score):
                    record['imdbRating'] = score
                for rating in info.get('Ratings', []):
                    if rating.get('Source') == 'Rotten Tomatoes':
                        value = str(rating.get('Value') or '')
                        if re.fullmatch(r'\d{1,3}%', value):
                            record['rottenTomatoes'] = value
                record['omdbCheckedOn'] = TODAY
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 402, 403, 429):
                    print(f'OMDb stopped after HTTP {exc.code}; cached scores remain intact.')
                    return
                print(f'OMDb lookup error for {imdb}: HTTP {exc.code}')
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                print(f'OMDb lookup error for {imdb}: {type(exc).__name__}')
            time.sleep(0.06)
    print(f'OMDb lookup requests this run: {attempted}')


def add_wikidata_links(snapshot, cache):
    """Find direct RT URLs from Wikidata P1258, matched by exact IMDb P345."""
    ids = []
    for kind in ('movies', 'shows'):
        for item in snapshot[kind]:
            imdb = str(item.get('id') or '')
            if not re.fullmatch(r'tt\d+', imdb):
                continue
            record = cache.setdefault(imdb, {})
            if record.get('rottenTomatoesUrl') or within_days(record.get('rtCheckedOn'), 7):
                continue
            ids.append((imdb, kind))
    resolved = 0
    batches = 0
    for offset in range(0, len(ids), 30):
        batch = ids[offset:offset + 30]
        values = ' '.join('"' + imdb + '"' for imdb, _ in batch)
        sparql = ('SELECT ?imdb ?rt WHERE { VALUES ?imdb { ' + values +
                  ' } ?item wdt:P345 ?imdb . ?item wdt:P1258 ?rt . }')
        query = urllib.parse.urlencode({'query': sparql, 'format': 'json'})
        request = urllib.request.Request('https://query.wikidata.org/sparql?' + query,
                                         headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json'})
        matches = {}
        batches += 1
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.loads(response.read(1500000))
            for row in payload.get('results', {}).get('bindings', []):
                imdb = row.get('imdb', {}).get('value', '')
                rt = row.get('rt', {}).get('value', '')
                matches.setdefault(imdb, set()).add(rt)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f'Wikidata link batch unavailable: {type(exc).__name__}')
            # Avoid repeatedly hitting a service when access is restricted.
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (403, 429):
                break
            continue
        for imdb, kind in batch:
            options = [slug for slug in matches.get(imdb, set())
                       if re.fullmatch(r'(?:m|tv)/[a-zA-Z0-9_./-]+', slug)
                       and slug.startswith('m/' if kind == 'movies' else 'tv/')]
            if len(options) == 1:
                cache[imdb]['rottenTomatoesUrl'] = 'https://www.rottentomatoes.com/' + options[0]
                resolved += 1
            cache[imdb]['rtCheckedOn'] = TODAY
        time.sleep(0.35)
    print(f'Wikidata RT links: newly linked={resolved}, batches={batches}')



class RTScorecardParser(HTMLParser):
    """Read only the scorecard JSON from a canonical Rotten Tomatoes page."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.complete = False
        self.fragments = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == 'media-scorecard-json':
            self.inside = True

    def handle_data(self, data):
        if self.inside:
            self.fragments.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.inside:
            self.inside = False
            self.complete = True


def parse_tv_critic_score(page):
    """Return (scorecard_found, score); score=None means no series score.

    Critic score is the RT series-wide Avg. Tomatometer, never the audience
    Popcornmeter or an individual season's score.
    """
    parser = RTScorecardParser()
    parser.feed(page)
    if not parser.complete:
        return False, None
    data = json.loads(''.join(parser.fragments))
    media_type = (data.get('overlay') or {}).get('mediaType')
    if media_type and media_type not in ('TvSeries', 'TVSeries'):
        return True, None
    score = (data.get('criticsScore') or {}).get('score')
    if score is None or score == '':
        return True, None
    value = str(score)
    if not re.fullmatch(r'\d{1,3}', value) or int(value) > 100:
        return True, None
    return True, value + '%'


def add_tv_rt_scores(snapshot, cache):
    """Fetch cached TV series scores from their already verified RT URLs.

    Limit rate and abort on access restrictions; never clear a saved score.
    """
    stats = {'attempted': 0, 'found': 0, 'no_score': 0, 'unreadable': 0}
    for item in snapshot.get('shows', []):
        imdb = str(item.get('id') or '')
        record = cache.setdefault(imdb, {})
        url = record.get('rottenTomatoesUrl') or ''
        if not re.fullmatch(r'https://www\.rottentomatoes\.com/tv/[a-zA-Z0-9_-]+', url):
            continue
        if within_days(record.get('rtTvCheckedOn'), 14):
            continue
        if stats['attempted'] >= 110:
            break
        stats['attempted'] += 1
        request = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; ScreenLogPersonalSite/1.0)',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                final_url = urllib.parse.urlparse(response.geturl())
                if final_url.hostname != 'www.rottentomatoes.com':
                    raise ValueError('Unexpected RT redirect host')
                page = response.read(3_000_001)
                if len(page) > 3_000_000:
                    raise ValueError('RT page exceeds size limit')
            complete, score = parse_tv_critic_score(page.decode('utf-8', 'replace'))
            if not complete:
                stats['unreadable'] += 1
                continue
            if score:
                record['rottenTomatoes'] = score
                stats['found'] += 1
            else:
                stats['no_score'] += 1
            record['rtTvCheckedOn'] = TODAY
        except urllib.error.HTTPError as exc:
            print(f'RT TV score retrieval HTTP {exc.code} for {imdb}')
            if exc.code in (403, 429):
                print('RT TV score lookup paused due to access restriction; scores preserved.')
                break
            stats['unreadable'] += 1
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            print(f'RT TV score retrieval issue for {imdb}: {type(exc).__name__}')
            stats['unreadable'] += 1
        time.sleep(0.25)
    print('RT TV series critic scores: ' + ', '.join(f'{k}={v}' for k, v in stats.items()))


def enrich(snapshot, omdb_key):
    cache = load_cache()
    add_omdb(snapshot, cache, omdb_key)
    add_wikidata_links(snapshot, cache)
    add_tv_rt_scores(snapshot, cache)
    stats = {'imdb': 0, 'rt': 0, 'links': 0}
    for kind in ('movies', 'shows'):
        for item in snapshot[kind]:
            record = cache.get(item.get('id'), {})
            for field in FIELDS:
                if record.get(field):
                    item[field] = record[field]
            stats['imdb'] += bool(item.get('imdbRating'))
            stats['rt'] += bool(item.get('rottenTomatoes'))
            stats['links'] += bool(item.get('rottenTomatoesUrl'))
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('Ratings coverage with cache: ' + ', '.join(f'{k}={v}' for k, v in stats.items()))
