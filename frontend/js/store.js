/**
 * store.js — 店铺主页逻辑
 * 依赖：api.js、mock-data.js、common.js
 * 场景：用户在图书详情页点击“进入书店” → 查看该书店全部在架图书 →
 * 点击其中任意一本书 → 跳转回对应图书详情页。
 */
const STORE_PAGE_SIZE = 12;
let storeState = {
  storeId: qs("id"),
  sort: "default",
  page: 1,
  allBooks: [],
};

async function loadStoreProfile() {
  const store = await StoreAPI.detail(storeState.storeId);
  document.title = `${store.storeName} - My-eBookStore`;
  document.getElementById("breadcrumbStoreName").textContent = store.storeName;
  document.getElementById("storeName").textContent = store.storeName;
  document.getElementById("storeCreatedTime").textContent = store.createdTime || "-";
  document.getElementById("storeBookCount").textContent = store.bookCount;
  document.getElementById("storeSalesCount").textContent = store.salesCount;
}

async function loadStoreBooks() {
  const grid = document.getElementById("storeBookGrid");
  grid.innerHTML = `<div class="skeleton" style="height:280px"></div><div class="skeleton" style="height:280px"></div><div class="skeleton" style="height:280px"></div>`;

  const res = await StoreAPI.books(storeState.storeId, { sort: storeState.sort });
  storeState.allBooks = res.list || [];
  document.getElementById("storeResultCount").textContent = `共 ${storeState.allBooks.length} 本图书`;
  renderStorePage();
}

function renderStorePage() {
  const grid = document.getElementById("storeBookGrid");
  const totalPages = Math.max(1, Math.ceil(storeState.allBooks.length / STORE_PAGE_SIZE));
  storeState.page = Math.min(storeState.page, totalPages);
  const start = (storeState.page - 1) * STORE_PAGE_SIZE;
  const pageItems = storeState.allBooks.slice(start, start + STORE_PAGE_SIZE);

  if (pageItems.length === 0) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <div class="empty-icon">📭</div>
      <p>该书店暂无在架图书！</p>
    </div>`;
  } else {
    grid.innerHTML = pageItems.map(renderBookCard).join("");
    bindAddToCartButtons(grid);
  }
  renderStorePagination(totalPages);
}

function renderStorePagination(totalPages) {
  const pager = document.getElementById("storePagination");
  if (totalPages <= 1) {
    pager.innerHTML = "";
    return;
  }
  let html = `<button ${storeState.page === 1 ? "disabled" : ""} data-page="${storeState.page - 1}">‹</button>`;
  for (let i = 1; i <= totalPages; i++) {
    html += `<button class="${i === storeState.page ? "active" : ""}" data-page="${i}">${i}</button>`;
  }
  html += `<button ${storeState.page === totalPages ? "disabled" : ""} data-page="${storeState.page + 1}">›</button>`;
  pager.innerHTML = html;
  pager.querySelectorAll("button[data-page]").forEach((btn) => {
    btn.addEventListener("click", () => {
      storeState.page = Number(btn.dataset.page);
      renderStorePage();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".sort-tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".sort-tabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      storeState.sort = btn.dataset.sort;
      storeState.page = 1;
      loadStoreBooks();
    });
  });

  loadStoreProfile();
  loadStoreBooks();
});
