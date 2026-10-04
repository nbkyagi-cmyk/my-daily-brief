const $ = id => document.getElementById(id);

let data = { articles: [] };

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
    if (filter === "today") {
      const today = new Date().toLocaleDateString("sv-SE", {
        timeZone: "Asia/Tokyo"
      });
      if (!String(a.first_seen || "").startsWith(today)) return false;
    }

    if (filter === "saved") {
      return false;
    }

    if (filter !== "all" && filter !== "today") {
      if (a.category !== filter) return false;
    }

    const text = [
      a.title,
      a.category,
      a.source,
      ...(Array.isArray(a.summary) ? a.summary : [])
    ].join(" ").toLowerCase();

    return !q || text.includes(q);
  });

  const box = $("articles");
  if (!box) return;

  box.innerHTML = articles.map(a => {
    const summary = Array.isArray(a.summary)
      ? a.summary.map(x => `<li>${esc(x)}</li>`).join("")
      : "";

    const analysis = a.analysis || {};
    const importance = analysis.importance || "未評価";

    return `
      <article class="card">
        <div class="meta">${esc(a.category)} ・ ${esc(a.source || "")}</div>
        <h3><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a></h3>
        <ul>${summary}</ul>
        <p><strong>重要度:</strong> ${esc(importance)}</p>
        ${analysis.background && analysis.background !== "未生成"
          ? `<p><strong>背景:</strong> ${esc(analysis.background)}</p>` : ""}
        ${analysis.why && analysis.why !== "未生成"
          ? `<p><strong>なぜ重要:</strong> ${esc(analysis.why)}</p>` : ""}
        ${analysis.outlook && analysis.outlook !== "未生成"
          ? `<p><strong>今後:</strong> ${esc(analysis.outlook)}</p>` : ""}
      </article>
    `;
  }).join("");

  if (!articles.length) {
    box.innerHTML = "<p>該当する記事はありません。</p>";
  }

  if ($("status")) {
    $("status").textContent = `公開版：${articles.length}件表示`;
  }
}

async function load() {
  try {
    const r = await fetch("./articles.json", { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);

    data = await r.json();
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

/* GitHub Pages公開版では管理機能を表示しない */
if ($("admin")) {
  $("admin").hidden = true;
}

load();
