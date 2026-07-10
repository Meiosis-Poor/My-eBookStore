/**
 * profile.js — 个人中心（我的资料）页面逻辑
 * 依赖：api.js、common.js
 */
/** 会员等级所需累计积分阈值，与 database/07_triggers.sql 中 trg_AutoLevelUp 保持一致 */
const LEVEL_POINTS_THRESHOLDS = [0, 1000, 3000, 5000, 10000];

function renderLevelProgress(user) {
  const level = Number(user.level) || 1;
  const totalPoints = Number(user.totalPoints) || 0;
  const maxLevel = LEVEL_POINTS_THRESHOLDS.length;
  document.getElementById("levelProgressName").textContent = `Lv.${level}`;

  if (level >= maxLevel) {
    document.getElementById("levelProgressHint").textContent = "已达最高等级";
    document.getElementById("levelProgressFill").style.width = "100%";
    return;
  }

  const currentFloor = LEVEL_POINTS_THRESHOLDS[level - 1];
  const nextFloor = LEVEL_POINTS_THRESHOLDS[level];
  const percent = Math.max(0, Math.min(100, ((totalPoints - currentFloor) / (nextFloor - currentFloor)) * 100));
  document.getElementById("levelProgressHint").textContent = `距离 Lv.${level + 1} 还需 ${Math.max(0, nextFloor - totalPoints)} 积分`;
  document.getElementById("levelProgressFill").style.width = `${percent}%`;
}

document.addEventListener("DOMContentLoaded", async () => {
  await initAccountSidebar("profile");
  if (!getCurrentUser()) return;

  const user = await UserAPI.me();
  document.getElementById("statLevel").textContent = `Lv.${user.level}`;
  document.getElementById("statPoints").textContent = user.availablePoints;
  document.getElementById("statCheckinDays").textContent = user.continuousCheckinDays;
  renderLevelProgress(user);

  const form = document.getElementById("profileForm");
  form.nickname.value = user.nickname || "";
  form.phone.value = user.phone || "";
  form.email.value = user.email || "";

  try {
    const records = await UserAPI.points({ page: 1, pageSize: 20 });
    const list = document.getElementById("pointsRecordList");
    const rows = Array.isArray(records) ? records : records.list || [];
    list.innerHTML = rows.length
      ? rows
          .map(
            (record) => `
        <div class="order-item-row">
          <div style="flex:1">
            <div style="font-weight:600">${record.reason || "积分变动"}</div>
            <div class="text-muted" style="font-size:12px">${formatDate(record.createdTime)}</div>
          </div>
          <div style="font-weight:700;color:${Number(record.pointsChange) >= 0 ? "var(--color-success)" : "var(--color-danger)"}">
            ${Number(record.pointsChange) >= 0 ? "+" : ""}${record.pointsChange}
          </div>
        </div>`
          )
          .join("")
      : '<div class="empty-state">暂无积分流水</div>';
  } catch (err) {
    showToast(err.message || "积分流水加载失败", "danger");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    /**
     * 接口对接位置：UserAPI.updateProfile()
     * 请求：PUT /api/users/me { nickname?, phone?, email? }
     */
    await UserAPI.updateProfile({
      nickname: form.nickname.value.trim(),
      phone: form.phone.value.trim(),
      email: form.email.value.trim(),
    });
    showToast("个人资料已更新", "success");
  });
});
