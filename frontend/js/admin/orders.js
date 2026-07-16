/**
 * admin/orders.js — 后台订单管理页逻辑
 * 依赖：../api.js、../common.js、common.js（本目录）
 * 对应用例：4.3.2 Order Management 订单管理
 */
let adminOrdersCache = [];

function renderAdminOrders(list) {
  const tbody = document.getElementById("adminOrdersTableBody");
  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted" style="padding:32px">暂无订单数据</td></tr>`;
    return;
  }
  tbody.innerHTML = list
    .map(
      (o) => `
    <tr>
      <td>${o.orderNo}</td>
      <td>${formatDate(o.createdTime)}</td>
      <td>${o.items.length} 件商品</td>
      <td>${formatPrice(o.actualAmount)}</td>
      <td><span class="badge badge-${o.orderStatus === "completed" ? "success" : o.orderStatus === "refunding" ? "warning" : "info"}">${o.statusLabel}</span></td>
      <td>
        <div class="row-actions">
          <button data-action="detail" data-id="${o.orderId}">查看详情</button>
          ${o.orderStatus === "shipped" ? `<button data-action="complete" data-id="${o.orderId}">标记完成</button>` : ""}
          ${o.orderStatus === "refunding" ? `<button data-action="approve" data-id="${o.orderId}">同意退款</button><button data-action="reject" data-id="${o.orderId}" class="danger">驳回退款</button>` : ""}
        </div>
      </td>
    </tr>`
    )
    .join("");

  tbody.querySelectorAll('[data-action="detail"]').forEach((btn) => {
    btn.addEventListener("click", () => showOrderDetail(btn.dataset.id));
  });
  tbody.querySelectorAll('[data-action="complete"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      await AdminAPI.orders.updateStatus(btn.dataset.id, "completed");
      showToast("订单处理成功", "success");
      loadAdminOrders();
    });
  });
  tbody.querySelectorAll('[data-action="approve"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      await AdminAPI.orders.handleRefund(btn.dataset.id, true);
      showToast("退款已同意", "success");
      loadAdminOrders();
    });
  });
  tbody.querySelectorAll('[data-action="reject"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      await AdminAPI.orders.handleRefund(btn.dataset.id, false);
      showToast("已驳回退款申请", "success");
      loadAdminOrders();
    });
  });
}

function showOrderDetail(orderId) {
  const order = adminOrdersCache.find((o) => String(o.orderId) === String(orderId));
  if (!order) return;
  document.getElementById("orderDetailBody").innerHTML = `
    <div class="summary-line"><span>订单号</span><span>${order.orderNo}</span></div>
    <div class="summary-line"><span>下单时间</span><span>${formatDate(order.createdTime)}</span></div>
    <div class="summary-line"><span>订单状态</span><span>${order.statusLabel}</span></div>
    <hr style="border:none;border-top:1px dashed var(--color-border);margin:12px 0" />
    ${order.items
      .map(
        (it) => `
      <div class="order-item-row">
        <div class="mini-cover">${renderBookCover(it.cover, it.bookName)}</div>
        <div style="flex:1">${it.bookName} × ${it.quantity}</div>
        <div>${formatPrice(it.unitPrice * it.quantity)}</div>
      </div>`
      )
      .join("")}
    <div class="summary-line total mt-4"><span>实付金额</span><span class="amount">${formatPrice(order.actualAmount)}</span></div>`;
  openModal("orderDetailModal");
}

let currentAdminOrderStatus = "all";
async function loadAdminOrders() {
  const keyword = document.getElementById("orderSearchInput").value.trim();
  const res = await AdminAPI.orders.list({ status: currentAdminOrderStatus, keyword });
  adminOrdersCache =
    currentAdminOrderStatus === "all" ? res.list : res.list.filter((o) => o.orderStatus === currentAdminOrderStatus);
  renderAdminOrders(adminOrdersCache);
}

document.addEventListener("DOMContentLoaded", () => {
  const user = initAdminShell("orders");
  if (!user) return;

  document.getElementById("orderSearchInput").addEventListener("input", debounce(loadAdminOrders, 350));

  document.querySelectorAll(".admin-tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".admin-tabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentAdminOrderStatus = btn.dataset.status;
      loadAdminOrders();
    });
  });

  loadAdminOrders();
});
