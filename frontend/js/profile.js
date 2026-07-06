/**
 * profile.js — 个人中心（我的资料）页面逻辑
 * 依赖：api.js、mock-data.js、common.js
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
