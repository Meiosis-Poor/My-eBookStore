/**
 * admin/promotions.js — 后台促销活动管理页逻辑
 * 依赖：../api.js、../common.js、common.js（本目录）
 * 对应用例：4.3.5 Promotion Activity Management 促销活动管理
 * 说明：
 * - 书店管理员：可选择是否参与活动、设置参与书目、设置店铺代金券金额与数量。
 * - 后台管理员：可新增/修改活动类型与内容、设置平台代金券、调整积分兑换奖品。
 */
let editingActivityId = null;
let editingRewardId = null;

function activityCardHtml(a, role) {
  const sellerControls = `
    <div class="mt-4" data-role-only="seller">
      <label class="flex items-center gap-2" style="font-size:13px">
        <label class="switch"><input type="checkbox" class="participate-toggle" /><span class="slider"></span></label>
        参与本活动
      </label>
      <div class="form-row mt-2">
        <div class="form-group">
          <label class="form-label">参与书目（ISBN 或商品 ID，逗号分隔）</label>
          <input type="text" class="form-control participate-books" placeholder="如：978-7-100001, 1001" />
        </div>
        <div class="form-group">
          <label class="form-label">店铺券金额/数量</label>
          <div class="flex gap-2">
            <input type="number" class="form-control coupon-amount" placeholder="金额" style="width:50%" />
            <input type="number" class="form-control coupon-qty" placeholder="数量" style="width:50%" />
          </div>
        </div>
      </div>
      <button type="button" class="btn btn-primary btn-sm save-participation" data-id="${a.activityId}">保存参与设置</button>
    </div>`;

  const adminControls = `
    <div class="row-actions mt-4" data-role-only="platform_admin">
      <button data-action="edit-activity" data-id="${a.activityId}">编辑活动</button>
    </div>`;

  return `
    <div class="card activity-card">
      <div class="activity-body">
        <div class="flex justify-between items-center">
          <div style="font-weight:700">${a.activityName}</div>
          <span class="badge badge-info">${a.activityType}</span>
        </div>
        <p class="text-muted mt-2" style="font-size:13px">${a.description}</p>
        <p class="text-muted" style="font-size:12px">${a.startTime} 至 ${a.endTime}</p>
        ${sellerControls}
        ${adminControls}
      </div>
    </div>`;
}

async function loadActivities(role) {
  const list = await AdminAPI.promotions.listActivities();
  const container = document.getElementById("adminActivityList");
  container.innerHTML = list.map((a) => activityCardHtml(a, role)).join("");

  if (role !== "platform_admin") {
    container.querySelectorAll('[data-role-only="platform_admin"]').forEach((el) => el.classList.add("hidden"));
  }
  if (role !== "seller") {
    container.querySelectorAll('[data-role-only="seller"]').forEach((el) => el.classList.add("hidden"));
  }

  container.querySelectorAll(".save-participation").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const card = btn.closest(".activity-card");
      const payload = {
        participate: card.querySelector(".participate-toggle").checked,
        books: card.querySelector(".participate-books").value.split(",").map((s) => s.trim()).filter(Boolean),
        couponAmount: Number(card.querySelector(".coupon-amount").value) || 0,
        couponQuantity: Number(card.querySelector(".coupon-qty").value) || 0,
      };
      await AdminAPI.promotions.setStoreParticipation(btn.dataset.id, payload);
      showToast("促销活动设置成功", "success");
      loadActivities(role);
    });
  });

  container.querySelectorAll('[data-action="edit-activity"]').forEach((btn) => {
    btn.addEventListener("click", () => openActivityModal(list.find((a) => String(a.activityId) === btn.dataset.id)));
  });
}

function openActivityModal(activity) {
  editingActivityId = activity ? activity.activityId : null;
  const form = document.getElementById("activityForm");
  form.reset();
  document.getElementById("activityModalTitle").textContent = activity ? "编辑活动" : "新增活动";
  if (activity) {
    form.activityName.value = activity.activityName;
    form.activityType.value = activity.activityType;
    form.description.value = activity.description;
    form.startTime.value = activity.startTime;
    form.endTime.value = activity.endTime;
  }
  openModal("activityModal");
}

