/**
 * admin/books.js — 后台图书管理页逻辑
 * 依赖：../api.js、../common.js、common.js（本目录）
 * 对应用例：4.3.1 Book Management 图书管理
 */
let booksCache = [];
let editingBookId = null;

function renderBooksTable(list) {
  const tbody = document.getElementById("booksTableBody");
  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding:32px">暂无图书数据</td></tr>`;
    return;
  }
  tbody.innerHTML = list
    .map(
      (b) => `
    <tr>
      <td>
        <div class="cell-book">
          <div class="mini-cover">${renderBookCover(b.cover, b.bookName)}</div>
          <div>
            <div style="font-weight:600">${b.bookName}</div>
            <div class="text-muted" style="font-size:12px">ISBN ${b.isbn}</div>
          </div>
        </div>
      </td>
      <td>${b.author}</td>
      <td>${b.storeName}</td>
      <td>${b.categoryName}</td>
      <td>${formatPrice(b.price)}</td>
      <td>${b.stock}</td>
      <td>${b.salesCount}</td>
      <td>
        <div class="row-actions">
          <button data-action="edit" data-id="${b.bookItemId}">编辑</button>
          <button data-action="remove" data-id="${b.bookItemId}" class="danger">下架</button>
          <button data-action="force" data-id="${b.bookItemId}" class="danger" data-role-only="platform_admin">强制下架</button>
        </div>
      </td>
    </tr>`
    )
    .join("");

  // 后台管理员专属操作按钮的显隐由 initAdminShell 统一处理，这里补一次防止表格重渲染后失效
  if (getCurrentUser().userType !== "platform_admin") {
    tbody.querySelectorAll('[data-role-only="platform_admin"]').forEach((el) => el.classList.add("hidden"));
  }

  tbody.querySelectorAll('[data-action="edit"]').forEach((btn) => {
    btn.addEventListener("click", () => openBookModal(btn.dataset.id));
  });
  tbody.querySelectorAll('[data-action="remove"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      await AdminAPI.books.remove(btn.dataset.id);
      showToast("图书信息操作成功", "success");
      loadBooks();
    });
  });
  tbody.querySelectorAll('[data-action="force"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      await AdminAPI.books.forceTakedown(btn.dataset.id, "平台巡检认定为违规/风险图书");
      showToast("已强制下架该图书", "success");
      loadBooks();
    });
  });
}

async function loadBooks() {
  const keyword = document.getElementById("bookSearchInput").value.trim();
  const res = await AdminAPI.books.list({ keyword });
  booksCache = res.list;
  renderBooksTable(booksCache);
}

async function openBookModal(bookItemId) {
  editingBookId = bookItemId || null;
  const form = document.getElementById("bookForm");
  form.reset();

  const categories = await BookAPI.listCategories();
  const categorySelect = form.categoryId;
  categorySelect.innerHTML = categories.map((c) => `<option value="${c.categoryId}">${c.categoryName}</option>`).join("");

  document.getElementById("bookModalTitle").textContent = editingBookId ? "编辑图书" : "新增图书";

  if (editingBookId) {
    const book = booksCache.find((b) => String(b.bookItemId) === String(editingBookId));
    if (book) {
      form.bookName.value = book.bookName;
      form.author.value = book.author;
      form.publisher.value = book.publisher;
      form.isbn.value = book.isbn;
      form.categoryId.value = book.categoryId;
      form.price.value = book.price;
      form.stock.value = book.stock;
      form.description.value = book.description;
    }
  }
  openModal("bookModal");
}

document.addEventListener("DOMContentLoaded", () => {
  const user = initAdminShell("books");
  if (!user) return;

  document.getElementById("bookSearchInput").addEventListener("input", debounce(loadBooks, 350));
  document.getElementById("addBookBtn").addEventListener("click", () => openBookModal(null));

  document.getElementById("bookForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const payload = {
      bookName: form.bookName.value.trim(),
      author: form.author.value.trim(),
      publisher: form.publisher.value.trim(),
      isbn: form.isbn.value.trim(),
      categoryId: form.categoryId.value,
      price: Number(form.price.value),
      stock: Number(form.stock.value),
      description: form.description.value.trim(),
    };
    /**
     * 接口对接位置：AdminAPI.books.create() / AdminAPI.books.update()
     * 新增：POST /api/admin/books   修改：PUT /api/admin/books/{bookItemId}
     * 请求体字段参考 book_infos / book_items 表设计
     */
    try {
      if (editingBookId) {
        await AdminAPI.books.update(editingBookId, payload);
      } else {
        await AdminAPI.books.create(payload);
      }
      showToast("图书信息操作成功", "success");
      closeModal("bookModal");
      loadBooks();
    } catch (err) {
      // 例如 ISBN 重复等业务校验错误，由 AdminAPI.books.create() 抛出，此处弹窗提示具体原因
      showToast(err.message || "操作失败，请稍后重试！", "danger");
    }
  });

  loadBooks();
});
