/**
 * profile.js — 个人中心（我的资料）页面逻辑
 * 依赖：api.js、common.js
 */
document.addEventListener("DOMContentLoaded", async () => {
  await initAccountSidebar("profile");
  if (!getCurrentUser()) return;

  const user = await UserAPI.me();
  document.getElementById("statLevel").textContent = `Lv.${user.level}`;
  document.getElementById("statPoints").textContent = user.availablePoints;
  document.getElementById("statCheckinDays").textContent = user.continuousCheckinDays;

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
