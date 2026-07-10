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
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str ?? "");
  return div.innerHTML;
}
/** 当前登录用户是否为管理员角色（书店管理员 / 后台管理员），二者均不具备购买行为 */
function isAdminRole(user) {
  return !!user && (user.userType === "seller" || user.userType === "platform_admin");
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
async function refreshCartBadge() {
  const badge = document.getElementById("cartBadge");
  if (!badge) return;
  const count = getLocalCartCount();
  badge.textContent = count > 99 ? "99+" : String(count);
  // .cart-badge 自身设置了 display:flex，与原生 hidden 属性同优先级时会被作者样式表覆盖，
  // 必须用 .hidden（!important）才能真正隐藏
  badge.classList.toggle("hidden", count === 0);
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

  // 书店管理员 / 后台管理员登录后不具备普通用户的购物行为，下拉菜单不再展示
  // “个人中心 / 我的订单 / 促销活动”，改为直达后台管理入口
  const menuLinksHtml = isAdminRole(user)
    ? `<a href="admin/dashboard.html">后台管理</a>`
    : `<a href="profile.html">个人中心</a>
       <a href="orders.html">我的订单</a>
       <a href="promotions.html">促销活动</a>`;

  area.innerHTML = `
    <div class="user-chip" id="userChipTrigger">
      <div class="avatar">${(user.nickname || user.userName || "U").slice(0, 1)}</div>
      <span id="userChipName">${user.nickname || user.userName}</span>
      <div class="user-menu" id="userChipMenu">
        ${menuLinksHtml}
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
  // 书店管理员 / 后台管理员不具备购买行为，图书卡片上的“＋”按钮全局隐藏
  if (isAdminRole(getCurrentUser())) {
    // .icon-btn 自身设置了 display:flex，优先级与原生 [hidden] 样式打平后会覆盖它，
    // 因此这里必须用 .hidden（!important）而非 hidden 属性来真正隐藏按钮
    container.querySelectorAll('[data-action="add-cart"]').forEach((btn) => btn.classList.add("hidden"));
    return;
  }
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

/**
 * 顶部导航“搜索方式”标签（书名 / 作者 / ISBN）通用绑定。
 * 用于首页 / 图书详情页 / 店铺主页等只做原生表单跳转（非 AJAX）的页面：
 * 点击标签只需要切换选中态、并把选中的方式写入表单内的隐藏字段 searchType，
 * 由浏览器原生提交带到 search.html。search.html 自身的 AJAX 搜索逻辑写在 search.js 中，
 * 不依赖这个隐藏字段，两者互不影响。
 */
function initHeaderSearchModeBar() {
  document.querySelectorAll(".header-search").forEach((wrap) => {
    const bar = wrap.querySelector(".search-mode-bar");
    if (!bar) return;
    const hiddenInput = wrap.querySelector('form input[name="searchType"]');
    bar.querySelectorAll("button[data-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        bar.querySelectorAll("button[data-mode]").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        if (hiddenInput) hiddenInput.value = btn.dataset.mode;
      });
    });
  });
}

/* ---------- 搜索历史下拉（挂载于顶部导航搜索框） ---------- */
function initSearchHistoryDropdown(input) {
  const wrap = input.closest(".header-search");
  if (!wrap) return;
  const dropdown = document.createElement("div");
  dropdown.className = "search-history-dropdown";
  wrap.appendChild(dropdown);

  async function renderHistory() {
    /**
     * 接口对接位置：SearchAPI.history()
     * 请求：GET /api/search/history，响应：string[]（按用户维度返回的历史搜索关键词）
     */
    const history = await SearchAPI.history();
    if (!history.length) {
      dropdown.classList.remove("is-open");
      return;
    }
    dropdown.innerHTML = `
      <div class="search-history-title">搜索历史</div>
      ${history.map((kw) => `<div class="search-history-item" data-kw="${escapeHtml(kw)}">${escapeHtml(kw)}</div>`).join("")}`;
    dropdown.querySelectorAll(".search-history-item").forEach((item) => {
      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        input.value = item.dataset.kw;
        dropdown.classList.remove("is-open");
        const form = input.closest("form");
        if (form.requestSubmit) form.requestSubmit();
        else form.submit();
      });
    });
    dropdown.classList.add("is-open");
  }

  input.addEventListener("focus", renderHistory);
  input.addEventListener("input", () => {
    if (!input.value) renderHistory();
    else dropdown.classList.remove("is-open");
  });
  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) dropdown.classList.remove("is-open");
  });
}

/* ---------- 页面初始化 ---------- */
document.addEventListener("DOMContentLoaded", () => {
  renderHeaderAuthArea();
  refreshCartBadge();

  // 书店管理员 / 后台管理员登录后不具备购买 / 参与促销的行为，全局隐藏购物车入口与顶部“促销活动”入口
  if (isAdminRole(getCurrentUser())) {
    document.querySelectorAll(".cart-link").forEach((el) => el.classList.add("hidden"));
    document.querySelectorAll('.main-nav a[href="promotions.html"]').forEach((el) => el.classList.add("hidden"));
  }

  document.querySelectorAll('.header-search input[type="search"]').forEach(initSearchHistoryDropdown);
  initHeaderSearchModeBar();

  // 移动端导航菜单开关（如页面包含 .nav-toggle 按钮）
  const navToggle = document.querySelector(".nav-toggle");
  if (navToggle) {
    navToggle.addEventListener("click", () => {
      const nav = document.querySelector(".main-nav");
      if (nav) nav.classList.toggle("is-open");
    });
  }
});
