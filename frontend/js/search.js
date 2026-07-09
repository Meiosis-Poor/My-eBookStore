/**
 * search.js — 搜索结果页 / 分类浏览页逻辑
 * 依赖：api.js、common.js
 * 对应用例：4.2.2 Browse and Search Books 图书浏览与搜索
 */
const PAGE_SIZE = 12;
let state = {
  keyword: qs("keyword") || "",
  searchType: qs("searchType") || "title",
  categoryId: qs("categoryId") || "",
  sort: qs("sort") || "default",
  inStockOnly: false,
  page: 1,
  allResults: [],
  total: 0,
};

async function loadCategories() {
  const panel = document.getElementById("categoryFilterList");
  const categories = await BookAPI.listCategories();
  panel.innerHTML = categories
    .map(
      (c) => `
      <label class="filter-option">
        <input type="radio" name="categoryFilter" value="${c.categoryId}" ${String(c.categoryId) === String(state.categoryId) ? "checked" : ""} />
        ${c.categoryName}
      </label>`
    )
    .join("");
  panel.querySelectorAll('input[name="categoryFilter"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.categoryId = input.value;
      state.page = 1;
      runSearch();
    });
  });
}

async function runSearch() {
  const grid = document.getElementById("searchResultGrid");
  const countEl = document.getElementById("resultCount");
  grid.innerHTML = `<div class="skeleton" style="height:280px"></div><div class="skeleton" style="height:280px"></div><div class="skeleton" style="height:280px"></div>`;

  const res = await BookAPI.list({
    keyword: state.keyword,
    searchType: state.searchType,
    categoryId: state.categoryId,
    sort: state.sort,
    page: state.page,
    pageSize: PAGE_SIZE,
    inStockOnly: state.inStockOnly ? 1 : "",
  });
  let list = res.list || [];
  state.allResults = list;
  state.total = res.total || list.length;

  countEl.textContent = `共找到 ${state.total} 件相关商品`;
  renderPage();

  if (state.keyword) SearchAPI.record(state.keyword);
}

function renderPage() {
  const grid = document.getElementById("searchResultGrid");
  const totalPages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
  state.page = Math.min(state.page, totalPages);
  const pageItems = state.allResults;

  if (pageItems.length === 0) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <div class="empty-icon">📭</div>
      <p>未找到相关图书！换个关键词试试吧。</p>
    </div>`;
  } else {
    grid.innerHTML = pageItems.map(renderBookCard).join("");
    bindAddToCartButtons(grid);
  }

  renderPagination(totalPages);
}

function renderPagination(totalPages) {
  const pager = document.getElementById("pagination");
  if (totalPages <= 1) {
    pager.innerHTML = "";
    return;
  }
  let html = `<button ${state.page === 1 ? "disabled" : ""} data-page="${state.page - 1}">‹</button>`;
  for (let i = 1; i <= totalPages; i++) {
    html += `<button class="${i === state.page ? "active" : ""}" data-page="${i}">${i}</button>`;
  }
  html += `<button ${state.page === totalPages ? "disabled" : ""} data-page="${state.page + 1}">›</button>`;
  pager.innerHTML = html;
  pager.querySelectorAll("button[data-page]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.page = Number(btn.dataset.page);
      runSearch();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("searchKeywordInput").value = state.keyword;
  document.getElementById("searchTitle").textContent = state.keyword
    ? `“${state.keyword}” 的搜索结果`
    : "全部图书";

  document.querySelectorAll("#searchModeBar button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === state.searchType);
    btn.addEventListener("click", () => {
      document.querySelectorAll("#searchModeBar button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.searchType = btn.dataset.mode;
      state.page = 1;
      if (state.keyword) runSearch();
    });
  });

  document.getElementById("searchForm").addEventListener("submit", (e) => {
    e.preventDefault();
    state.keyword = document.getElementById("searchKeywordInput").value.trim();
    state.page = 1;
    document.getElementById("searchTitle").textContent = state.keyword
      ? `“${state.keyword}” 的搜索结果`
      : "全部图书";
    runSearch();
  });

  document.querySelectorAll(".sort-tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".sort-tabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.sort = btn.dataset.sort;
      state.page = 1;
      runSearch();
    });
  });

  document.getElementById("inStockOnly").addEventListener("change", (e) => {
    state.inStockOnly = e.target.checked;
    state.page = 1;
    runSearch();
  });

  loadCategories();
  runSearch();
});
