/**
 * admin/users.js — 后台用户管理页逻辑
 * 依赖：../api.js、../common.js、common.js（本目录）
 * 对应用例：4.3.3 User Management 用户管理
 * 说明：书店管理员仅能查看购买过本店图书的用户，并可将其加入本店黑名单；
 * 后台管理员可对全平台用户执行封禁/解封操作（对应超过10家店铺拉黑自动平台封禁的规则）。
 */
let usersCache = [];
let blacklistTargetId = null;

function renderUsersTable(list, role) {
  const tbody = document.getElementById("usersTableBody");
  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted" style="padding:32px">暂无用户数据</td></tr>`;
    return;
  }
  tbody.innerHTML = list
    .map(
      (u) => `
    <tr>
      <td>${u.nickname}（${u.userName}）</td>
      <td>${u.registeredAt}</td>
      <td>
        ${
          role === "platform_admin"
            ? `<span class="badge badge-${u.status === "active" ? "success" : "danger"}">${u.status === "active" ? "正常" : "已封禁"}</span>`
            : `<span class="badge badge-${u.isBlacklisted ? "danger" : "success"}">${u.isBlacklisted ? "已拉黑" : "正常"}</span>`
        }
      </td>
      <td>
        <div class="row-actions">
          ${
            role === "platform_admin"
              ? `<button data-action="toggle-status" data-id="${u.userId}" data-status="${u.status}" class="${u.status === "active" ? "danger" : ""}">${u.status === "active" ? "封禁账号" : "解封账号"}</button>`
              : u.isBlacklisted
              ? `<button data-action="unblacklist" data-id="${u.userId}">解除黑名单</button>`
              : `<button data-action="blacklist" data-id="${u.userId}" class="danger">加入本店黑名单</button>`
          }
        </div>
      </td>
    </tr>`
    )
    .join("");

  tbody.querySelectorAll('[data-action="toggle-status"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      const nextStatus = btn.dataset.status === "active" ? "banned" : "active";
      await AdminAPI.users.setStatus(btn.dataset.id, nextStatus);
      showToast("用户管理操作成功", "success");
      loadUsers();
    });
  });
  tbody.querySelectorAll('[data-action="blacklist"]').forEach((btn) => {
    btn.addEventListener("click", () => {
      blacklistTargetId = btn.dataset.id;
      document.getElementById("blacklistReason").value = "";
      openModal("blacklistModal");
    });
  });
  tbody.querySelectorAll('[data-action="unblacklist"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      await AdminAPI.users.removeFromStoreBlacklist(btn.dataset.id);
      showToast("已解除本店黑名单", "success");
      loadUsers();
    });
  });
}

async function loadUsers() {
  const user = getCurrentUser();
  const keyword = document.getElementById("userSearchInput").value.trim();
  const res = await AdminAPI.users.list({ keyword });
  usersCache = res.list;
  renderUsersTable(usersCache, user.userType);
}

document.addEventListener("DOMContentLoaded", () => {
  const user = initAdminShell("users");
  if (!user) return;

  document.getElementById("userSearchInput").addEventListener("input", debounce(loadUsers, 350));

  document.getElementById("confirmBlacklistBtn").addEventListener("click", async () => {
    const reason = document.getElementById("blacklistReason").value.trim();
    /**
     * 接口对接位置：AdminAPI.users.addToStoreBlacklist()
     * 请求：POST /api/admin/users/{userId}/blacklist { reason }
     * 备注：当同一用户被超过 10 家店铺拉黑时，后端应自动将其加入平台封禁名单。
     */
    await AdminAPI.users.addToStoreBlacklist(blacklistTargetId, reason);
    showToast("已加入本店黑名单", "success");
    closeModal("blacklistModal");
    loadUsers();
  });

  loadUsers();
});
