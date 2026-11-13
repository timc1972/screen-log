#!/usr/bin/env python3
"""Build a public read-only Screen Log snapshot from public Trakt history.

Designed for a GitHub Actions job. Requires a Trakt API client ID as an
Actions secret (TRAKT_CLIENT_ID), never in site/ or source control.
No password, OAuth token, client secret, or add-on configuration is needed
when the target Trakt profile/history is public.
"""
import json, os, re, tarfile, time, urllib.error, urllib.parse, urllib.request
from copy import deepcopy
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from ratings import enrich

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'site'/'data.js'
POSTERS=ROOT/'site'/'posters'
HISTORY_CACHE=ROOT/'scripts'/'watch-history-cache.json'
HISTORY_BOOTSTRAP=ROOT/'.history-bootstrap'/'artifact.tar'
USER='kfg72'
API='https://api.trakt.tv'


def parse_history_snapshot(raw):
    """Read only snapshots belonging to this Trakt profile."""
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    prefix = 'window.SCREENLOG_DATA = '
    if not raw.lstrip().startswith(prefix):
        raise ValueError('Unexpected ScreenLog history format')
    payload = json.loads(raw.strip()[len(prefix):].rstrip(';'))
    return check_history_snapshot(payload)


def check_history_snapshot(snapshot):
    if not isinstance(snapshot, dict) or (snapshot.get('profile') or {}).get('username') != USER:
        raise ValueError('Watch history is not for the configured Trakt account')
    if not isinstance(snapshot.get('movies'), list) or not isinstance(snapshot.get('shows'), list):
        raise ValueError('Watch history is missing movie or show records')
    if not snapshot['movies'] or not snapshot['shows']:
        raise ValueError('Watch history snapshot appears empty')
    return snapshot


def load_snapshot():
    """Use the last successful published watch archive, not stale repo data.js.

    The archive survives runs in an Actions cache. A verified deployment artifact
    seeds it initially; the live site's snapshot is a recovery fallback.
    Fail closed if none is available so a sync cannot erase the archive.
    """
    if HISTORY_CACHE.exists():
        try:
            snapshot = check_history_snapshot(json.loads(HISTORY_CACHE.read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeError('Persisted ScreenLog history cache is invalid; refusing to overwrite it') from exc
        print('Watch archive loaded from Actions cache: {} movies, {} shows, {} episodes'.format(
            len(snapshot['movies']), len(snapshot['shows']),
            sum(len(show.get('episodes', [])) for show in snapshot['shows'])))
        return snapshot
    if HISTORY_BOOTSTRAP.is_file():
        try:
            with tarfile.open(HISTORY_BOOTSTRAP, mode='r:*') as bundle:
                member = next(m for m in bundle.getmembers()
                              if m.name.lstrip('./') == 'data.js' and m.isfile())
                raw = bundle.extractfile(member).read()
            snapshot = parse_history_snapshot(raw)
            print('Watch archive bootstrapped from verified Nov 13 deployment: {} episodes'.format(
                sum(len(show.get('episodes', [])) for show in snapshot['shows'])))
            return snapshot
        except (OSError, ValueError, KeyError, StopIteration, tarfile.TarError) as exc:
            raise RuntimeError('Verified ScreenLog history bootstrap is corrupt') from exc
    # Handles an evicted cache after the initial seed artifact has expired.
    url = 'https://timc1972.github.io/screen-log/data.js?archive-refresh=' + str(int(time.time()))
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'ScreenLogHistoryArchive/1.0',
                                                       'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(10_000_001)
        if len(raw) > 10_000_000:
            raise ValueError('Published history is too large')
        snapshot = parse_history_snapshot(raw)
        print('Watch archive recovered from currently published ScreenLog site.')
        return snapshot
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise RuntimeError('No trustworthy prior watch history available; refusing to discard watches') from exc

def request(url,client_id):
    headers={'Content-Type':'application/json','trakt-api-key':client_id,
             'trakt-api-version':'2','User-Agent':'ScreenLogPersonalSite/1.0'}
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (429,500,502,503) and attempt<3:
                delay=min(20,int(exc.headers.get('Retry-After','4'))*(attempt+1))
                time.sleep(delay);continue
            raise RuntimeError(f'Trakt API returned HTTP {exc.code}. Check that @kfg72 history is public and the client ID works.') from exc
    raise RuntimeError('Too many API retries')


def history(client_id,kind):
    all_items=[]
    for page in range(1,101):
        query=urllib.parse.urlencode({'page':page,'limit':100,'extended':'full'})
        payload=request(f'{API}/users/{USER}/history/{kind}?{query}',client_id)
        if not isinstance(payload,list): raise RuntimeError(f'Unexpected Trakt response for {kind}, page {page}')
        if not payload: break
        all_items.extend(payload)
        print(f'{kind} page {page}: {len(payload)} events')
        if len(payload)<100:break
    else:
        raise RuntimeError('History exceeded 100 pages; refusing a potentially partial sync')
    return all_items


def safe_date(date):
    if not date: return None
    try:
        parsed=datetime.fromisoformat(str(date).replace('Z','+00:00')).astimezone(timezone.utc)
        return parsed.isoformat(timespec='seconds').replace('+00:00','Z')
    except ValueError:return None


def make_id(obj):
    ids=obj.get('ids') or {}
    imdb=ids.get('imdb')
    if isinstance(imdb,str) and re.fullmatch(r'tt\d+',imdb): return imdb
    trakt=ids.get('trakt')
    if isinstance(trakt,int): return f'trakt-{trakt}'
    return None


def safe_overview(item, old):
    """Use Trakt's synopsis; retain an older nonempty description if missing."""
    raw = item.get('overview')
    if not isinstance(raw, str) or not raw.strip():
        raw = old.get('overview', '')
    if not isinstance(raw, str):
        return ''
    text = ' '.join(raw.split())
    if len(text) > 1800:
        text = text[:1799].rsplit(' ', 1)[0] + '…'
    return text


def local_poster(obj,kind,key):
    images=obj.get('images') or {}
    raw=images.get('poster') if isinstance(images,dict) else None
    if not raw:return None
    url=raw[0] if isinstance(raw,list) and raw else raw if isinstance(raw,str) else None
    if not url or not isinstance(url,str):return None
    if not url.startswith('https://'):url='https://'+url.lstrip('/')
    host=urlparse(url).hostname or ''
    if not host.endswith('.trakt.tv'):return None
    # Trakt requires images be locally cached, not linked to their CDN.
    POSTERS.mkdir(parents=True,exist_ok=True)
    dest=POSTERS/f'{kind}-{re.sub("[^a-zA-Z0-9_-]","",key)}.webp'
    if not dest.exists():
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'ScreenLogPersonalSite/1.0'})
            with urllib.request.urlopen(req,timeout=25) as resp:
                mime=resp.headers.get('Content-Type','').split(';')[0].lower()
                if mime not in ('image/webp','image/jpeg','image/png'):return None
                blob=resp.read(2_000_001)
                if len(blob)>2_000_000:return None
                # Browsers sniff image bytes; Trakt poster URLs are WebP by default.
                dest.write_bytes(blob)
        except (OSError,urllib.error.URLError):return None
    return 'posters/'+dest.name


