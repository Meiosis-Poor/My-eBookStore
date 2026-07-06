/**
 * cart.js — 购物车页面逻辑
 * 依赖：api.js、mock-data.js、common.js
 * 对应用例：4.2.3 Add Book to Cart（购物车管理部分）
 */
let cartItems = [];
let selectedIds = new Set();

function groupByStore(items) {
  const map = new Map();
  items.forEach((item) => {
    const storeName = (item.book && item.book.storeName) || "未知店铺";
    if (!map.has(storeName)) map.set(storeName, []);
    map.get(storeName).push(item);
  });
  return map;
}

function calcTotal() {
  return cartItems
    .filter((item) => selectedIds.has(String(item.bookItemId)))
    .reduce((sum, item) => sum + (item.book ? item.book.price : 0) * item.quantity, 0);
}

function renderCart() {
  const container = document.getElementById("cartList");
  const emptyState = document.getElementById("cartEmptyState");

  if (cartItems.length === 0) {
    container.innerHTML = "";
    emptyState.classList.remove("hidden");
    updateSummary();
    return;
  }
  emptyState.classList.add("hidden");

  const grouped = groupByStore(cartItems);
  let html = "";
  grouped.forEach((items, storeName) => {
    html += `
      <div class="cart-store-group card">
        <div class="store-title">
          <input type="checkbox" class="store-checkbox" data-store="${storeName}" />
          🏬 ${storeName}
        </div>
        <table class="cart-table">
          <thead>
            <tr><th></th><th>商品</th><th>单价</th><th>数量</th><th>小计</th><th>操作</th></tr>
          </thead>
          <tbody>
            ${items
              .map(
                (item) => `
              <tr data-id="${item.bookItemId}">
                <td><input type="checkbox" class="item-checkbox" value="${item.bookItemId}" ${selectedIds.has(String(item.bookItemId)) ? "checked" : ""} /></td>
                <td>
                  <div class="cart-product">
                    <div class="mini-cover">${(item.book && item.book.cover) || "📘"}</div>
                    <div>
                      <div style="font-weight:600">${item.book ? item.book.bookName : "商品 " + item.bookItemId}</div>
                      <div class="text-muted" style="font-size:12px">${item.book ? item.book.author : ""}</div>
                    </div>
                  </div>
                </td>
                <td>${formatPrice(item.book ? item.book.price : 0)}</td>
                <td>
                  <div class="qty-stepper">
                    <button type="button" class="qty-minus">−</button>
                    <input type="number" class="qty-input" value="${item.quantity}" min="1" />
                    <button type="button" class="qty-plus">＋</button>
                  </div>
                </td>
                <td>${formatPrice((item.book ? item.book.price : 0) * item.quantity)}</td>
                <td><button type="button" class="btn-text remove-item">删除</button></td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
  });
  container.innerHTML = html;
  bindRowEvents();
}

function syncStoreCheckboxes() {
  document.querySelectorAll(".cart-store-group").forEach((group) => {
    const itemBoxes = [...group.querySelectorAll(".item-checkbox")];
    group.querySelector(".store-checkbox").checked = itemBoxes.length > 0 && itemBoxes.every((cb) => cb.checked);
  });
}

function bindRowEvents() {
  document.querySelectorAll(".item-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) selectedIds.add(cb.value);
      else selectedIds.delete(cb.value);
      syncStoreCheckboxes();
      syncSelectAll();
      updateSummary();
    });
  });

  document.querySelectorAll(".store-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      const row = cb.closest(".cart-store-group");
      row.querySelectorAll(".item-checkbox").forEach((itemCb) => {
        itemCb.checked = cb.checked;
        if (cb.checked) selectedIds.add(itemCb.value);
        else selectedIds.delete(itemCb.value);
      });
      syncSelectAll();
      updateSummary();
    });
  });

  // 初次渲染 / 数据变更重渲染后，依据当前选中状态同步“店铺全选”复选框
  syncStoreCheckboxes();

  document.querySelectorAll("tr[data-id]").forEach((row) => {
    const bookItemId = row.dataset.id;
    row.querySelector(".qty-minus").addEventListener("click", () => changeQty(bookItemId, -1, row));
    row.querySelector(".qty-plus").addEventListener("click", () => changeQty(bookItemId, 1, row));
    row.querySelector(".qty-input").addEventListener("change", async (e) => {
      const val = Math.max(1, Number(e.target.value) || 1);
      await CartAPI.updateQuantity(bookItemId, val);
      await reload();
    });
    row.querySelector(".remove-item").addEventListener("click", async () => {
      await CartAPI.remove(bookItemId);
      showToast("已从购物车移除", "success");
      document.dispatchEvent(new CustomEvent("cart:updated"));
      await reload();
    });
  });
}

async function changeQty(bookItemId, delta, row) {
  const input = row.querySelector(".qty-input");
  const newVal = Math.max(1, Number(input.value) + delta);
  input.value = newVal;
  await CartAPI.updateQuantity(bookItemId, newVal);
  await reload();
}

function syncSelectAll() {
  const selectAll = document.getElementById("selectAllCheckbox");
  selectAll.checked = cartItems.length > 0 && cartItems.every((i) => selectedIds.has(String(i.bookItemId)));
}

function updateSummary() {
  const total = calcTotal();
  document.getElementById("selectedCount").textContent = selectedIds.size;
  document.getElementById("cartTotalAmount").textContent = formatPrice(total);
  document.getElementById("goCheckoutBtn").disabled = selectedIds.size === 0;
}

async function reload() {
  cartItems = await CartAPI.list();
  // 首次加载时默认全选
  if (selectedIds.size === 0) {
    cartItems.forEach((i) => selectedIds.add(String(i.bookItemId)));
  }
  renderCart();
  syncSelectAll();
  updateSummary();
  document.dispatchEvent(new CustomEvent("cart:updated"));
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!requireLogin("请先登录后查看购物车")) return;

  document.getElementById("selectAllCheckbox").addEventListener("change", (e) => {
    if (e.target.checked) cartItems.forEach((i) => selectedIds.add(String(i.bookItemId)));
    else selectedIds.clear();
    renderCart();
    updateSummary();
  });

  document.getElementById("goCheckoutBtn").addEventListener("click", () => {
    if (selectedIds.size === 0) return;
    /**
     * 将选中的购物车项传递给结算页。真实对接后端时，可直接在提交订单接口
     * OrderAPI.create({ cartItemIds }) 中传入这些 ID，无需依赖本地存储中转。
     */
    localStorage.setItem("ebs_checkout_items", JSON.stringify(Array.from(selectedIds)));
    window.location.href = "checkout.html";
  });

  await reload();
});
