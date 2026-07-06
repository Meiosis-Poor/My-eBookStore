/**
 * admin/store-profile.js — 后台“店铺信息设置”页逻辑（仅书店管理员可访问）
 * 依赖：../api.js、../mock-data.js、../common.js、common.js（本目录）
 * 说明：书店管理员在此维护本店的展示信息（店铺名称），
 * 该信息即为客户端 store.html 店铺主页展示的内容。
 */
document.addEventListener("DOMContentLoaded", async () => {
  const user = initAdminShell("store-profile");
  if (!user) return;
  if (user.userType !== "seller") {
    showToast("无权限执行此操作！", "danger");
    setTimeout(() => (window.location.href = "dashboard.html"), 800);
    return;
  }

  const form = document.getElementById("storeProfileForm");
  const previewLink = document.getElementById("previewStoreLink");
  previewLink.href = `../store.html?id=${user.storeId}`;

  const store = await StoreAPI.detail(user.storeId);
  form.storeName.value = store.storeName;
  document.getElementById("storeBookCount").textContent = store.bookCount;
  document.getElementById("storeSalesCount").textContent = store.salesCount;
  document.getElementById("storeCreatedTime").textContent = store.createdTime;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      storeName: form.storeName.value.trim(),
    };
    await StoreAPI.updateProfile(user.storeId, payload);

    // 同步更新当前会话中的 storeName，使侧边栏“当前角色”标签与顶部信息保持一致
    const sessionUser = getCurrentUser();
    sessionUser.storeName = payload.storeName;
    setSession(getToken(), sessionUser);
    document.querySelector("#adminRoleTag .role-name").textContent = `${payload.storeName} · 书店管理员`;

    showToast("店铺信息保存成功", "success");
  });
});
