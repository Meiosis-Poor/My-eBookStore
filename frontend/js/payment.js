/**
 * payment.js — 支付页逻辑
 * 依赖：api.js、common.js
 * 对应用例：4.2.4 Submit Order and Payment（支付部分）
 */
let selectedMethod = "alipay";

document.addEventListener("DOMContentLoaded", async () => {
  if (!requireLogin("请先登录")) return;

  const orderId = qs("orderId");
  let amount = qs("amount") || "0.00";
  let orderNo = qs("orderNo") || "-";

  try {
    const order = await OrderAPI.detail(orderId);
    orderNo = order.orderNo;
    amount = order.actualAmount;
  } catch (err) {
    showToast(err.message || "订单信息加载失败", "danger");
  }

  document.getElementById("payOrderNo").textContent = orderNo;
  document.getElementById("payAmount").textContent = formatPrice(amount);

  document.querySelectorAll(".pay-method").forEach((el) => {
    el.addEventListener("click", () => {
      document.querySelectorAll(".pay-method").forEach((m) => m.classList.remove("selected"));
      el.classList.add("selected");
      selectedMethod = el.dataset.method;
    });
  });

  document.getElementById("confirmPayBtn").addEventListener("click", async () => {
    const btn = document.getElementById("confirmPayBtn");
    btn.disabled = true;
    btn.textContent = "支付处理中...";

    try {
      const result = await OrderAPI.pay(orderId, selectedMethod);
      const order = result.order || {};
      const nextOrderNo = order.orderNo || orderNo;
      const nextAmount = order.actualAmount || amount;
      const status = result.paymentStatus === "success" ? "success" : "fail";
      window.location.href = `payment-result.html?status=${status}&orderId=${orderId}&orderNo=${nextOrderNo}&amount=${nextAmount}`;
    } catch (err) {
      showToast(err.message || "支付失败，请重新尝试！", "danger");
      btn.disabled = false;
      btn.textContent = "确认支付";
    }
  });
});
