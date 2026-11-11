(() => {
  'use strict';
  const data = window.SCREENLOG_DATA;
  const $ = (q, root=document) => root.querySelector(q);
  const $$ = (q, root=document) => Array.from(root.querySelectorAll(q));
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const time = date => new Date(date || 0).getTime() || 0;
  const longDate = date => new Date(date).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'});
  const shortDate = date => new Date(date).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
  const monthKey = date => new Date(date).toISOString().slice(0,7);
  const colors = [['#765451','#302a42'],['#475b66','#192c36'],['#725642','#222a36'],['#4f5b51','#282c40'],['#594261','#222d39'],['#62604a','#263342']];
  const colorFor = id => {let h=0;for(const char of String(id))h=(h*31+char.charCodeAt(0))|0;return colors[Math.abs(h)%colors.length]};
  const movies = [...(data?.movies||[])].map(x=>({...x,kind:'movie'}));
  const shows = [...(data?.shows||[])].map(x=>({...x,kind:'show',episodes:[...(x.episodes||[])]}));
  const movieById=new Map(movies.map(x=>[x.id,x]));
  const showById=new Map(shows.map(x=>[x.id,x]));
  const episodes = shows.flatMap(s=>s.episodes.map(ep=>({...ep,kind:'episode',showId:s.id,showTitle:s.title,poster:s.poster,imdb:s.id})));
  const activity = [...movies.map(m=>({...m,kind:'movie'})),...episodes].sort((a,b)=>time(b.watchedAt)-time(a.watchedAt));
  let activityFilter='all',displayCount=50;
  let lastFocused=null,toastTimer=null;

  function placeholder(text){const words=String(text).split(' ');return words.slice(0,Math.min(words.length,6)).join(' ')}
  function posterArt(x,label){
    const [g1,g2]=colorFor(x.id||x.showId||x.title);
    const img=x.poster?`<img src="${esc(x.poster)}" alt="" loading="lazy" />`:'';
    const badge=label?`<span class="poster-label">${esc(label)}</span>`:'';
    return `<div class="poster-art" style="--g1:${g1};--g2:${g2}"><div class="poster-placeholder">${esc(placeholder(x.title||x.showTitle))}</div>${img}${badge}</div>`;
  }
  function card(x){
    const isShow=x.kind==='show';
    const info=isShow?`${x.episodes.length} episodes · ${new Set(x.episodes.map(e=>e.season)).size} seasons`:shortDate(x.watchedAt);
    return `<button type="button" class="poster-card" data-open="${isShow?'show':'movie'}" data-id="${esc(x.id)}" aria-label="Details for ${esc(x.title)}">${posterArt(x,isShow?'TV SHOW':'FILM')}<div class="poster-info"><div class="poster-title">${esc(x.title)}</div><div class="poster-meta">${esc(info)}</div></div></button>`;
  }
  function attachImages(parent=document){
    $$('img',parent).forEach(img=>{
      const fail=()=>{img.style.display='none'};
      img.addEventListener('error',fail,{once:true});
      if(img.complete&&!img.naturalWidth)fail();
    });
  }
  function goto(view){
    if(!['home','movies','shows','activity'].includes(view))view='home';
    $$('.view').forEach(el=>el.classList.toggle('active',el.id===`view-${view}`));
    $$('.nav-link').forEach(el=>{
      const selected=el.dataset.view===view;
      el.classList.toggle('selected',selected);el.setAttribute('aria-current',selected?'page':'false');
    });
    if(location.hash.slice(1)!==view)history.replaceState(null,'',`#${view}`);
    window.scrollTo({top:0,behavior:'smooth'});
    if(view==='movies')renderMovies();
    if(view==='shows')renderShows();
    if(view==='activity')renderActivity();
  }
  function stat(number,label,icon){return `<div class="stat"><div><strong>${esc(number)}</strong><span>${esc(label)}</span></div><div class="stat-icon" aria-hidden="true">${icon}</div></div>`}
  function renderHome(){
    $('#stats').innerHTML=stat(movies.length.toLocaleString(),'Films logged','◈')+stat(episodes.length.toLocaleString(),'TV episodes','▣')+stat(shows.length.toLocaleString(),'Series followed','☷')+stat(new Set(activity.map(x=>monthKey(x.watchedAt))).size,'Months of history','◷');
    const seenRecent=new Set();
    const newest=activity.filter(a=>{const key=a.kind==='movie'?`movie:${a.id}`:`show:${a.showId}`;if(seenRecent.has(key))return false;seenRecent.add(key);return true}).slice(0,7).map(a=>a.kind==='movie'?a:{title:a.showTitle,kind:'show',id:a.showId,poster:a.poster,watchedAt:a.watchedAt,episodes:showById.get(a.showId)?.episodes||[]});
    $('#recentRail').innerHTML=newest.map(card).join('');
    $('#seriesRail').innerHTML=[...shows].sort((a,b)=>b.episodes.length-a.episodes.length).slice(0,6).map(card).join('');
    const collage = [ ...shows.filter(x=>x.episodes.length>5).slice(0,4),...movies.slice(0,2) ];
    $('#heroCollage').innerHTML=collage.map(x=>`<div class="hero-mini" style="background:linear-gradient(140deg,${colorFor(x.id)[0]},${colorFor(x.id)[1]})">${x.poster?`<img src="${esc(x.poster)}" alt="" loading="lazy">`:''}<span>${esc(placeholder(x.title))}</span></div>`).join('');
    const months=new Map();
    activity.forEach(a=>{const key=monthKey(a.watchedAt);months.set(key,(months.get(key)||0)+1)});
    const newestMonths=[...months.keys()].sort().slice(-8);
    const max=Math.max(...newestMonths.map(k=>months.get(k)),1);
    $('#monthlyChart').innerHTML=newestMonths.map(key=>{
      const value=months.get(key);
      const label=new Date(key+'-01T12:00:00Z').toLocaleDateString('en-US',{month:'short'});
      return `<div class="month-col" title="${esc(key)}: ${value} plays"><div class="month-val">${value}</div><div class="month-plot"><div class="month-bar" style="height:${Math.max(3,value/max*100)}%"></div></div><div class="month-label">${esc(label)}</div></div>`;
    }).join('');
    $('#syncStatus').textContent=data.live?'Synced with Trakt · '+shortDate(data.updatedAt):'Imported from Nuvio · '+shortDate(data.updatedAt);
    $('#footerDate').textContent='Last updated '+longDate(data.updatedAt);
    attachImages($('#view-home'));
  }
  function renderMovies(){
    const query=$('#movieSearch').value.toLocaleLowerCase().trim();
    const sort=$('#movieSort').value;
    const list=movies.filter(x=>(x.title||'').toLocaleLowerCase().includes(query));
    if(sort==='alpha')list.sort((a,b)=>a.title.localeCompare(b.title));
    if(sort==='recent')list.sort((a,b)=>time(b.watchedAt)-time(a.watchedAt));
    if(sort==='oldest')list.sort((a,b)=>time(a.watchedAt)-time(b.watchedAt));
    $('#movieCount').textContent=`${list.length} ${list.length===1?'movie':'movies'}`;
    $('#moviesGrid').innerHTML=list.length?list.map(card).join(''):'<div class="empty">No movies matched that search.</div>';
    attachImages($('#moviesGrid'));
  }
  function renderShows(){
    const query=$('#showSearch').value.toLocaleLowerCase().trim();
    const sort=$('#showSort').value;
    const list=shows.filter(x=>(x.title||'').toLocaleLowerCase().includes(query));
    if(sort==='alpha')list.sort((a,b)=>a.title.localeCompare(b.title));
    if(sort==='recent')list.sort((a,b)=>time(b.lastWatchedAt)-time(a.lastWatchedAt));
    if(sort==='most')list.sort((a,b)=>b.episodes.length-a.episodes.length);
    $('#showCount').textContent=`${list.length} ${list.length===1?'series':'series'}`;
    $('#showsGrid').innerHTML=list.length?list.map(card).join(''):'<div class="empty">No series matched that search.</div>';
    attachImages($('#showsGrid'));
  }
  function renderActivity(){
    const selected=activity.filter(x=>activityFilter==='all'||x.kind===activityFilter);
    $('#activityCount').textContent=`${selected.length} logged items`;
    let last='',html='';
    selected.slice(0,displayCount).forEach(x=>{
      const date=new Date(x.watchedAt).toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'});
      if(date!==last){html+=`<div class="day-head">${esc(date)}</div>`;last=date}
      const isMovie=x.kind==='movie';const label=isMovie?x.title:x.showTitle;
      const title=isMovie?x.title:(x.title&&x.title!==x.showTitle?`${x.title}`:`Season ${x.season}, episode ${x.episode}`);
      const detail=isMovie?'Movie watched':`${x.showTitle} · S${String(x.season).padStart(2,'0')}E${String(x.episode).padStart(2,'0')}`;
      html+=`<div class="activity-row"><div class="activity-thumb" style="background:linear-gradient(135deg,${colorFor(x.id||x.showId)[0]},${colorFor(x.id||x.showId)[1]})">${x.poster?`<img src="${esc(x.poster)}" alt="" loading="lazy">`:''}</div><div style="min-width:0"><div class="activity-title">${esc(title)}</div><div class="activity-sub">${esc(detail)} <span class="activity-type">${isMovie?'FILM':'EPISODE'}</span></div></div><time datetime="${esc(x.watchedAt)}">${esc(new Date(x.watchedAt).toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'}))}</time></div>`;
    });
    $('#activityList').innerHTML=html||'<div class="empty">Nothing in this category yet.</div>';
    $('#loadMore').hidden=selected.length<=displayCount;
    attachImages($('#activityList'));
  }
  function ratingMarkup(item){
    const imdb = item.imdbRating && /^\d+(?:\.\d+)?$/.test(String(item.imdbRating)) ? item.imdbRating+'/10' : 'N/A';
    const rt = item.rottenTomatoes && /^\d{1,3}%$/.test(String(item.rottenTomatoes)) ? item.rottenTomatoes : 'N/A';
    const imdbUrl = /^tt\d+$/.test(item.id) ? 'https://www.imdb.com/title/'+encodeURIComponent(item.id)+'/' : null;
    const rtDirect = typeof item.rottenTomatoesUrl === 'string' && /^https:\/\/www\.rottentomatoes\.com\/(?:m|tv)\/[a-zA-Z0-9_/-]+$/.test(item.rottenTomatoesUrl);
    const rtUrl = rtDirect ? item.rottenTomatoesUrl : 'https://www.rottentomatoes.com/search?search='+encodeURIComponent(item.title);
    return '<div class="detail-metric" style="display:flex;gap:22px;flex-wrap:wrap;align-items:center">'+
      '<div><div class="detail-label">IMDb</div><div style="font-size:1.4rem;font-weight:800;margin-top:5px">★ '+esc(imdb)+'</div>'+
      (imdbUrl?'<a class="detail-link" href="'+imdbUrl+'" target="_blank" rel="noopener noreferrer">IMDb ↗</a>':'')+'</div>'+
      '<div><div class="detail-label">'+(item.kind==='show'?'Rotten Tomatoes · Series Avg.':'Rotten Tomatoes · Critics')+'</div><div style="font-size:1.4rem;font-weight:800;margin-top:5px">🍅 '+esc(rt)+'</div>'+
      '<a class="detail-link" href="'+rtUrl+'" target="_blank" rel="noopener noreferrer">'+(rtDirect?'View on Rotten Tomatoes ↗':'Find on Rotten Tomatoes ↗')+'</a></div></div>';
  }
  function openDetail(kind,id){
    const item=(kind==='show'?showById:movieById).get(id);
    if(!item)return;
    lastFocused=document.activeElement;
    const isShow=kind==='show';
    const count=isShow?item.episodes.length:1;
    const kicker=isShow?`TV SERIES · ${count} EPISODES`:'MOVIE · WATCHED';
    let html=`<div class="detail-top"><button type="button" class="detail-close" aria-label="Close details">×</button><div class="detail-kicker">${esc(kicker)}</div><h2>${esc(item.title)}</h2></div><div class="detail-body">`;
    html+=ratingMarkup(item);
    if(isShow){
      html+=`<p class="detail-summary">Every episode recorded for this series, grouped by season. These are watched episodes, not a guarantee that the series is complete.</p><div class="detail-metric"><div><div class="detail-number">${item.episodes.length}</div><div class="detail-label">Episodes logged</div></div><div><div class="detail-number">${new Set(item.episodes.map(e=>e.season)).size}</div><div class="detail-label">Seasons represented</div></div></div>`;
      const seasons=[...new Set(item.episodes.map(e=>e.season))].sort((a,b)=>b-a);
      seasons.forEach(season=>{
        html+=`<h3 class="detail-season-title">Season ${esc(season)}</h3>`;
        const list=item.episodes.filter(e=>e.season===season).sort((a,b)=>a.episode-b.episode);
        list.forEach(ep=>{const episodeTitle=ep.title&&ep.title!==item.title?ep.title:`Episode ${ep.episode}`;html+=`<div class="episode-item"><span class="episode-id">E${String(ep.episode).padStart(2,'0')}</span><span class="episode-title">${esc(episodeTitle)}</span><span class="episode-date">${esc(shortDate(ep.watchedAt))}</span></div>`});
      });
    }else{
      html+=`<p class="detail-summary">This movie is recorded as watched in the archive.</p><div class="detail-metric"><div><div class="detail-label">Last watched</div><div style="margin-top:7px;font-weight:700">${esc(longDate(item.watchedAt))}</div></div></div>`;
      if(item.year)html+=`<div class="detail-metric"><div class="detail-label">Release year</div><strong>${esc(item.year)}</strong></div>`;
    }
    if(/^tt\d+$/.test(id))html+=`<a class="detail-link" href="https://www.imdb.com/title/${encodeURIComponent(id)}/" target="_blank" rel="noopener">View on IMDb ↗</a>`;
    html+='</div>';
    $('#detailContent').innerHTML=html;
    $('#detailBackdrop').hidden=false;$('#detailPanel').hidden=false;
    document.body.style.overflow='hidden';
    $('.detail-close').focus();
  }
  function closeDetail(){
    $('#detailBackdrop').hidden=true;$('#detailPanel').hidden=true;
    document.body.style.overflow='';
    if(lastFocused && typeof lastFocused.focus==='function')lastFocused.focus();
  }
  function toast(s){
    const el=$('#toast');el.textContent=s;el.classList.add('visible');
    if(toastTimer)clearTimeout(toastTimer);
    toastTimer=setTimeout(()=>el.classList.remove('visible'),3200);
  }
  async function share(){
    if(location.protocol==='file:'){toast('This is a private preview. Publish the site first to share a public link.');return}
    try{
      if(navigator.share){await navigator.share({title:'Screen Log',url:location.href});return}
      await navigator.clipboard.writeText(location.href);toast('Site link copied to clipboard!');
    }catch(e){if(e.name!=='AbortError')toast('Copy the address from your browser to share.')}
  }
  function init(){
    if(!data||!data.movies||!data.shows){$('#main').innerHTML='<div class="empty">No viewing history is available.</div>';return}
    renderHome();renderMovies();renderShows();renderActivity();
    $$('.nav-link').forEach(el=>el.addEventListener('click',()=>goto(el.dataset.view)));
    $$('[data-goto]').forEach(el=>el.addEventListener('click',()=>goto(el.dataset.goto)));
    $('#brand').addEventListener('click',e=>{e.preventDefault();goto('home')});
    $('#movieSearch').addEventListener('input',renderMovies);$('#showSearch').addEventListener('input',renderShows);
    $('#movieSort').addEventListener('change',renderMovies);$('#showSort').addEventListener('change',renderShows);
    $$('[data-history-filter]').forEach(el=>el.addEventListener('click',()=>{activityFilter=el.dataset.historyFilter;displayCount=50;$$('[data-history-filter]').forEach(n=>n.classList.toggle('active',n===el));renderActivity()}));
    $('#loadMore').addEventListener('click',()=>{displayCount+=50;renderActivity()});
    document.addEventListener('click',e=>{const hit=e.target.closest('[data-open]');if(hit)openDetail(hit.dataset.open,hit.dataset.id)});
    $('#detailBackdrop').addEventListener('click',closeDetail);
    $('#detailPanel').addEventListener('click',e=>{if(e.target.closest('.detail-close'))closeDetail()});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#detailPanel').hidden)closeDetail()});
    $('#shareBtn').addEventListener('click',share);
    window.addEventListener('hashchange',()=>goto(location.hash.slice(1)||'home'));
    goto(location.hash.slice(1)||'home');
  }
  document.addEventListener('DOMContentLoaded',init);
})();
