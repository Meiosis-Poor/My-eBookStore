/**
 * admin/common.js
 * ------------------------------------------------------------------
 * 后台管理端（书店管理员 / 后台管理员）公共壳逻辑：登录态校验与跳转、
 * 侧边栏角色标签渲染、按角色显示/隐藏专属菜单项、当前菜单高亮、
 * 退出登录、移动端侧边栏开关。
 * 依赖：../api.js、../common.js（Toast / 格式化等工具）先于本文件加载。
 * ------------------------------------------------------------------
 */

const ROLE_LABELS = {
  seller: "书店管理员",
  platform_admin: "后台管理员",
};

/** 校验当前登录角色是否具备后台访问权限，无权限则跳转回登录页 */
function guardAdminAccess() {
  const user = getCurrentUser();
  if (!user || (user.userType !== "seller" && user.userType !== "platform_admin")) {
    window.location.href = "../login.html";
    return null;
  }
  return user;
}

function initAdminShell(activeMenuKey) {
  const user = guardAdminAccess();
  if (!user) return;

  // 角色标签 + 当前用户名
  const roleTag = document.getElementById("adminRoleTag");
  if (roleTag) {
    roleTag.querySelector(".role-name").textContent =
      user.userType === "seller" ? `${user.storeName || "本店"} · ${ROLE_LABELS.seller}` : ROLE_LABELS.platform_admin;
  }
  const topUserEl = document.getElementById("adminTopUser");
  if (topUserEl) topUserEl.textContent = user.nickname || user.userName;

  // 仅后台管理员可见的菜单项 / 页面区块（如“店铺管理”、活动类型新增等）
  if (user.userType !== "platform_admin") {
    document.querySelectorAll('[data-role-only="platform_admin"]').forEach((el) => el.classList.add("hidden"));
  }
  // 仅书店管理员可见的区块（如“参与平台活动设置”）
  if (user.userType !== "seller") {
    document.querySelectorAll('[data-role-only="seller"]').forEach((el) => el.classList.add("hidden"));
  }

  // 当前菜单高亮
  document.querySelectorAll(".admin-menu a[data-nav]").forEach((a) => {
    a.classList.toggle("active", a.dataset.nav === activeMenuKey);
  });

  // 退出登录
  const logoutBtn = document.getElementById("adminLogoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      await AuthAPI.logout();
      window.location.href = "../login.html";
    });
  }

  // 移动端侧边栏开关
  const toggle = document.getElementById("adminSidebarToggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      document.querySelector(".admin-sidebar").classList.toggle("is-open");
    });
  }

  return user;
}
