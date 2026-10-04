let data,category='all',csrf='',pendingRun=null,prefs=JSON.parse(localStorage.getItem('mdb-prefs')||'{}');
const $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
async function api(path,body){const r=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},body:body?JSON.stringify(body):undefined});const v=await r.json();if(!r.ok)throw Error(v.error||'通信に失敗しました');return v;}
function save(){localStorage.setItem('mdb-prefs',JSON.stringify(prefs));render();}
function render(){
 if(pendingRun){const r=data.runs.find(r=>r.id===pendingRun);if(r&&r.status!=='running'){$('message').textContent=r.status==='success'?`更新完了：新着${r.added}件`:'更新に失敗または一部失敗しました。履歴をご確認ください。';pendingRun=null;}}
 const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Tokyo'}).format(new Date());
 $('status').textContent='最終全更新成功：'+(data.last_success?new Date(data.last_success).toLocaleString('ja-JP',{timeZone:'Asia/Tokyo'}):'まだありません');
 const latest=data.runs[0];$('warning').textContent=data.demo?'デモモード：すべて架空の記事です。':latest&&['failed','partial'].includes(latest.status)?'更新に失敗または一部取得に失敗しました。更新管理から手動復旧できます。':data.overdue?'本日の全更新が未完了です。更新管理をご確認ください。':'';
 const newCount=data.articles.filter(a=>a.first_seen.startsWith(today)).length;
 const yesterday=new Date(Date.now()-86400000);const y=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Tokyo'}).format(yesterday);
 $('diff').textContent=`昨日との差分：今日の新着 ${newCount}件 ／ 昨日の新着 ${data.articles.filter(a=>a.first_seen.startsWith(y)).length}件（初回取得日による比較）`;
 const q=$('search').value.toLowerCase(),f=$('filter').value;
 const list=data.articles.filter(a=>(category==='all'||a.category===category)&&JSON.stringify([a.title,a.source,a.summary]).toLowerCase().includes(q)&&(f!=='saved'||prefs[a.id]?.saved)&&(f!=='unread'||!prefs[a.id]?.read)&&(f!=='today'||a.first_seen.startsWith(today))).sort((a,b)=>(a.analysis.importance==='高'?-1:0)-(b.analysis.importance==='高'?-1:0));
 $('articles').replaceChildren();if(!list.length)$('articles').append(el('p','記事がありません。カテゴリ・検索条件や取得元設定をご確認ください。'));
 for(const a of list){const card=el('article','','card'+(prefs[a.id]?.read?' read':''));card.append(el('p',a.category+' · '+a.source+' · 重要度 '+a.analysis.importance,'meta'),el('h3',a.title));const ul=el('ul','','summary');for(const s of a.summary)ul.append(el('li',s));card.append(el('small','出典概要（最大3行相当・AIによる事実補作なし）'),ul,el('p','掲載日：'+(a.published||'取得元に記載なし')+' ／ 初回取得：'+a.first_seen.slice(0,10),'meta'));
 const detail=el('details');detail.append(el('summary','背景・なぜ重要か・所見 / 展望'));const box=el('div','','analysis');box.append(el('small','AI分析（事実と分離）'));for(const [k,label] of [['background','背景'],['why','なぜ重要か'],['outlook','所見・展望']])box.append(el('p',label+'：'+a.analysis[k]));detail.append(box);card.append(detail);
 const actions=el('div','','actions');const link=el('a','原文を読む');link.href=a.url;link.target='_blank';link.rel='noopener noreferrer';actions.append(link);
 for(const [key,label] of [['saved','保存'],['read','既読']]){const b=el('button',(prefs[a.id]?.[key]?'✓ ':'')+label);b.setAttribute('aria-pressed',String(!!prefs[a.id]?.[key]));b.onclick=()=>{prefs[a.id]??={};prefs[a.id][key]=!prefs[a.id][key];save();};actions.append(b);}card.append(actions);$('articles').append(card);}
 $('runs').replaceChildren();for(const r of data.runs){const names={success:'成功',partial:'一部失敗',failed:'失敗',running:'更新中'};$('runs').append(el('p',`${r.mode==='automatic'?'自動':r.mode==='manual'?'手動':'ローカル'} · ${r.category==='all'?'全更新':r.category} · ${names[r.status]} · ${r.started} · 新着${r.added}件 ${r.error||''}`));}
 $('update').disabled=data.runs.some(r=>r.status==='running');
}
async function refresh(){try{data=await api('/api/news');render();}catch(e){$('warning').textContent='オフラインまたは通信失敗。更新状態を確認できません。接続後に再試行してください。';$('update').disabled=true;}}
function auth(ok){$('login').hidden=ok;$('controls').hidden=!ok;}
async function init(){await refresh();if(!data)return;for(const c of ['all',...data.categories]){const b=el('button',c==='all'?'すべて':c,c==='all'?'active':'');b.onclick=()=>{category=c;for(const n of $('categories').children)n.classList.toggle('active',n===b);render();};$('categories').append(b);if(c!=='all'){const o=el('option',c);o.value=c;$('target').append(o);}}
 const session=await api('/api/session');csrf=session.csrf;auth(session.authenticated);
}
$('search').oninput=()=>data&&render();$('filter').onchange=()=>data&&render();
$('login').onsubmit=async e=>{e.preventDefault();const b=$('login').querySelector('button');b.disabled=true;try{const s=await api('/api/login',{password:$('password').value});csrf=s.csrf;$('password').value='';auth(true);$('message').textContent='ログインしました';}catch(e){$('message').textContent=e.message;}finally{b.disabled=false;}};
$('update').onclick=async()=>{ $('update').disabled=true;try{const result=await api('/api/update',{category:$('target').value});pendingRun=result.id;$('message').textContent='更新を開始しました。この画面を閉じても処理は続きます。';await refresh();}catch(e){$('message').textContent=e.message;$('update').disabled=false;}};
$('logout').onclick=async()=>{await api('/api/logout',{});csrf='';auth(false);};
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js');
init().catch(e=>$('message').textContent=e.message);setInterval(refresh,15000);
