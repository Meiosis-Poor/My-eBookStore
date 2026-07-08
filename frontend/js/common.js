/**
 * common.js
 * ------------------------------------------------------------------
 * 前台各页面公共交互逻辑：顶部导航登录态渲染、购物车角标、消息提示 Toast、
 * 模态框开关、金额/日期格式化、登录态校验跳转等。
 * 依赖 api.js（getCurrentUser / getToken / clearSession 等）先于本文件加载。
 * ------------------------------------------------------------------
 */

/* ---------- 消息提示 Toast ---------- */
function ensureToastStack() {
  let stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }
  return stack;
}

function showToast(message, type = "info", duration = 2600) {
  const stack = ensureToastStack();
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  stack.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("is-visible"));
  setTimeout(() => {
    toast.classList.remove("is-visible");
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

/* ---------- 模态框 ---------- */
function openModal(modalId) {
  const mask = document.getElementById(modalId);
  if (mask) mask.classList.add("is-open");
}
function closeModal(modalId) {
  const mask = document.getElementById(modalId);
  if (mask) mask.classList.remove("is-open");
}
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal-mask")) {
    e.target.classList.remove("is-open");
  }
});

/* ---------- 格式化工具 ---------- */
function formatPrice(value) {
  return `¥${Number(value || 0).toFixed(2)}`;
}
function formatDate(value) {
  if (!value) return "-";
  return String(value).replace("T", " ").slice(0, 16);
}
function debounce(fn, wait = 300) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}
function qs(name) {
  return new URLSearchParams(window.location.search).get(name);
}
function maskPhone(phone) {
  const str = String(phone || "");
  return str.length === 11 ? `${str.slice(0, 3)}****${str.slice(7)}` : str;
}

/* ---------- 登录态校验 ---------- */
/** 需要登录才能访问的操作：未登录时提示并跳转登录页，登录后可通过 redirect 参数回跳 */
function requireLogin(message = "请先登录后再进行该操作") {
  const user = getCurrentUser();
  if (!user) {
    showToast(message, "warning");
    setTimeout(() => {
      window.location.href = `login.html?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`;
    }, 600);
    return false;
  }
  return true;
}

/* ---------- 购物车角标 ---------- */
function getLocalCartCount() {
  try {
    const cart = JSON.parse(localStorage.getItem("ebs_cart") || "[]");
    return cart.reduce((sum, item) => sum + (item.quantity || 0), 0);
  } catch (err) {
    return 0;
  }
}
function refreshCartBadge() {
  const badge = document.getElementById("cartBadge");
  if (!badge) return;
  const count = getLocalCartCount();
  badge.textContent = count > 99 ? "99+" : String(count);
  badge.hidden = count === 0;
}
document.addEventListener("cart:updated", refreshCartBadge);

/* ---------- 顶部导航登录区域渲染 ---------- */
function renderHeaderAuthArea() {
  const area = document.getElementById("authArea");
  if (!area) return;
  const user = getCurrentUser();

  if (!user) {
    area.innerHTML = `
      <div class="guest-actions">
        <a class="btn btn-outline btn-sm" href="login.html">登录</a>
        <a class="btn btn-primary btn-sm" href="register.html">注册</a>
      </div>`;
    return;
  }

  area.innerHTML = `
    <div class="user-chip" id="userChipTrigger">
      <div class="avatar">${(user.nickname || user.userName || "U").slice(0, 1)}</div>
      <span>${user.nickname || user.userName}</span>
      <div class="user-menu" id="userChipMenu">
        <a href="profile.html">个人中心</a>
        <a href="orders.html">我的订单</a>
        <a href="promotions.html">促销活动</a>
        <button type="button" data-action="logout">退出登录</button>
      </div>
    </div>`;

  // 下拉菜单改为“点击展开 / 点击外部收起”，而非 :hover 触发——
  // 悬浮触发在头像与菜单之间存在间隙，鼠标移动经过间隙时会丢失 hover 状态，
  // 导致菜单在用户点击到菜单项之前就提前收起。
  const chip = document.getElementById("userChipTrigger");
  const menu = document.getElementById("userChipMenu");
  chip.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.classList.toggle("is-open");
  });
  document.addEventListener("click", () => menu.classList.remove("is-open"));

  area.querySelector('[data-action="logout"]').addEventListener("click", async () => {
    await AuthAPI.logout();
    showToast("已退出登录", "success");
    setTimeout(() => (window.location.href = "index.html"), 500);
  });
}

/* ---------- 图书卡片渲染（首页 / 搜索结果页共用） ---------- */
function renderBookCard(book) {
  return `
    <a class="book-card" href="book-detail.html?id=${book.bookItemId}">
      <div class="book-cover">
        ${book.stock === 0 ? '<span class="badge badge-danger stock-tag">已售罄</span>' : ""}
        <span>${book.cover || "📘"}</span>
      </div>
      <div class="book-info">
        <div class="book-title">${book.bookName}</div>
        <div class="book-meta">${book.author} · ${book.storeName || ""}</div>
        <div class="book-price-row">
          <span class="book-price">${Number(book.price).toFixed(2)}</span>
          <button type="button" class="icon-btn" data-action="add-cart" data-id="${book.bookItemId}" title="加入购物车">＋</button>
        </div>
      </div>
    </a>`;
}

/** 为容器内所有“加入购物车”按钮绑定事件（阻止冒泡，避免触发卡片跳转链接） */
function bindAddToCartButtons(container) {
  container.querySelectorAll('[data-action="add-cart"]').forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!requireLogin("请先登录后再加入购物车")) return;
      await CartAPI.add(btn.dataset.id, 1);
      document.dispatchEvent(new CustomEvent("cart:updated"));
      showToast("已加入购物车", "success");
    });
  });
}

/* ---------- 个人中心侧边栏（profile / orders / order-detail 共用） ---------- */
async function initAccountSidebar(activeNavKey) {
  const sidebar = document.getElementById("accountSidebar");
  if (!sidebar) return;
  if (!requireLogin("请先登录后查看个人中心")) return;

  document.querySelectorAll(".account-nav a[data-nav]").forEach((a) => {
    a.classList.toggle("active", a.dataset.nav === activeNavKey);
  });

  try {
    const user = await UserAPI.me();
    document.getElementById("accountAvatar").textContent = (user.nickname || user.userName || "U").slice(0, 1);
    document.getElementById("accountNickname").textContent = user.nickname || user.userName;
    document.getElementById("accountLevel").textContent = `Lv.${user.level}`;
    const pointsEl = document.getElementById("accountPoints");
    if (pointsEl) pointsEl.textContent = user.availablePoints;
  } catch (err) {
    console.error("加载用户信息失败", err);
  }
}

/* ---------- 页面初始化 ---------- */
document.addEventListener("DOMContentLoaded", () => {
  renderHeaderAuthArea();
  refreshCartBadge();

  // 移动端导航菜单开关（如页面包含 .nav-toggle 按钮）
  const navToggle = document.querySelector(".nav-toggle");
  if (navToggle) {
    navToggle.addEventListener("click", () => {
      document.querySelector(".main-nav")?.classList.toggle("is-open");
    });
  }
});
