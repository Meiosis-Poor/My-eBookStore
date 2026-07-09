/**
 * checkout.js — 订单确认页逻辑
 * 依赖：api.js、common.js
 * 对应用例：4.2.4 Submit Order and Payment（下单部分）
 */
let checkoutItems = [];
let selectedCoupon = null;
let addressList = [];
let selectedAddressId = null;

/* ---------- 收货地址：主页面展示卡片 ---------- */
function renderAddressCard() {
  const card = document.getElementById("checkoutAddressCard");
  const address = addressList.find((a) => String(a.addressId) === String(selectedAddressId));
  if (!address) {
    card.innerHTML = `
      <div class="text-muted">暂无收货地址，请先添加一个</div>
      <button type="button" class="btn-text" id="changeAddressBtn">添加地址</button>`;
  } else {
    card.innerHTML = `
      <div>
        <div style="font-weight:600">${address.recipientName} &nbsp;${maskPhone(address.phone)}</div>
        <div class="text-muted mt-2" style="font-size:13px">${address.addressDetail}${address.isDefault ? " · 默认地址" : ""}</div>
      </div>
      <button type="button" class="btn-text" id="changeAddressBtn">更换地址</button>`;
  }
  document.getElementById("changeAddressBtn").addEventListener("click", () => {
    renderAddressList();
    showAddressListView();
    openModal("addressModal");
  });
}

async function loadAddresses() {
  addressList = await AddressAPI.list();
  if (!addressList.find((a) => String(a.addressId) === String(selectedAddressId))) {
    const defaultAddress = addressList.find((a) => a.isDefault) || addressList[0];
    selectedAddressId = defaultAddress ? defaultAddress.addressId : null;
  }
  renderAddressCard();
}

/* ---------- 收货地址：弹窗内“选择地址”列表视图 ---------- */
function renderAddressList() {
  const box = document.getElementById("addressList");
  if (addressList.length === 0) {
    box.innerHTML = `<div class="text-muted" style="font-size:13px">暂无收货地址，请点击下方按钮新增</div>`;
  } else {
    box.innerHTML = addressList
      .map(
        (a) => `
      <label class="address-option">
        <input type="radio" name="addressRadio" value="${a.addressId}" ${String(a.addressId) === String(selectedAddressId) ? "checked" : ""} />
        <div class="address-option-info">
          <div><b>${a.recipientName}</b> &nbsp;${maskPhone(a.phone)} ${a.isDefault ? '<span class="badge badge-info">默认</span>' : ""}</div>
          <div class="text-muted" style="font-size:13px">${a.addressDetail}</div>
        </div>
        <div class="address-option-actions">
          <button type="button" class="btn-text" data-edit="${a.addressId}">编辑</button>
          <button type="button" class="btn-text" data-remove="${a.addressId}">删除</button>
        </div>
      </label>`
      )
      .join("");
  }

  box.querySelectorAll("[data-edit]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const address = addressList.find((a) => String(a.addressId) === btn.dataset.edit);
      showAddressFormView(address);
    });
  });
  box.querySelectorAll("[data-remove]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      await AddressAPI.remove(btn.dataset.remove);
      showToast("地址已删除", "success");
      await loadAddresses();
      renderAddressList();
    });
  });
}

/* ---------- 收货地址：弹窗内“新增 / 编辑地址”表单视图 ---------- */
function showAddressListView() {
  document.getElementById("addressModalTitle").textContent = "选择收货地址";
  document.getElementById("addressListView").hidden = false;
  document.getElementById("addressForm").hidden = true;
  document.getElementById("addressListFooter").hidden = false;
  document.getElementById("addressFormFooter").hidden = true;
}

function showAddressFormView(address) {
  const form = document.getElementById("addressForm");
  form.reset();
  form.addressId.value = address ? address.addressId : "";
  if (address) {
    form.recipientName.value = address.recipientName;
    form.phone.value = address.phone;
    form.addressDetail.value = address.addressDetail;
    form.isDefault.checked = !!address.isDefault;
  }
  document.getElementById("addressModalTitle").textContent = address ? "编辑收货地址" : "新增收货地址";
  document.getElementById("addressListView").hidden = true;
  form.hidden = false;
  document.getElementById("addressListFooter").hidden = true;
  document.getElementById("addressFormFooter").hidden = false;
}

function renderOrderItems() {
  const container = document.getElementById("checkoutItemList");
  container.innerHTML = checkoutItems
    .map(
      (item) => `
      <div class="order-item-row">
        <div class="mini-cover">${item.book.cover || "📘"}</div>
        <div style="flex:1">
          <div style="font-weight:600">${item.book.bookName}</div>
          <div class="text-muted" style="font-size:12px">${item.book.storeName} × ${item.quantity}</div>
        </div>
        <div>${formatPrice(item.book.price * item.quantity)}</div>
      </div>`
    )
    .join("");
}

function calcSubtotal() {
  return checkoutItems.reduce((sum, item) => sum + item.book.price * item.quantity, 0);
}

