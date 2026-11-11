#!/usr/bin/env python3
"""Convert a personal NuvioSync backup to Screen Log's public-only snapshot.

No account identifiers, plugins, access tokens, playback progress, or private profiles are exported.
"""
import json, sys, re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
# Explicit IMDb corrections discovered from source/library mismatches.
KNOWN_SHOW_NAMES = {
  'tt0118375': 'King of the Hill',
  'tt5875444': 'Slow Horses',
  'tt34866681': 'Lucky'
}

def iso(ms):
    return datetime.fromtimestamp(int(ms)/1000, tz=timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def candidate_poster(meta, imdb):
    poster = (meta or {}).get('poster')
    if isinstance(poster,str) and poster.startswith('https://'):
        return poster
    # This is Nuvio's Cinemeta poster URL pattern, not Trakt's artwork CDN.
    return f'https://images.metahub.space/poster/medium/{imdb}/img' if re.fullmatch('tt[0-9]+', imdb or '') else ''

def export(data):
    original = data['original']; library = {x['content_id']:x for x in original.get('library',[]) if x.get('content_id')}
    watches=original.get('watched',[])
    titles=defaultdict(list)
    for entry in watches:
        if entry.get('content_type') == 'series' and entry.get('season') is not None and entry.get('episode') is not None:
            titles[entry['content_id']].append(entry)
    # For series missing from library, the Nuvio episode title is not necessarily the series name.
    # The 3 known ambiguities are corrected by IMDb ID. Other names are matched to a verified import reference.
    ref=HERE.parent/'Trakt_TV_Importer_kfg72_V2'/'tv_episodes.json'
    refnames={}
    if ref.exists():
        for item in json.loads(ref.read_text(encoding='utf-8')):
            refnames.setdefault(item['show_imdb_id'], item['nuvio_title'])
    showlist=[]
    for imdb, eps in titles.items():
        info=library.get(imdb,{})
        name=KNOWN_SHOW_NAMES.get(imdb) or info.get('name') or refnames.get(imdb)
        if not name:
            name=f'Series {imdb}'
        episodes=[{'season':int(x['season']),'episode':int(x['episode']), 'title':x.get('title') or '', 'watchedAt':iso(x['watched_at'])} for x in eps]
        episodes.sort(key=lambda x: (x['season'],x['episode']))
        showlist.append({'id':imdb,'title':name,'year':str(info.get('release_info','')).split('–')[0][:4] if info.get('release_info') else None,'poster':candidate_poster(info,imdb),'genres':info.get('genres') or [],'episodes':episodes,'lastWatchedAt':max(e['watchedAt'] for e in episodes)})
    showlist.sort(key=lambda x:x['lastWatchedAt'],reverse=True)
    movie_map={}
    for x in watches:
        if x.get('content_type')!='movie': continue
        imdb=x.get('content_id'); meta=library.get(imdb,{})
        dt=iso(x['watched_at'])
        if imdb not in movie_map or dt>movie_map[imdb]['watchedAt']:
            movie_map[imdb]={'id':imdb,'title':x.get('title') or meta.get('name') or imdb,
              'year':str(meta.get('release_info','')).split('–')[0][:4] if meta.get('release_info') else None,
              'poster':candidate_poster(meta,imdb), 'genres':meta.get('genres') or [], 'watchedAt':dt, 'watches':1}
        else: movie_map[imdb]['watches']+=1
    movies=sorted(movie_map.values(),key=lambda x:x['watchedAt'],reverse=True)
    return {
      'schemaVersion':1,
      'profile': {'username':'kfg72','displayName':'Screen Log'},
      'source':'Nuvio backup preview',
      'updatedAt':data.get('createdAt'),
      'live':False,
      'movies':movies,
      'shows':showlist,
    }

if __name__=='__main__':
    if len(sys.argv)<2: raise SystemExit('Usage: python scripts/build_seed.py /path/to/nuvio-backup.json')
    input_data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    clean=export(input_data)
    outfile=HERE/'site'/'data.js'
    outfile.write_text('window.SCREENLOG_DATA = '+json.dumps(clean,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print('Public snapshot:',len(clean['movies']),'movies,',len(clean['shows']),'shows,',sum(len(x['episodes']) for x in clean['shows']),'episodes')
    print('Wrote',outfile)
