/**
 * orders.js — 我的订单列表页逻辑
 * 依赖：api.js、common.js
 * 对应用例：4.2.5 Query Orders 订单查询
 */
const STATUS_TABS = [
  { key: "all", label: "全部" },
  { key: "pending_payment", label: "待支付" },
  { key: "shipped", label: "待收货" },
  { key: "completed", label: "已完成" },
  { key: "refunding", label: "退款中" },
];

function orderActionsHtml(order) {
  if (order.orderStatus === "pending_payment") {
    return `
      <button class="btn btn-outline btn-sm" data-action="cancel" data-id="${order.orderId}">取消订单</button>
      <a class="btn btn-primary btn-sm" href="payment.html?orderId=${order.orderId}&orderNo=${order.orderNo}&amount=${order.actualAmount}">去支付</a>`;
  }
  if (order.orderStatus === "completed" || order.orderStatus === "shipped") {
    return `
      <button class="btn btn-outline btn-sm" data-action="refund" data-id="${order.orderId}">申请退款</button>
      <a class="btn btn-primary btn-sm" href="order-detail.html?id=${order.orderId}">查看详情</a>`;
  }
  return `<a class="btn btn-primary btn-sm" href="order-detail.html?id=${order.orderId}">查看详情</a>`;
}

function renderOrders(list) {
  const container = document.getElementById("orderList");
  const empty = document.getElementById("orderEmptyState");
  if (list.length === 0) {
    container.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  container.innerHTML = list
    .map(
      (order) => `
    <div class="card order-card">
      <div class="order-card-header">
        <span>订单号：${order.orderNo} · ${formatDate(order.createdTime)}</span>
        <span class="badge badge-${order.orderStatus === "completed" ? "success" : order.orderStatus === "refunding" ? "warning" : "info"}">${order.statusLabel}</span>
      </div>
      <div class="order-card-body">
        ${order.items
          .map(
            (it) => `
          <div class="order-item-row">
            <div class="mini-cover">${it.cover}</div>
            <div style="flex:1">${it.bookName} × ${it.quantity}</div>
            <div>${formatPrice(it.unitPrice * it.quantity)}</div>
          </div>`
          )
          .join("")}
      </div>
      <div class="order-card-footer">
        <span>实付：<b>${formatPrice(order.actualAmount)}</b></span>
        ${orderActionsHtml(order)}
      </div>
    </div>`
    )
    .join("");

  container.querySelectorAll('[data-action="cancel"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      await OrderAPI.cancel(btn.dataset.id);
      showToast("订单已取消", "success");
      loadOrders(currentStatus);
    });
  });
  container.querySelectorAll('[data-action="refund"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      await OrderAPI.requestRefund(btn.dataset.id, "用户申请退款");
      showToast("退款申请已提交", "success");
      loadOrders(currentStatus);
    });
  });
}

let currentStatus = "all";
async function loadOrders(status) {
  currentStatus = status;
  const res = await OrderAPI.list({ status });
  renderOrders(res.list || []);
}

document.addEventListener("DOMContentLoaded", async () => {
  await initAccountSidebar("orders");
  if (!getCurrentUser()) return;

  const tabsEl = document.getElementById("orderStatusTabs");
  tabsEl.innerHTML = STATUS_TABS.map(
    (t, idx) => `<button class="${idx === 0 ? "active" : ""}" data-status="${t.key}">${t.label}</button>`
  ).join("");
  tabsEl.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      tabsEl.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadOrders(btn.dataset.status);
    });
  });

  loadOrders("all");
});
