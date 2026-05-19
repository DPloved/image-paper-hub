const state = {
  data: null,
  category: 'all',
  query: '',
  year: 'all',
};

const categoryRows = document.querySelector('#categoryRows');
const categoryChips = document.querySelector('#categoryChips');
const chapterList = document.querySelector('#chapterList');
const paperList = document.querySelector('#paperList');
const statsGrid = document.querySelector('#statsGrid');
const emptyState = document.querySelector('#emptyState');
const searchInput = document.querySelector('#searchInput');
const yearFilter = document.querySelector('#yearFilter');

const hasLink = (paper, key) => Boolean(paper.links?.[key]);
const categoryById = (id) => state.data.categories.find((item) => item.id === id);
const subcategoryById = (category, id) => category?.subcategories?.find((item) => item.id === id);

function papersForCategory(categoryId) {
  return state.data.papers.filter((paper) => paper.category === categoryId);
}

function countByCategory(categoryId) {
  const papers = papersForCategory(categoryId);
  return {
    total: papers.length,
    arxiv: papers.filter((paper) => hasLink(paper, 'arxiv')).length,
    code: papers.filter((paper) => hasLink(paper, 'code')).length,
  };
}

function renderStats() {
  const papers = state.data.papers;
  const subcategoryCount = state.data.categories.reduce((sum, item) => sum + (item.subcategories?.length || 0), 0);
  const stats = [
    ['论文总数', papers.length],
    ['大类', state.data.categories.length],
    ['小类', subcategoryCount],
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
    const subcats = (category.subcategories || []).map((item) => item.name).join(' / ');
    return `
      <tr>
        <td>${index + 1}</td>
        <td>
          <button class="category-link" data-category="${category.id}">${category.name}</button>
          <br><small>${subcats}</small>
        </td>
        <td>${counts.total}</td>
        <td>${counts.arxiv}</td>
        <td>${counts.code}</td>
      </tr>
    `;
  }).join('');

  categoryChips.innerHTML = [
    `<button class="chip active" data-category="all">全部</button>`,
    ...state.data.categories.map((category, index) => `<button class="chip" data-category="${category.id}">${index + 1}. ${category.name.split('、')[0]}</button>`),
  ].join('');

  document.querySelectorAll('[data-category]').forEach((button) => {
    button.addEventListener('click', () => {
      state.category = button.dataset.category;
      document.querySelector('#papers').scrollIntoView({ behavior: 'smooth' });
      renderAllPaperViews();
    });
  });
}

function renderYearFilter() {
  const years = [...new Set(state.data.papers.map((paper) => paper.year))].sort((a, b) => b - a);
  yearFilter.innerHTML = '<option value="all">全部年份</option>' + years.map((year) => `<option value="${year}">${year}</option>`).join('');
}

function paperMatches(paper) {
  const category = categoryById(paper.category);
  const subcategory = subcategoryById(category, paper.subcategory);
  const haystack = [
    paper.title,
    paper.authors,
    paper.venue,
    paper.summary,
    category?.name,
    subcategory?.name,
    ...(paper.tags || []),
  ].join(' ').toLowerCase();
  const queryMatch = !state.query || haystack.includes(state.query.toLowerCase());
  const categoryMatch = state.category === 'all' || paper.category === state.category;
  const yearMatch = state.year === 'all' || String(paper.year) === state.year;
  return queryMatch && categoryMatch && yearMatch;
}

function linkText(paper) {
  const links = [];
  if (hasLink(paper, 'paper')) links.push(`<a href="${paper.links.paper}" target="_blank" rel="noreferrer">paper</a>`);
  if (hasLink(paper, 'arxiv')) links.push(`<a href="${paper.links.arxiv}" target="_blank" rel="noreferrer">arXiv</a>`);
  if (hasLink(paper, 'code')) links.push(`<a href="${paper.links.code}" target="_blank" rel="noreferrer">code</a>`);
  return links.join(' ');
}

function renderPaperLine(paper) {
  return `
    <li class="paper-line">
      <span class="paper-year">${paper.year}</span>
      <strong>${paper.title}</strong>
      <span class="authors">— ${paper.authors}</span>
      <span class="venue"> · ${paper.venue}</span>
      <span class="inline-links">${linkText(paper)}</span>
      <p>${paper.summary}</p>
    </li>
  `;
}

function renderChapters(filteredPapers) {
  const visibleCategories = state.data.categories.filter((category) => {
    return state.category === 'all' ? true : category.id === state.category;
  });

  chapterList.innerHTML = visibleCategories.map((category, categoryIndex) => {
    const subSections = (category.subcategories || []).map((subcategory, subIndex) => {
      const papers = filteredPapers
        .filter((paper) => paper.category === category.id && paper.subcategory === subcategory.id)
        .sort((a, b) => b.year - a.year || a.title.localeCompare(b.title));
      if (!papers.length && state.query) return '';
      return `
        <section class="subchapter" id="${subcategory.id}">
          <h3>${categoryIndex + 1}.${subIndex + 1} ${subcategory.name}</h3>
          ${papers.length ? `<ul>${papers.map(renderPaperLine).join('')}</ul>` : '<p class="empty-sub">暂未收录，欢迎补充。</p>'}
        </section>
      `;
    }).join('');

    const counts = countByCategory(category.id);
    return `
      <article class="chapter" id="${category.id}">
        <div class="chapter-title">
          <div>
            <span class="chapter-no">${categoryIndex + 1}</span>
            <h2>${category.name}</h2>
          </div>
          <span>${counts.total} 篇</span>
        </div>
        <p class="chapter-summary">${category.summary}</p>
        ${subSections || '<p class="empty-sub">当前筛选下没有匹配论文。</p>'}
      </article>
    `;
  }).join('');
}

function renderCards(filteredPapers) {
  paperList.innerHTML = filteredPapers.slice(0, 12).map((paper) => {
    const category = categoryById(paper.category);
    const subcategory = subcategoryById(category, paper.subcategory);
    return `
      <article class="paper-card">
        <span class="status">${paper.status}</span>
        <div class="paper-meta">${paper.year} · ${paper.venue} · ${subcategory?.name || category?.name || '未分类'}</div>
        <h3>${paper.title}</h3>
        <p><strong>${paper.authors}</strong></p>
        <p>${paper.summary}</p>
        <div class="tags">${(paper.tags || []).map((tag) => `<span class="tag">${tag}</span>`).join('')}</div>
        <div class="links">${linkText(paper) || '<span class="tag">待补充链接</span>'}</div>
      </article>
    `;
  }).join('');
}

function renderAllPaperViews() {
  const filteredPapers = state.data.papers.filter(paperMatches);

  document.querySelectorAll('.chip').forEach((chip) => {
    chip.classList.toggle('active', chip.dataset.category === state.category);
  });

  renderChapters(filteredPapers);
  renderCards(filteredPapers);
  emptyState.hidden = filteredPapers.length > 0;
}

async function init() {
  const response = await fetch('papers.json');
  state.data = await response.json();
  renderStats();
  renderCategories();
  renderYearFilter();
  renderAllPaperViews();
}

searchInput.addEventListener('input', (event) => {
  state.query = event.target.value.trim();
  renderAllPaperViews();
});

yearFilter.addEventListener('change', (event) => {
  state.year = event.target.value;
  renderAllPaperViews();
});

init();
