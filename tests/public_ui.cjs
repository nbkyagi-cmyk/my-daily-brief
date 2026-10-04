const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.value = 'all'; this.children = []; this.dataset = {}; this.innerHTML = ''; }
  classList = { toggle() {} };
  setAttribute() {}
  addEventListener() {}
  replaceChildren() { this.children = []; }
  append(n) { this.children.push(n); }
}
const elements = Object.fromEntries(['search', 'filter', 'articles', 'categories', 'status', 'warning', 'reload', 'published-at'].map(id => [id, new Element()]));
elements.search.value = '';
const context = vm.createContext({document: {getElementById: id => elements[id], createElement: () => new Element()}, localStorage: {getItem: () => '{}', setItem() {}}, fetch: async () => ({ok: true, json: async () => ({articles: []})}), console});
vm.runInContext(fs.readFileSync('docs/app.js', 'utf8'), context);
assert.equal(elements.categories.children.length, 7);
vm.runInContext(`data = {articles: categories.map((c, i) => ({id: String(i), category: c, title: 'title' + i, url: 'https://example.com', summary: [], first_seen: new Date().toISOString(), analysis: {}}))}; render();`, context);
assert.match(elements.status.textContent, /6件表示/);
elements.categories.children[2].onclick();
assert.match(elements.status.textContent, /1件表示/);
assert.match(elements.articles.innerHTML, /政治/);
elements.filter.value = 'saved';
vm.runInContext('render()', context);
assert.match(elements.status.textContent, /0件表示/);
vm.runInContext("savePreference('1', 'saved')", context);
assert.match(elements.status.textContent, /1件表示/);
elements.filter.value = 'unread';
vm.runInContext("savePreference('1', 'read')", context);
assert.match(elements.status.textContent, /0件表示/);
elements.filter.value = 'today';
vm.runInContext('render()', context);
assert.match(elements.status.textContent, /1件表示/);
elements.search.value = 'absent';
vm.runInContext('render()', context);
assert.match(elements.status.textContent, /0件表示/);
vm.runInContext("data.articles[1].url = 'javascript:alert(1)';", context);
elements.search.value = '';
vm.runInContext('render()', context);
assert.doesNotMatch(elements.articles.innerHTML, /javascript:/);
assert.equal(vm.runInContext("tokyoDay('2026-10-03T16:00:00Z')", context), '2026-10-04');
console.log('Public UI behavior passed');
vm.runInContext("data.articles[1].analysis = {importance: '対象外'}; render();", context);
assert.match(elements.articles.innerHTML, /スポーツ記事：AI分析対象外/);
assert.doesNotMatch(elements.articles.innerHTML, /<strong>重要度:<\/strong> 対象外/);
assert.match(elements.articles.innerHTML, /保存/);
