/**
 * admin/stores.js — 后台店铺管理页逻辑（仅后台管理员可访问）
 * 依赖：../api.js、../common.js、common.js（本目录）
 * 对应用例：3.1 用户需求 2.3 后台管理员需求 —— 全平台店铺管理（开放/封禁店铺）
 */
function renderStoresTable(list) {
  const tbody = document.getElementById("storesTableBody");
  tbody.innerHTML = list
    .map(
      (s) => `
    <tr>
      <td>${s.storeName}</td>
      <td>${s.createdTime}</td>
      <td>${s.bookCount}</td>
      <td>${s.orderCount}</td>
      <td><span class="badge badge-${s.status === "active" ? "success" : "danger"}">${s.status === "active" ? "正常营业" : "已封禁"}</span></td>
      <td>
        <div class="row-actions">
          <button data-action="toggle" data-id="${s.storeId}" data-status="${s.status}" class="${s.status === "active" ? "danger" : ""}">
            ${s.status === "active" ? "封禁店铺" : "开放店铺"}
          </button>
        </div>
      </td>
    </tr>`
    )
    .join("");

  tbody.querySelectorAll('[data-action="toggle"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      const nextStatus = btn.dataset.status === "active" ? "banned" : "active";
      /**
       * 接口对接位置：AdminAPI.stores.setStatus()
       * 请求：PUT /api/admin/stores/{storeId}/status { status: "active"|"banned" }
       */
      await AdminAPI.stores.setStatus(btn.dataset.id, nextStatus);
      showToast(nextStatus === "active" ? "店铺已开放" : "店铺已封禁", "success");
      loadStores();
    });
  });
}

async function loadStores() {
  const res = await AdminAPI.stores.list();
  renderStoresTable(res.list);
}

document.addEventListener("DOMContentLoaded", () => {
  const user = initAdminShell("stores");
  if (!user) return;
  if (user.userType !== "platform_admin") {
    showToast("无权限执行此操作！", "danger");
    setTimeout(() => (window.location.href = "dashboard.html"), 800);
    return;
  }
  loadStores();
});
