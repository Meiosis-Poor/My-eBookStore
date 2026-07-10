/**
 * home.js — 首页逻辑
 * 依赖：api.js、common.js
 * 对应接口：BookAPI.listCategories()、BookAPI.recommended()（4.2.2 图书浏览与搜索流程）
 */
document.addEventListener("DOMContentLoaded", async () => {
  const categoryNav = document.getElementById("categoryNav");
  const bookGrid = document.getElementById("recommendedGrid");
  const hotBookGrid = document.getElementById("hotBookGrid");

  // 事件监听需在同步阶段立即绑定，不能等待下方几个图书接口依次 await 完成后再绑定，
  // 否则用户在接口响应期间点击该链接会不经拦截直接跳转（浏览器默认锚点行为）。
  document.getElementById("merchantEntryLink").addEventListener("click", (e) => {
    if (!isAdminRole(getCurrentUser())) {
      e.preventDefault();
      showToast("仅管理员可访问", "warning");
    }
  });
  document.getElementById("footerProfileLink").addEventListener("click", (e) => {
    if (isAdminRole(getCurrentUser())) {
      e.preventDefault();
      showToast("管理员账号请前往后台管理", "warning");
    }
  });

  // 隐藏彩蛋：连续点击右上角用户名 20 次解锁（common.js 的 renderHeaderAuthArea 在此之前已同步渲染完 authArea）
  const usernameEl = document.getElementById("userChipName");
  if (usernameEl) {
    let easterEggClicks = 0;
    let easterEggLastClickTime = 0;
    usernameEl.addEventListener("click", () => {
      const now = Date.now();
      easterEggClicks = now - easterEggLastClickTime > 1500 ? 1 : easterEggClicks + 1;
      easterEggLastClickTime = now;
      if (easterEggClicks < 20) return;
      easterEggClicks = 0;
      showToast("您已解锁宋律科技", "success", 4000);
      document.body.classList.add("pink-mode");
      document.getElementById("heroTitle").textContent = "遇见宋律，遇见更大的大姐姐";
      document.getElementById("heroDesc").textContent =
        "汇聚全网优质巨大娘的海量宋律资源，涵盖中杯、大杯、超大杯等多个CUP，畅享便捷的在线变大与专属宋律科技。";
    });
  }

  try {
    const categories = await BookAPI.listCategories();
    categoryNav.innerHTML =
      `<a href="search.html" class="active">全部</a>` +
      categories
        .map((c) => `<a href="search.html?categoryId=${c.categoryId}">${c.categoryName}</a>`)
        .join("");
  } catch (err) {
    console.error("加载分类失败", err);
  }

  try {
    const books = await BookAPI.recommended({ limit: 5, type: "guess" });
    bookGrid.innerHTML = books.map(renderBookCard).join("");
    bindAddToCartButtons(bookGrid);
  } catch (err) {
    bookGrid.innerHTML = `<div class="empty-state">推荐图书加载失败，请稍后重试。</div>`;
    console.error("加载推荐图书失败", err);
  }

  try {
    const books = await BookAPI.recommended({ limit: 5, type: "hot" });
    hotBookGrid.innerHTML = books.map(renderBookCard).join("");
    bindAddToCartButtons(hotBookGrid);
  } catch (err) {
    hotBookGrid.innerHTML = `<div class="empty-state">热销图书加载失败，请稍后重试。</div>`;
    console.error("加载热销图书失败", err);
  }
});
