/**
 * promotions.js — 促销活动页逻辑
 * 依赖：api.js、mock-data.js、common.js
 * 对应用例：4.2.6 Promotion Activities 促销活动
 */
let currentUser = null;

function renderCheckinDays(continuousDays) {
  const wrap = document.getElementById("checkinDays");
  const dayInCycle = continuousDays % 7 || 7;
  wrap.innerHTML = Array.from({ length: 7 })
    .map((_, idx) => `<div class="checkin-day ${idx < dayInCycle ? "done" : ""}">第${idx + 1}天</div>`)
    .join("");
}

async function renderActivities() {
  const list = await PromotionAPI.listActivities();
  const container = document.getElementById("activityList");
  const iconMap = { checkin: "📅", quiz: "🧩", discount: "🏷️" };
  container.innerHTML = list
    .map(
      (a) => `
    <div class="card activity-card">
      <div class="activity-banner">${iconMap[a.activityType] || "🎉"}</div>
      <div class="activity-body">
        <div style="font-weight:700">${a.activityName}</div>
        <p class="text-muted mt-2" style="font-size:13px">${a.description}</p>
        <p class="text-muted" style="font-size:12px">${a.startTime} 至 ${a.endTime}</p>
        <button class="btn btn-accent btn-block mt-4" data-id="${a.activityId}" data-action="join">参与活动</button>
      </div>
    </div>`
    )
    .join("");

  container.querySelectorAll('[data-action="join"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const res = await PromotionAPI.joinActivity(btn.dataset.id);
        showToast(res.rewardCouponName ? `活动参与成功，获得【${res.rewardCouponName}】` : "活动参与成功", "success");
      } catch (err) {
        showToast(err.message || "当前无法参与该活动！", "danger");
      }
    });
  });
}

async function renderCoupons() {
  const list = await PromotionAPI.myCoupons("unused");
  const container = document.getElementById("couponGrid");
  if (list.length === 0) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">🎫</div><p>暂无可用代金券</p></div>`;
    return;
  }
  container.innerHTML = list
    .map(
      (c) => `
    <div class="coupon-card">
      <div class="coupon-amount"><span class="amt">${c.amount}</span><span style="font-size:11px">满${c.minAmount}可用</span></div>
      <div class="coupon-detail">
        <div class="coupon-name">${c.couponName}</div>
        <div class="coupon-cond">${c.couponType === "platform" ? "平台通用券" : "店铺专用券：" + c.storeName}</div>
        <div class="coupon-date">有效期至 ${c.validEnd}</div>
      </div>
    </div>`
    )
    .join("");
}

async function renderRewards() {
  const list = await PromotionAPI.listRewards();
  const container = document.getElementById("rewardGrid");
  container.innerHTML = list
    .map((r) => {
      const affordable = currentUser.availablePoints >= r.requiredPoints && currentUser.level >= r.requiredLevel;
      return `
      <div class="card reward-card">
        <div class="reward-icon">${r.rewardType === "coupon" ? "🎟️" : "🎁"}</div>
        <div style="font-weight:600">${r.rewardName}</div>
        <div class="reward-points">${r.requiredPoints} 积分</div>
        <div class="text-muted" style="font-size:12px">需 Lv.${r.requiredLevel} 及以上 · 剩余 ${r.stock}</div>
        <button class="btn ${affordable ? "btn-primary" : "btn-outline"} btn-block mt-4" data-id="${r.rewardId}" data-action="redeem" ${affordable ? "" : "disabled"}>
          ${affordable ? "立即兑换" : "积分/等级不足"}
        </button>
      </div>`;
    })
    .join("");

  container.querySelectorAll('[data-action="redeem"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      await PromotionAPI.redeemReward(btn.dataset.id);
      showToast("兑换成功，请前往个人中心查看", "success");
    });
  });
}

function bindTabStrip() {
  const tabs = document.querySelectorAll(".tab-strip button");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll(".promo-panel").forEach((p) => p.classList.add("hidden"));
      document.getElementById(tab.dataset.panel).classList.remove("hidden");
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!requireLogin("请先登录后参与促销活动")) return;

  currentUser = await UserAPI.me();
  document.getElementById("userPointsText").textContent = currentUser.availablePoints;
  document.getElementById("userLevelText").textContent = `Lv.${currentUser.level}`;
  renderCheckinDays(currentUser.continuousCheckinDays);

  document.getElementById("checkinBtn").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    if (btn.disabled) return;
    try {
      /**
       * 接口对接位置：PromotionAPI.checkin()
       * 请求：POST /api/promotions/checkin
       * 备选事件流 E-3：用户已完成签到，系统提示“奖励已领取，请勿重复操作！”
       */
      const res = await PromotionAPI.checkin();
      renderCheckinDays(res.continuousDays);
      btn.disabled = true;
      btn.textContent = "今日已签到";
      showToast(`签到成功，获得 ${res.rewardPoints} 积分`, "success");
    } catch (err) {
      showToast(err.message || "奖励已领取，请勿重复操作！", "warning");
    }
  });

  const weeklyBtn = document.getElementById("weeklyCouponBtn");
  if (currentUser.level >= 3) {
    weeklyBtn.classList.remove("hidden");
    weeklyBtn.addEventListener("click", async () => {
      await PromotionAPI.claimWeeklyCoupon();
      showToast("领取成功，代金券已发放到账户", "success");
    });
  }

  bindTabStrip();
  renderActivities();
  renderCoupons();
  renderRewards();
});