function rewardCardRowHtml(r) {
  return `
    <tr>
      <td>${r.rewardName}</td>
      <td>${r.rewardType === "coupon" ? "代金券" : "实物奖品"}</td>
      <td>${r.requiredPoints}</td>
      <td>Lv.${r.requiredLevel}</td>
      <td>${r.stock}</td>
      <td class="row-actions"><button data-action="edit-reward" data-id="${r.rewardId}">编辑</button></td>
    </tr>`;
}

let rewardsCache = [];
async function loadRewards() {
  rewardsCache = await PromotionAPI.listRewards();
  document.getElementById("rewardsTableBody").innerHTML = rewardsCache.map(rewardCardRowHtml).join("");
  document.querySelectorAll('[data-action="edit-reward"]').forEach((btn) => {
    btn.addEventListener("click", () => openRewardModal(rewardsCache.find((r) => String(r.rewardId) === btn.dataset.id)));
  });
}

function openRewardModal(reward) {
  editingRewardId = reward ? reward.rewardId : null;
  const form = document.getElementById("rewardForm");
  form.reset();
  document.getElementById("rewardModalTitle").textContent = reward ? "编辑奖品" : "新增奖品";
  if (reward) {
    form.rewardName.value = reward.rewardName;
    form.rewardType.value = reward.rewardType;
    form.requiredPoints.value = reward.requiredPoints;
    form.requiredLevel.value = reward.requiredLevel;
    form.stock.value = reward.stock;
  }
  openModal("rewardModal");
}

document.addEventListener("DOMContentLoaded", () => {
  const user = initAdminShell("promotions");
  if (!user) return;

  loadActivities(user.userType);
  if (user.userType === "platform_admin") loadRewards();

  document.querySelectorAll(".admin-tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".admin-tabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".promo-admin-panel").forEach((p) => p.classList.add("hidden"));
      document.getElementById(btn.dataset.panel).classList.remove("hidden");
    });
  });

  const addActivityBtn = document.getElementById("addActivityBtn");
  if (addActivityBtn) addActivityBtn.addEventListener("click", () => openActivityModal(null));
  document.getElementById("activityForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const payload = {
      activityId: editingActivityId || undefined,
      activityName: form.activityName.value.trim(),
      activityType: form.activityType.value,
      description: form.description.value.trim(),
      startTime: form.startTime.value,
      endTime: form.endTime.value,
    };
    await AdminAPI.promotions.saveActivity(payload);
    showToast("促销活动设置成功", "success");
    closeModal("activityModal");
    loadActivities(user.userType);
  });

  const platformCouponForm = document.getElementById("platformCouponForm");
  if (platformCouponForm) platformCouponForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    await AdminAPI.promotions.savePlatformCoupon({
      couponName: form.couponName.value.trim(),
      amount: Number(form.amount.value),
      minAmount: Number(form.minAmount.value),
      quantity: Number(form.quantity.value),
    });
    showToast("平台代金券设置已保存", "success");
    form.reset();
    loadActivities(user.userType);
  });

  const addRewardBtn = document.getElementById("addRewardBtn");
  if (addRewardBtn) addRewardBtn.addEventListener("click", () => openRewardModal(null));
  document.getElementById("rewardForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    await AdminAPI.promotions.saveReward({
      rewardId: editingRewardId || undefined,
      rewardName: form.rewardName.value.trim(),
      rewardType: form.rewardType.value,
      requiredPoints: Number(form.requiredPoints.value),
      requiredLevel: Number(form.requiredLevel.value),
      stock: Number(form.stock.value),
    });
    showToast("积分兑换奖品设置成功", "success");
    closeModal("rewardModal");
    loadRewards();
  });
});
