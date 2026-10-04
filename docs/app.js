const $ = id => document.getElementById(id);

let data = { articles: [] };
let category = "all";
const categories = ['総合ニュース', '政治', '経済', '国際', '水道・インフラ', '無電柱化'];
let prefs = {};
try { prefs = JSON.parse(localStorage.getItem('mdb-prefs') || '{}') || {}; } catch {}
function savePreference(id, key) {
  prefs[id] ??= {};
  prefs[id][key] = !prefs[id][key];
  try { localStorage.setItem('mdb-prefs', JSON.stringify(prefs)); } catch {
    $('warning').textContent = '端末に保存できません。この画面を閉じると保存・既読の状態が失われます。';
  }
  render();
}
function tokyoDay(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('sv-SE', {timeZone: 'Asia/Tokyo'});
}
function renderCategories() {
  $('categories').replaceChildren();
  for (const c of ['all', ...categories]) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = c === 'all' ? 'すべて' : c;
    button.classList.toggle('active', category === c);
    button.setAttribute('aria-pressed', String(category === c));
    button.onclick = () => { category = c; renderCategories(); render(); };
    $('categories').append(button);
  }
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function render() {
  const q = ($("search")?.value || "").toLowerCase();
  const filter = $("filter")?.value || "all";

  let articles = data.articles || [];

  articles = articles.filter(a => {
    if (category !== 'all' && a.category !== category) return false;
    if (filter === "today") {
      const today = new Date().toLocaleDateString("sv-SE", {
        timeZone: "Asia/Tokyo"
      });
      if (tokyoDay(a.first_seen) !== today) return false;
    }

    if (filter === "saved") {
      if (!prefs[a.id]?.saved) return false;
    }

    if (filter === 'unread' && prefs[a.id]?.read) return false;

    const text = [
      a.title,
      a.category,
      a.source,
      ...(Array.isArray(a.summary) ? a.summary : [])
    ].join(" ").toLowerCase();

    return !q || text.includes(q);
  }).sort((a, b) => (b.analysis?.importance === '高') - (a.analysis?.importance === '高') ||
    String(b.first_seen).localeCompare(String(a.first_seen)));

  const box = $("articles");
  if (!box) return;

  box.innerHTML = articles.map(a => {
    const summary = Array.isArray(a.summary)
      ? a.summary.map(x => `<li>${esc(x)}</li>`).join("")
      : "";

    const analysis = a.analysis || {};
    const importance = analysis.importance || "未評価";

    return `
      <article class="card${prefs[a.id]?.read ? ' read' : ''}">
        <div class="meta">${esc(a.category)} ・ ${esc(a.source || "")}</div>
        <h3><a href="${esc(/^https:\/\//i.test(a.url) ? a.url : '#')}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a></h3>
        <ul>${summary}</ul>
        ${importance === '対象外' ? '<p class="muted">スポーツ記事：AI分析対象外</p>' : `<p><strong>重要度:</strong> ${esc(importance)}</p>`}
        ${analysis.background && analysis.background !== "未生成"
          ? `<p><strong>背景:</strong> ${esc(analysis.background)}</p>` : ""}
        ${analysis.why && analysis.why !== "未生成"
          ? `<p><strong>なぜ重要:</strong> ${esc(analysis.why)}</p>` : ""}
        ${analysis.outlook && analysis.outlook !== "未生成"
          ? `<p><strong>今後:</strong> ${esc(analysis.outlook)}</p>` : ""}
        <div class="actions">
          <button type="button" data-id="${esc(a.id)}" data-pref="saved" aria-pressed="${!!prefs[a.id]?.saved}">${prefs[a.id]?.saved ? '✓ ' : ''}保存</button>
          <button type="button" data-id="${esc(a.id)}" data-pref="read" aria-pressed="${!!prefs[a.id]?.read}">${prefs[a.id]?.read ? '✓ ' : ''}既読</button>
        </div>
      </article>
    `;
  }).join("");

  if (!articles.length) {
    box.innerHTML = "<p>該当する記事はありません。</p>";
  }

  if ($("status")) {
    $("status").textContent = `公開版：${articles.length}件表示 ／ 全${data.articles.length}件`;
  }
}

async function load() {
  try {
    const r = await fetch("./articles.json", { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);

    data = await r.json();
    if (!Array.isArray(data.articles)) throw new Error('Invalid articles');
    $('warning').textContent = '';
    $('published-at').textContent = '記事データ更新日時：' + (data.generated_at && tokyoDay(data.generated_at)
      ? new Date(data.generated_at).toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo'}) + ' JST' : '不明');
    render();
  } catch (e) {
    console.error(e);
    if ($("warning")) {
      $("warning").textContent =
        "ニュースデータを読み込めませんでした。";
    }
  }
}

$("search")?.addEventListener("input", render);
$("filter")?.addEventListener("change", render);

$('articles').addEventListener('click', event => {
  const button = event.target.closest('button[data-pref]');
  if (button) savePreference(button.dataset.id, button.dataset.pref);
});
$('reload').addEventListener('click', load);
renderCategories();

load();
