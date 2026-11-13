const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('site/app.js','utf8');
const start = source.indexOf('  function renderActivity(){');
const end = source.indexOf('  function ratingMarkup', start);
assert.ok(start >= 0 && end > start, 'History renderer should be present');
const elements = {
  '#activityCount': {},
  '#activityList': {},
  '#loadMore': {}
};
const context = {
  activityFilter:'all',
  displayCount:50,
  activity:[
    {kind:'movie',id:'tt1234567',title:'A Film & Friends',poster:'posters/film.webp',watchedAt:'2026-11-13T12:00:00Z'},
    {kind:'episode',showId:'tt7777000',showTitle:'MobLand',title:'Nervous Breakdown',season:2,episode:9,poster:'posters/show.webp',watchedAt:'2026-11-13T13:00:00Z'}
  ],
  $:selector=>elements[selector],
  esc:input=>String(input??'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  colorFor:()=>['#111','#222'],
  attachImages:()=>{},
  Date, String
};
vm.runInNewContext(source.slice(start,end)+'\nrenderActivity();',context);
const output = elements['#activityList'].innerHTML;
assert.equal((output.match(/class="activity-poster-link"/g)||[]).length,2);
assert.equal((output.match(/class="activity-title-link"/g)||[]).length,2);
assert.equal((output.match(/data-open="movie" data-id="tt1234567"/g)||[]).length,2);
assert.equal((output.match(/data-open="show" data-id="tt7777000"/g)||[]).length,2);
assert.ok(output.includes('A Film &amp; Friends'));
assert.ok(output.includes('>MobLand</button>'));
assert.ok(output.includes('Nervous Breakdown'));
assert.ok(output.includes('S02E09'));
assert.equal(elements['#activityCount'].textContent,'2 logged items');
console.log('History links and content: passed');
