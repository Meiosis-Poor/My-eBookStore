document.addEventListener("DOMContentLoaded", async () => {
  const orderId = qs("orderId") || "";
  const panel = document.getElementById("resultPanel");

  function renderSuccess(order) {
    panel.classList.remove("fail");
    panel.classList.add("success");
    panel.querySelector(".result-icon").textContent = "✅";
    panel.querySelector("h2").textContent = "支付成功";
    panel.querySelector("p").textContent = `订单号 ${order.orderNo} 已支付 ${formatPrice(order.actualAmount)}，感谢您的购买！`;
    panel.querySelector(".result-actions").innerHTML = `
      <a class="btn btn-outline" href="index.html">继续购物</a>
      <a class="btn btn-primary" href="order-detail.html?id=${order.orderId}">查看订单</a>`;
  }

  function renderPending(order) {
    panel.classList.remove("success");
    panel.classList.add("fail");
    panel.querySelector(".result-icon").textContent = "❌";
    panel.querySelector("h2").textContent = "订单未支付";
    panel.querySelector("p").textContent = `订单号 ${order.orderNo} 当前状态为 ${order.statusLabel || order.paymentStatus}。`;
    panel.querySelector(".result-actions").innerHTML = `
      <a class="btn btn-outline" href="orders.html">返回订单列表</a>
      <a class="btn btn-primary" href="payment.html?orderId=${order.orderId}&orderNo=${order.orderNo}&amount=${order.actualAmount}">重新支付</a>`;
  }

  try {
    const order = await OrderAPI.detail(orderId);
    if (order.paymentStatus === "paid" || order.orderStatus === "completed") {
      renderSuccess(order);
    } else {
      renderPending(order);
    }
  } catch (err) {
    panel.classList.add("fail");
    panel.querySelector(".result-icon").textContent = "❌";
    panel.querySelector("h2").textContent = "支付结果加载失败";
    panel.querySelector("p").textContent = err.message || "请稍后在订单列表中查看状态。";
    panel.querySelector(".result-actions").innerHTML = `<a class="btn btn-primary" href="orders.html">返回订单列表</a>`;
  }
});