function validateCheckoutItems(items) {
  const invalid = items.find(
    (item) =>
      !item.book ||
      !item.book.bookName ||
      !item.book.storeName ||
      typeof item.book.price !== "number"
  );
  if (invalid) {
    throw new Error("购物车接口返回缺少书名、店铺名或价格，请检查后端 /api/cart 字段");
  }
}

/** 满减是否生效：需商品总额达到代金券的使用门槛（minAmount）才可计入优惠 */
function isCouponEligible(coupon, subtotal) {
  return !!coupon && subtotal >= coupon.minAmount;
}

function updateSummary() {
  const subtotal = calcSubtotal();
  const eligible = isCouponEligible(selectedCoupon, subtotal);
  const discount = eligible ? selectedCoupon.amount : 0;
  const total = Math.max(0, subtotal - discount);
  document.getElementById("summarySubtotal").textContent = formatPrice(subtotal);
  document.getElementById("summaryDiscount").textContent = `- ${formatPrice(discount)}`;
  document.getElementById("summaryTotal").textContent = formatPrice(total);
  document.getElementById("couponLabel").textContent = eligible
    ? `${selectedCoupon.couponName}（-¥${selectedCoupon.amount}）`
    : "选择可用代金券";
}

async function loadCoupons() {
  const list = await PromotionAPI.myCoupons("unused");
  const subtotal = calcSubtotal();
  const box = document.getElementById("couponList");
  box.innerHTML = `
    <label class="filter-option"><input type="radio" name="couponRadio" value="" checked /> 不使用代金券</label>
    ${list
      .map((c) => {
        const eligible = subtotal >= c.minAmount;
        return `
      <label class="filter-option ${eligible ? "" : "is-disabled"}">
        <input type="radio" name="couponRadio" value="${c.couponId}" ${eligible ? "" : "disabled"} />
        ${c.couponName}（满${c.minAmount}减${c.amount}）${eligible ? "" : `<span class="text-muted">（还差¥${(c.minAmount - subtotal).toFixed(2)}可用）</span>`}
      </label>`;
      })
      .join("")}`;
  box.querySelectorAll('input[name="couponRadio"]:not([disabled])').forEach((input) => {
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
  validateCheckoutItems(checkoutItems);

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

  // 收货地址：加载地址簿并渲染当前展示卡片；弹窗内的“更换地址”按钮由 renderAddressCard() 动态绑定
  loadAddresses();

  document.getElementById("confirmAddressBtn").addEventListener("click", () => {
    const checked = document.querySelector('input[name="addressRadio"]:checked');
    if (checked) selectedAddressId = checked.value;
    renderAddressCard();
    closeModal("addressModal");
  });
  document.getElementById("showAddAddressBtn").addEventListener("click", () => showAddressFormView(null));
  document.getElementById("saveAddressBtn").addEventListener("click", async () => {
    const form = document.getElementById("addressForm");
    if (!form.reportValidity()) return;
    const payload = {
      recipientName: form.recipientName.value.trim(),
      phone: form.phone.value.trim(),
      addressDetail: form.addressDetail.value.trim(),
      isDefault: form.isDefault.checked,
    };
    const addressId = form.addressId.value;
    if (addressId) {
      await AddressAPI.update(addressId, payload);
    } else {
      const res = await AddressAPI.create(payload);
      selectedAddressId = res.addressId;
    }
    showToast("地址已保存", "success");
    await loadAddresses();
    renderAddressList();
    showAddressListView();
  });

  document.getElementById("submitOrderBtn").addEventListener("click", async () => {
    const address = addressList.find((a) => String(a.addressId) === String(selectedAddressId));
    if (!address) {
      showToast("请先添加并选择收货地址！", "warning");
      return;
    }

    const subtotal = calcSubtotal();
    const discount = selectedCoupon ? selectedCoupon.amount : 0;
    const btn = document.getElementById("submitOrderBtn");
    btn.disabled = true;
    btn.textContent = "提交中...";
    try {
      /**
       * 接口对接位置：OrderAPI.create()
       * 请求：POST /api/orders { cartItemIds, couponId?, addressId, receiverName, receiverPhone, receiverAddress }
       * 响应：{ orderId, orderNo, totalAmount, discountAmount, actualAmount }
       * 备选事件流：E-1 购物车为空 / E-2 库存不足 已在购物车/本页前置校验
       */
      const order = await OrderAPI.create({
        cartItemIds: selectedIds,
        couponId: selectedCoupon ? selectedCoupon.couponId : undefined,
        addressId: address.addressId,
        receiverName: address.recipientName,
        receiverPhone: address.phone,
        receiverAddress: address.addressDetail,
        totalAmount: subtotal,
        discountAmount: discount,
        actualAmount: Math.max(0, subtotal - discount),
      });
      localStorage.removeItem("ebs_checkout_items");
      window.location.href = `payment.html?orderId=${order.orderId}&amount=${order.actualAmount}&orderNo=${order.orderNo}`;
    } catch (err) {
      showToast(err.message || "提交订单失败，请稍后重试！", "danger");
      btn.disabled = false;
      btn.textContent = "提交订单";
    }
  });
});