def merge_archive(current, previous):
    """Never silently drop previously confirmed watches on a partial Trakt response.

    Trakt remains authoritative for newer dates, but absence alone is not
    treated as deletion. An explicit archive-removal feature would be required
    if the owner intentionally wants to unwatch a title.
    """
    stats = {'movies': 0, 'shows': 0, 'episodes': 0}
    existing_movies = {str(item['id']): item for item in current['movies']}
    for prior in previous.get('movies', []):
        if not isinstance(prior, dict) or not prior.get('id'):
            continue
        ident = str(prior['id'])
        item = existing_movies.get(ident)
        if item is None:
            current['movies'].append(deepcopy(prior))
            existing_movies[ident] = current['movies'][-1]
            stats['movies'] += 1
        else:
            if prior.get('watchedAt', '') > item.get('watchedAt', ''):
                item['watchedAt'] = prior['watchedAt']
            item['watches'] = max(item.get('watches', 1), prior.get('watches', 1))
    current['movies'].sort(key=lambda item: item.get('watchedAt', ''), reverse=True)

    existing_shows = {str(item['id']): item for item in current['shows']}
    for prior in previous.get('shows', []):
        if not isinstance(prior, dict) or not prior.get('id'):
            continue
        ident = str(prior['id'])
        item = existing_shows.get(ident)
        if item is None:
            item = deepcopy(prior)
            current['shows'].append(item)
            existing_shows[ident] = item
            stats['shows'] += 1
            stats['episodes'] += len(item.get('episodes') or [])
            continue
        episodes = {(ep['season'], ep['episode']): ep for ep in item.get('episodes', [])}
        for old in prior.get('episodes', []):
            key = (old['season'], old['episode'])
            if key not in episodes:
                episodes[key] = deepcopy(old)
                stats['episodes'] += 1
            elif old.get('watchedAt', '') > episodes[key].get('watchedAt', ''):
                episodes[key]['watchedAt'] = old['watchedAt']
                if not episodes[key].get('title'):
                    episodes[key]['title'] = old.get('title', '')
        item['episodes'] = sorted(episodes.values(), key=lambda ep: (ep['season'], ep['episode']))
        if item['episodes']:
            item['lastWatchedAt'] = max(ep['watchedAt'] for ep in item['episodes'])
    current['shows'].sort(key=lambda item: item.get('lastWatchedAt', ''), reverse=True)
    print('Watch archive preserved missing records: ' +
          ', '.join('{}={}'.format(key, value) for key, value in stats.items()))
    return current


