/**
 * order-detail.js — 订单详情页逻辑
 * 依赖：api.js、common.js
 * 对应用例：4.2.5 Query Orders（订单详情部分）
 */
document.addEventListener("DOMContentLoaded", async () => {
  if (!requireLogin("请先登录后查看订单详情")) return;

  const orderId = qs("id");
  const order = await OrderAPI.detail(orderId);

  document.getElementById("orderNo").textContent = order.orderNo;
  document.getElementById("orderTime").textContent = formatDate(order.createdTime);
  document.getElementById("orderStatusBadge").textContent = order.statusLabel;
  document.getElementById("orderTotal").textContent = formatPrice(order.totalAmount);
  document.getElementById("orderDiscount").textContent = `- ${formatPrice(order.discountAmount)}`;
  document.getElementById("orderActual").textContent = formatPrice(order.actualAmount);

  document.getElementById("orderReceiverName").textContent = order.receiverName || "-";
  document.getElementById("orderReceiverPhone").textContent = order.receiverPhone ? maskPhone(order.receiverPhone) : "";
  document.getElementById("orderReceiverAddress").textContent = order.receiverAddress || "-";

  const canReview = ["completed", "shipped"].includes(order.orderStatus) || order.paymentStatus === "paid";
  document.getElementById("orderItemList").innerHTML = order.items
    .map(
      (it) => `
    <div class="order-item-row">
      <div class="mini-cover">${it.cover}</div>
      <div style="flex:1">
        <div style="font-weight:600">${it.bookName}</div>
        <div class="text-muted" style="font-size:12px">${formatPrice(it.unitPrice)} × ${it.quantity}</div>
        ${
          canReview
            ? `<form class="review-form mt-3" data-book-item-id="${it.bookItemId}">
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label">评分</label>
                    <select class="form-control" name="rating">
                      <option value="5">5 分</option>
                      <option value="4">4 分</option>
                      <option value="3">3 分</option>
                      <option value="2">2 分</option>
                      <option value="1">1 分</option>
                    </select>
                  </div>
                  <div class="form-group" style="flex:2">
                    <label class="form-label">评价</label>
                    <input class="form-control" name="content" maxlength="500" placeholder="写下这本书的阅读体验" />
                  </div>
                </div>
                <button type="submit" class="btn btn-outline btn-sm">提交评价</button>
              </form>`
            : ""
        }
      </div>
      <div>${formatPrice(it.unitPrice * it.quantity)}</div>
    </div>`
    )
    .join("");

  document.querySelectorAll(".review-form").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      try {
        await OrderAPI.submitReview(order.orderId, {
          bookItemId: form.dataset.bookItemId,
          rating: Number(form.rating.value),
          content: form.content.value.trim(),
        });
        showToast("评价已提交", "success");
        setTimeout(() => window.location.reload(), 600);
      } catch (err) {
        showToast(err.message || "提交评价失败", "danger");
        btn.disabled = false;
      }
    });
  });

  const actionBar = document.getElementById("orderActionBar");
  if (order.orderStatus === "pending_payment") {
    actionBar.innerHTML = `
      <a class="btn btn-primary" href="payment.html?orderId=${order.orderId}&orderNo=${order.orderNo}&amount=${order.actualAmount}">去支付</a>
      <button class="btn btn-outline" id="cancelBtn">取消订单</button>`;
    document.getElementById("cancelBtn").addEventListener("click", async () => {
      await OrderAPI.cancel(order.orderId);
      showToast("订单已取消", "success");
      setTimeout(() => window.location.reload(), 600);
    });
  } else if (order.orderStatus === "completed" || order.orderStatus === "shipped") {
    actionBar.innerHTML = `<button class="btn btn-outline" id="refundBtn">申请退款</button>`;
    document.getElementById("refundBtn").addEventListener("click", async () => {
      await OrderAPI.requestRefund(order.orderId, "用户申请退款");
      showToast("退款申请已提交", "success");
      setTimeout(() => window.location.reload(), 600);
    });
  }
});
