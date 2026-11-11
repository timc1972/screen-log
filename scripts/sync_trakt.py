#!/usr/bin/env python3
"""Build a public read-only Screen Log snapshot from public Trakt history.

Designed for a GitHub Actions job. Requires a Trakt API client ID as an
Actions secret (TRAKT_CLIENT_ID), never in site/ or source control.
No password, OAuth token, client secret, or add-on configuration is needed
when the target Trakt profile/history is public.
"""
import json, os, re, time, urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'site'/'data.js'
POSTERS=ROOT/'site'/'posters'
USER='kfg72'
API='https://api.trakt.tv'


def load_snapshot():
    text=DATA.read_text(encoding='utf-8').strip()
    if not text.startswith('window.SCREENLOG_DATA = '):
        raise RuntimeError('Existing data.js has unexpected format')
    return json.loads(text[len('window.SCREENLOG_DATA = '):].rstrip(';'))


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
                        'watchedAt':date,'watches':1}
        else:
            movies[id]['watches']+=1
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
                       'episodes':{}}
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


def add_ratings(snapshot, api_key):
    """Enrich titles using OMDb. Never expose the key in published data."""
    if not api_key:
        print('OMDB_API_KEY missing; ratings will remain unavailable.')
        return
    for kind in ('movies', 'shows'):
        for item in snapshot[kind]:
            imdb_id = item.get('id', '')
            if not re.fullmatch(r'tt\\d+', imdb_id):
                continue
            try:
                query = urllib.parse.urlencode({'apikey': api_key, 'i': imdb_id})
                req = urllib.request.Request('https://www.omdbapi.com/?' + query,
                                             headers={'User-Agent': 'ScreenLogPersonalSite/1.0'})
                with urllib.request.urlopen(req, timeout=15) as response:
                    info = json.loads(response.read())
                if info.get('Response') != 'True':
                    continue
                score = info.get('imdbRating')
                if score and score != 'N/A':
                    item['imdbRating'] = score
                for rating in info.get('Ratings', []):
                    if rating.get('Source') == 'Rotten Tomatoes':
                        value = rating.get('Value', '')
                        if re.fullmatch(r'\\d{1,3}%', value):
                            item['rottenTomatoes'] = value
                # OMDb does not reliably provide an RT title URL.
                # Link to a title search rather than guessing a slug.
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                print(f'Ratings unavailable for {imdb_id}: {type(exc).__name__}')
            time.sleep(0.06)


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
    new=build(mh,eh,prev)\n    add_ratings(new, os.getenv('OMDB_API_KEY','').strip())
    before=len(prev.get('movies',[]))+sum(len(s['episodes']) for s in prev.get('shows',[]))
    after=len(new['movies'])+sum(len(s['episodes']) for s in new['shows'])
    # Safety guard for an accidental missing page, or API/profile access regression.
    if before>100 and after<before*0.6:
        raise RuntimeError(f'Refusing to replace {before} existing watched items with only {after}; existing site data is preserved.')
    DATA.write_text('window.SCREENLOG_DATA = '+json.dumps(new,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print(f'Screen Log synced: {len(new["movies"])} movies, {len(new["shows"])} shows, {sum(len(s["episodes"]) for s in new["shows"])} unique episodes')

if __name__=='__main__':main()
