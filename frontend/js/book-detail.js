/**
 * book-detail.js — 图书详情页逻辑
 * 依赖：api.js、common.js
 * 对应用例：4.2.2 Browse and Search Books（详情部分）、4.2.3 Add Book to Cart
 */
let currentBook = null;

function renderDetail(book) {
  currentBook = book;
  document.title = `${book.bookName} - My-eBookStore`;

  document.getElementById("bookCoverIcon").textContent = book.cover || "📘";
  document.getElementById("breadcrumbTitle").textContent = book.bookName;
  document.getElementById("bookTitle").textContent = book.bookName;
  document.getElementById("bookStoreName").textContent = book.storeName;
  document.getElementById("enterStoreLink").href = `store.html?id=${book.storeId}`;
  document.getElementById("bookAuthor").textContent = book.author;
  document.getElementById("bookPublisher").textContent = book.publisher || "-";
  document.getElementById("bookIsbn").textContent = book.isbn || "-";
  document.getElementById("bookCategory").textContent = book.categoryName || "-";
  document.getElementById("bookPublishDate").textContent = book.publishDate || "-";
  document.getElementById("bookSales").textContent = book.salesCount;
  document.getElementById("bookPrice").textContent = Number(book.price).toFixed(2);
  document.getElementById("bookOriginPrice").textContent = `¥${Number(book.originPrice || book.price).toFixed(2)}`;
  document.getElementById("bookDescription").textContent = book.description;

  const stockEl = document.getElementById("bookStock");
  stockEl.textContent = book.stock > 0 ? `库存 ${book.stock} 件` : "已售罄";
  stockEl.className = book.stock > 0 ? "badge badge-success" : "badge badge-danger";

  const qtyInput = document.getElementById("qtyInput");
  qtyInput.max = book.stock;
  const addBtn = document.getElementById("addToCartBtn");
  const buyBtn = document.getElementById("buyNowBtn");
  if (book.stock === 0) {
    addBtn.disabled = true;
    buyBtn.disabled = true;
  }
  // 书店管理员 / 后台管理员不具备购买行为，隐藏“加入购物车 / 立即购买”按钮
  if (isAdminRole(getCurrentUser())) {
    addBtn.classList.add("hidden");
    buyBtn.classList.add("hidden");
  }

  renderReviews(book.reviews || []);
}

function renderReviews(reviews) {
  const el = document.getElementById("reviewList");
  if (!reviews.length) {
    el.innerHTML = "暂无评价";
    return;
  }
  el.innerHTML = reviews
    .map(
      (r) => `
    <div class="order-item-row">
      <div style="flex:1">
        <div style="font-weight:600">${escapeHtml(r.userName || "匿名用户")}<span class="text-muted" style="font-weight:400;margin-left:8px">${"★".repeat(r.rating)}${"☆".repeat(5 - r.rating)}</span></div>
        <div class="text-muted" style="font-size:12px;margin-top:4px">${escapeHtml(r.content || "")}</div>
        <div class="text-muted" style="font-size:12px">${formatDate(r.createdTime)}</div>
      </div>
    </div>`
    )
    .join("");
}

async function loadSimilarBooks(bookItemId) {
  const grid = document.getElementById("similarGrid");
  const similar = await BookAPI.similar(bookItemId);
  grid.innerHTML = similar.map(renderBookCard).join("");
  bindAddToCartButtons(grid);
}

function bindQtyStepper() {
  const input = document.getElementById("qtyInput");
  document.getElementById("qtyMinus").addEventListener("click", () => {
    input.value = Math.max(1, Number(input.value) - 1);
  });
  document.getElementById("qtyPlus").addEventListener("click", () => {
    input.value = Math.min(Number(input.max) || 99, Number(input.value) + 1);
  });
}

function bindTabs() {
  const tabs = document.querySelectorAll(".detail-tabs button");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll(".detail-panel").forEach((p) => p.classList.remove("active"));
      document.getElementById(tab.dataset.panel).classList.add("active");
    });
  });
}

function bindActions() {
  document.getElementById("addToCartBtn").addEventListener("click", async () => {
    if (!requireLogin("请先登录后再加入购物车！")) return;
    const qty = Number(document.getElementById("qtyInput").value) || 1;
    await CartAPI.add(currentBook.bookItemId, qty);
    document.dispatchEvent(new CustomEvent("cart:updated"));
    showToast("加入购物车成功", "success");
  });

  document.getElementById("buyNowBtn").addEventListener("click", async () => {
    if (!requireLogin("请先登录后再购买！")) return;
    const qty = Number(document.getElementById("qtyInput").value) || 1;
    await CartAPI.add(currentBook.bookItemId, qty);
    localStorage.setItem("ebs_checkout_items", JSON.stringify([String(currentBook.bookItemId)]));
    document.dispatchEvent(new CustomEvent("cart:updated"));
    window.location.href = "checkout.html";
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  const bookItemId = qs("id");
  if (!bookItemId) {
    showToast("缺少图书编号，请从搜索页重新选择图书", "warning");
    setTimeout(() => (window.location.href = "search.html"), 700);
    return;
  }
  try {
    const book = await BookAPI.detail(bookItemId);
    renderDetail(book);
    bindQtyStepper();
    bindTabs();
    bindActions();
    loadSimilarBooks(bookItemId);
  } catch (err) {
    showToast(err.message || "图书详情加载失败", "danger");
    setTimeout(() => (window.location.href = "search.html"), 900);
  }
});
