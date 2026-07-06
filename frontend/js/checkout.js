/**
 * checkout.js — 订单确认页逻辑
 * 依赖：api.js、mock-data.js、common.js
 * 对应用例：4.2.4 Submit Order and Payment（下单部分）
 */
let checkoutItems = [];
let selectedCoupon = null;

function renderOrderItems() {
  const container = document.getElementById("checkoutItemList");
  container.innerHTML = checkoutItems
    .map(
      (item) => `
      <div class="order-item-row">
        <div class="mini-cover">${(item.book && item.book.cover) || "📘"}</div>
        <div style="flex:1">
          <div style="font-weight:600">${item.book ? item.book.bookName : "商品"}</div>
          <div class="text-muted" style="font-size:12px">${item.book ? item.book.storeName : ""} × ${item.quantity}</div>
        </div>
        <div>${formatPrice((item.book ? item.book.price : 0) * item.quantity)}</div>
      </div>`
    )
    .join("");
}

function calcSubtotal() {
  return checkoutItems.reduce((sum, item) => sum + (item.book ? item.book.price : 0) * item.quantity, 0);
}

function updateSummary() {
  const subtotal = calcSubtotal();
  const discount = selectedCoupon ? selectedCoupon.amount : 0;
  const total = Math.max(0, subtotal - discount);
  document.getElementById("summarySubtotal").textContent = formatPrice(subtotal);
  document.getElementById("summaryDiscount").textContent = `- ${formatPrice(discount)}`;
  document.getElementById("summaryTotal").textContent = formatPrice(total);
  document.getElementById(
    "couponLabel"
  ).textContent = selectedCoupon ? `${selectedCoupon.couponName}（-¥${selectedCoupon.amount}）` : "选择可用代金券";
}

async function loadCoupons() {
  const list = await PromotionAPI.myCoupons("unused");
  const box = document.getElementById("couponList");
  box.innerHTML = `
    <label class="filter-option"><input type="radio" name="couponRadio" value="" checked /> 不使用代金券</label>
    ${list
      .map(
        (c) => `
      <label class="filter-option">
        <input type="radio" name="couponRadio" value="${c.couponId}" />
        ${c.couponName}（满${c.minAmount}减${c.amount}）
      </label>`
      )
      .join("")}`;
  box.querySelectorAll('input[name="couponRadio"]').forEach((input) => {
    input.addEventListener("change", () => {
      selectedCoupon = list.find((c) => String(c.couponId) === input.value) || null;
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!requireLogin("请先登录后再结算订单")) return;

  const selectedIds = JSON.parse(localStorage.getItem("ebs_checkout_items") || "[]");
  const allCart = await CartAPI.list();
  checkoutItems = allCart.filter((item) => selectedIds.includes(String(item.bookItemId)));

  if (checkoutItems.length === 0) {
    showToast("购物车中暂无商品！", "warning");
    setTimeout(() => (window.location.href = "cart.html"), 800);
    return;
  }

  renderOrderItems();
  updateSummary();

  // 事件监听需在同步阶段立即绑定，不能等待优惠券加载完成后再绑定，
  // 否则若接口响应较慢，用户在此期间点击“提交订单”将不会有任何反应。
  document.getElementById("couponSelect").addEventListener("click", () => openModal("couponModal"));
  document.getElementById("confirmCouponBtn").addEventListener("click", () => {
    updateSummary();
    closeModal("couponModal");
  });

  loadCoupons();

  document.getElementById("submitOrderBtn").addEventListener("click", async () => {
    const subtotal = calcSubtotal();
    const discount = selectedCoupon ? selectedCoupon.amount : 0;
    const btn = document.getElementById("submitOrderBtn");
    btn.disabled = true;
    btn.textContent = "提交中...";
    try {
      /**
       * 接口对接位置：OrderAPI.create()
       * 请求：POST /api/orders { cartItemIds, couponId?, addressId? }
       * 响应：{ orderId, orderNo, totalAmount, discountAmount, actualAmount }
       * 备选事件流：E-1 购物车为空 / E-2 库存不足 已在购物车/本页前置校验
       */
      const order = await OrderAPI.create({
        cartItemIds: selectedIds,
        couponId: selectedCoupon ? selectedCoupon.couponId : undefined,
        totalAmount: subtotal,
        discountAmount: discount,
        actualAmount: Math.max(0, subtotal - discount),
      });
      selectedIds.forEach((id) => CartAPI.remove(id));
      localStorage.removeItem("ebs_checkout_items");
      window.location.href = `payment.html?orderId=${order.orderId}&amount=${order.actualAmount}&orderNo=${order.orderNo}`;
    } catch (err) {
      showToast(err.message || "提交订单失败，请稍后重试！", "danger");
      btn.disabled = false;
      btn.textContent = "提交订单";
    }
  });
});
