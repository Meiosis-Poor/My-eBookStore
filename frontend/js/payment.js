/**
 * payment.js — 支付页逻辑
 * 依赖：api.js、common.js
 * 对应用例：4.2.4 Submit Order and Payment（支付部分）
 */
let selectedMethod = "alipay";

document.addEventListener("DOMContentLoaded", () => {
  if (!requireLogin("请先登录")) return;

  const orderId = qs("orderId");
  const amount = qs("amount") || "0.00";
  const orderNo = qs("orderNo") || "-";

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

    // 仅用于前端演示：勾选后本地模拟支付失败结果，不发起真实请求；对接后端后可删除该分支。
    const simulateFail = document.getElementById("simulateFailCheckbox").checked;

    try {
      let result;
      if (simulateFail) {
        result = { paymentStatus: "fail" };
      } else {
        /**
         * 接口对接位置：OrderAPI.pay()
         * 请求：POST /api/orders/{orderId}/pay { paymentMethod }
         * 响应：{ paymentStatus: "success"|"fail", paymentNo? }
         */
        result = await OrderAPI.pay(orderId, selectedMethod);
      }
      const status = result.paymentStatus === "success" ? "success" : "fail";
      window.location.href = `payment-result.html?status=${status}&orderId=${orderId}&orderNo=${orderNo}&amount=${amount}`;
    } catch (err) {
      showToast(err.message || "支付失败，请重新尝试！", "danger");
      btn.disabled = false;
      btn.textContent = "确认支付";
    }
  });
});