def build(movies_history,episode_history,previous):
    old_movies={x['id']:x for x in previous.get('movies',[])}
    old_shows={x['id']:x for x in previous.get('shows',[])}
    movies={}
    for row in movies_history:
        item=row.get('movie') or {}; id=make_id(item)
        date=safe_date(row.get('watched_at'))
        if not id or not date:continue
        old=old_movies.get(id,{})
        poster=local_poster(item,'movie',id) or old.get('poster') or ''
        if id not in movies:
            movies[id]={'id':id,'title':item.get('title') or old.get('title') or id,
                        'year':str(item['year']) if item.get('year') else old.get('year'),
                        'poster':poster,'genres':item.get('genres') or old.get('genres') or [],
                        'overview':safe_overview(item, old),
                        'watchedAt':date,'watches':1}
        else:
            movies[id]['watches']+=1
            if not movies[id].get('overview'):
                movies[id]['overview']=safe_overview(item, old)
            if date>movies[id]['watchedAt']:movies[id]['watchedAt']=date
    shows={}
    for row in episode_history:
        item=row.get('show') or {}
        episode=row.get('episode') or {}
        id=make_id(item)
        s=episode.get('season');e=episode.get('number');date=safe_date(row.get('watched_at'))
        if not id or s is None or e is None or not date:continue
        old=old_shows.get(id,{})
        if id not in shows:
            poster=local_poster(item,'show',id) or old.get('poster') or ''
            shows[id]={'id':id,'title':item.get('title') or old.get('title') or id,
                       'year':str(item['year']) if item.get('year') else old.get('year'),
                       'poster':poster,'genres':item.get('genres') or old.get('genres') or [],
                       'overview':safe_overview(item, old),
                       'episodes':{}}
        elif not shows[id].get('overview'):
            shows[id]['overview']=safe_overview(item, old)
        ep_key=(int(s),int(e))
        old_ep=next((x for x in old.get('episodes',[]) if x['season']==s and x['episode']==e),None)
        ep={'season':int(s),'episode':int(e),'title':episode.get('title') or (old_ep or {}).get('title') or '',
            'watchedAt':date}
        if ep_key not in shows[id]['episodes'] or date>shows[id]['episodes'][ep_key]['watchedAt']:
            shows[id]['episodes'][ep_key]=ep
    output_shows=[]
    for s in shows.values():
        s['episodes']=sorted(s['episodes'].values(),key=lambda x:(x['season'],x['episode']))
        s['lastWatchedAt']=max(x['watchedAt'] for x in s['episodes'])
        output_shows.append(s)
    output_shows.sort(key=lambda s:s['lastWatchedAt'],reverse=True)
    output_movies=sorted(movies.values(),key=lambda m:m['watchedAt'],reverse=True)
    return {'schemaVersion':1,'profile':{'username':USER,'displayName':'Screen Log'},
            'source':'Trakt API','updatedAt':datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'),
            'live':True,'movies':output_movies,'shows':output_shows}


def main():
    client_id=os.getenv('TRAKT_CLIENT_ID','').strip()
    if not client_id:
        print('TRAKT_CLIENT_ID secret not present; keeping the private-preview snapshot unchanged.')
        return
    prev=load_snapshot()
    mh=history(client_id,'movies')
    eh=history(client_id,'episodes')
    if not mh or not eh:
        raise RuntimeError('Trakt returned empty or incomplete watch history. Existing site data is preserved.')
    new=merge_archive(build(mh,eh,prev), prev)
    enrich(new, os.getenv('OMDB_API_KEY','').strip())
    before=len(prev.get('movies',[]))+sum(len(s['episodes']) for s in prev.get('shows',[]))
    after=len(new['movies'])+sum(len(s['episodes']) for s in new['shows'])
    # Safety guard for an accidental missing page, or API/profile access regression.
    if before>100 and after<before*0.6:
        raise RuntimeError(f'Refusing to replace {before} existing watched items with only {after}; existing site data is preserved.')
    DATA.write_text('window.SCREENLOG_DATA = '+json.dumps(new,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    HISTORY_CACHE.write_text(json.dumps(new, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Screen Log synced: {len(new["movies"])} movies, {len(new["shows"])} shows, {sum(len(s["episodes"]) for s in new["shows"])} unique episodes')
    print(f'Synopsis coverage: movies={sum(bool(m.get("overview")) for m in new["movies"])}/{len(new["movies"])}, shows={sum(bool(s.get("overview")) for s in new["shows"])}/{len(new["shows"])}')

if __name__=='__main__':main()
