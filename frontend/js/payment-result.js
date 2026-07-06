/**
 * payment-result.js — 支付结果页逻辑
 * 依赖：common.js
 */
document.addEventListener("DOMContentLoaded", () => {
  const status = qs("status") || "success";
  const orderNo = qs("orderNo") || "-";
  const amount = qs("amount") || "0.00";
  const orderId = qs("orderId") || "";

  const panel = document.getElementById("resultPanel");
  if (status === "success") {
    panel.classList.add("success");
    panel.querySelector(".result-icon").textContent = "✅";
    panel.querySelector("h2").textContent = "支付成功";
    panel.querySelector("p").textContent = `订单号 ${orderNo} 已支付 ${formatPrice(amount)}，感谢您的购买！`;
    panel.querySelector(".result-actions").innerHTML = `
      <a class="btn btn-outline" href="index.html">继续购物</a>
      <a class="btn btn-primary" href="order-detail.html?id=${orderId}">查看订单</a>`;
  } else {
    panel.classList.add("fail");
    panel.querySelector(".result-icon").textContent = "❌";
    panel.querySelector("h2").textContent = "支付失败，请重新尝试！";
    panel.querySelector("p").textContent = `订单号 ${orderNo}，订单未支付，可稍后继续支付或取消订单。`;
    panel.querySelector(".result-actions").innerHTML = `
      <a class="btn btn-outline" href="orders.html">订单未支付，可稍后继续支付或取消订单</a>
      <a class="btn btn-primary" href="payment.html?orderId=${orderId}&orderNo=${orderNo}&amount=${amount}">重新支付</a>`;
  }
});
