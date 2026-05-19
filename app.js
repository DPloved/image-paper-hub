const state = {
  data: null,
  category: 'all',
  query: '',
  year: 'all',
};

const categoryRows = document.querySelector('#categoryRows');
const categoryChips = document.querySelector('#categoryChips');
const paperList = document.querySelector('#paperList');
const statsGrid = document.querySelector('#statsGrid');
const emptyState = document.querySelector('#emptyState');
const searchInput = document.querySelector('#searchInput');
const yearFilter = document.querySelector('#yearFilter');

const hasLink = (paper, key) => Boolean(paper.links?.[key]);
const categoryById = (id) => state.data.categories.find((item) => item.id === id);

function countByCategory(categoryId) {
  const papers = state.data.papers.filter((paper) => paper.category === categoryId);
  return {
    total: papers.length,
    arxiv: papers.filter((paper) => hasLink(paper, 'arxiv')).length,
    code: papers.filter((paper) => hasLink(paper, 'code')).length,
  };
}

function renderStats() {
  const papers = state.data.papers;
  const stats = [
    ['论文总数', papers.length],
    ['研究方向', state.data.categories.length],
    ['已匹配 arXiv', papers.filter((paper) => hasLink(paper, 'arxiv')).length],
    ['已找到代码', papers.filter((paper) => hasLink(paper, 'code')).length],
  ];

  statsGrid.innerHTML = stats.map(([label, value]) => `
    <article class="stat-card">
      <span>${label}</span>
      <strong>${value}</strong>
    </article>
  `).join('');

  document.querySelector('#lastUpdated').textContent = state.data.site.updated;
}

function renderCategories() {
  categoryRows.innerHTML = state.data.categories.map((category, index) => {
    const counts = countByCategory(category.id);
    return `
      <tr>
        <td>${index + 1}</td>
        <td><button class="category-link" data-category="${category.id}">${category.name}</button><br><small>${category.summary}</small></td>
        <td>${counts.total}</td>
        <td>${counts.arxiv}</td>
        <td>${counts.code}</td>
      </tr>
    `;
  }).join('');

  categoryChips.innerHTML = [
    `<button class="chip active" data-category="all">全部</button>`,
    ...state.data.categories.map((category) => `<button class="chip" data-category="${category.id}">${category.name}</button>`),
  ].join('');

  document.querySelectorAll('[data-category]').forEach((button) => {
    button.addEventListener('click', () => {
      state.category = button.dataset.category;
      document.querySelector('#papers').scrollIntoView({ behavior: 'smooth' });
      renderPapers();
    });
  });
}

function renderYearFilter() {
  const years = [...new Set(state.data.papers.map((paper) => paper.year))].sort((a, b) => b - a);
  yearFilter.innerHTML = '<option value="all">全部年份</option>' + years.map((year) => `<option value="${year}">${year}</option>`).join('');
}

function paperMatches(paper) {
  const haystack = [paper.title, paper.authors, paper.venue, paper.summary, ...(paper.tags || [])].join(' ').toLowerCase();
  const queryMatch = !state.query || haystack.includes(state.query.toLowerCase());
  const categoryMatch = state.category === 'all' || paper.category === state.category;
  const yearMatch = state.year === 'all' || String(paper.year) === state.year;
  return queryMatch && categoryMatch && yearMatch;
}

function renderPapers() {
  const papers = state.data.papers.filter(paperMatches).sort((a, b) => b.year - a.year || a.title.localeCompare(b.title));

  document.querySelectorAll('.chip').forEach((chip) => {
    chip.classList.toggle('active', chip.dataset.category === state.category);
  });

  paperList.innerHTML = papers.map((paper) => {
    const category = categoryById(paper.category);
    const links = Object.entries(paper.links || {})
      .filter(([, url]) => Boolean(url))
      .map(([label, url]) => `<a href="${url}" target="_blank" rel="noreferrer">${label}</a>`)
      .join('');

    return `
      <article class="paper-card">
        <span class="status">${paper.status}</span>
        <div class="paper-meta">${paper.year} · ${paper.venue} · ${category?.name || '未分类'}</div>
        <h3>${paper.title}</h3>
        <p><strong>${paper.authors}</strong></p>
        <p>${paper.summary}</p>
        <div class="tags">${(paper.tags || []).map((tag) => `<span class="tag">${tag}</span>`).join('')}</div>
        <div class="links">${links || '<span class="tag">待补充链接</span>'}</div>
      </article>
    `;
  }).join('');

  emptyState.hidden = papers.length > 0;
}

async function init() {
  const response = await fetch('papers.json');
  state.data = await response.json();
  renderStats();
  renderCategories();
  renderYearFilter();
  renderPapers();
}

searchInput.addEventListener('input', (event) => {
  state.query = event.target.value.trim();
  renderPapers();
});

yearFilter.addEventListener('change', (event) => {
  state.year = event.target.value;
  renderPapers();
});

init();
