/**
 * api.js
 * ------------------------------------------------------------------------
 * 全站统一的后端接口调用层（占位实现）。
 *
 * 使用说明（对接后端时请阅读）：
 * 1. 本文件只负责“调用约定”，不包含任何服务器 / 数据库逻辑。
 * 2. 每个方法头部的 JSDoc 注释均标明：接口用途、HTTP 方法、请求路径、
 *    请求参数（Query/Body）格式、以及预期的响应 JSON 数据结构，供后端
 *    同学对照实现，也方便前端后续联调。
 * 3. 每个方法内部使用 fetch 通过 request() 发起真实请求；由于目前后端
 *    尚未开发，request() 会请求失败（网络错误 / 404），此时 catch 分支会
 *    退化为读取 mock-data.js 中的模拟数据，以保证页面在无后端环境下依旧
 *    可以正常演示交互效果。
 *    【对接真实后端时，只需删除各方法 catch 分支中的 mock 回退逻辑即可，
 *    request() 部分无需改动。】
 * ------------------------------------------------------------------------
 */

/** 后端 API 根路径，实际联调时按后端部署地址修改，或改为相对路径 "/api" 由反向代理转发 */
const API_BASE_URL = "/api";

/** 本地存储 key 约定 */
const STORAGE_KEYS = {
  TOKEN: "ebs_token",
  USER: "ebs_user",
  CART: "ebs_cart", // 前端演示用的本地购物车缓存；对接后端后购物车以接口数据为准
};

function getToken() {
  return localStorage.getItem(STORAGE_KEYS.TOKEN) || "";
}

function getCurrentUser() {
  const raw = localStorage.getItem(STORAGE_KEYS.USER);
  return raw ? JSON.parse(raw) : null;
}

function setSession(token, user) {
  localStorage.setItem(STORAGE_KEYS.TOKEN, token);
  localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
}

function clearSession() {
  localStorage.removeItem(STORAGE_KEYS.TOKEN);
  localStorage.removeItem(STORAGE_KEYS.USER);
}

/**
 * 通用请求封装。
 * @param {string} path 相对路径，如 "/books"，将拼接为 `${API_BASE_URL}${path}`
 * @param {object} options fetch 配置：{ method, body, headers }；body 为对象时会自动 JSON.stringify
 * @returns {Promise<any>} 解析后的 JSON 响应体
 *
 * 预期后端统一响应格式（建议）：
 *   成功：{ code: 0, message: "ok", data: <业务数据> }
 *   失败：{ code: <非0错误码>, message: "错误描述", data: null }
 */
async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    ...(options.headers || {}),
  };
  const body =
    options.body && typeof options.body !== "string" ? JSON.stringify(options.body) : options.body;

  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok || (payload && payload.code !== undefined && payload.code !== 0)) {
    throw new Error((payload && payload.message) || `请求失败（HTTP ${res.status}）`);
  }
  return payload && payload.data !== undefined ? payload.data : payload;
}

/* ============================================================
 * 1. 用户认证模块  AuthAPI
 * ============================================================ */
const AuthAPI = {
  /**
   * 普通用户注册
   * 方法：POST  路径：/auth/register/user
   * 请求体：{ userName: string, password: string, phone?: string, email?: string, nickname: string }
   * 响应：{ userId: number }
   * 对应用例：4.2.1 User Register 普通用户注册
   */
  async registerUser(payload) {
    try {
      return await request("/auth/register/user", { method: "POST", body: payload });
    } catch (err) {
      console.warn("[AuthAPI.registerUser] 后端接口未就绪，使用模拟注册结果：", err.message);
      return mockDelay({ userId: Date.now() });
    }
  },

  /**
   * 书店管理员（卖家）注册
   * 方法：POST  路径：/auth/register/seller
   * 请求体：{ userName: string, password: string, storeName: string, phone?: string, email?: string }
   * 响应：{ userId: number, storeId: number }
   * 对应用例：4.2.1 Seller Register 卖家注册
   */
  async registerSeller(payload) {
    try {
      return await request("/auth/register/seller", { method: "POST", body: payload });
    } catch (err) {
      console.warn("[AuthAPI.registerSeller] 后端接口未就绪，使用模拟注册结果：", err.message);
      return mockDelay({ userId: Date.now(), storeId: Date.now() });
    }
  },

  /**
   * 用户登录（普通用户 / 书店管理员 / 后台管理员 共用一个接口，由 role 区分）
   * 方法：POST  路径：/auth/login
   * 请求体：{ userName: string, password: string, role: "customer"|"seller"|"platform_admin" }
   * 响应：{ token: string, user: { userId, userName, nickname, userType, level, ... } }
   * 对应用例：4.2.1 User Login 用户登录
   */
  async login(payload) {
    try {
      return await request("/auth/login", { method: "POST", body: payload });
    } catch (err) {
      console.warn("[AuthAPI.login] 后端接口未就绪，使用模拟登录结果：", err.message);
      // 演示环境下，登录的书店管理员统一关联到 MOCK_STORE_PROFILES 中的第一家店铺（storeId 100），
      // 以便店铺信息设置页、后台图书/统计等页面与客户端 store.html 的数据能对应上；
      // 真实后端应根据登录账号返回其实际关联的 storeId / storeName。
      const sellerStore = MOCK_STORE_PROFILES[0];
      return mockDelay({
        token: "mock-token-" + Date.now(),
        user: {
          userId: Date.now(),
          userName: payload.userName,
          nickname: payload.userName,
          storeId: payload.role === "seller" ? sellerStore.storeId : undefined,
          storeName: payload.role === "seller" ? sellerStore.storeName : undefined,
          userType: payload.role || "customer",
          level: 3,
          totalPoints: MOCK_CURRENT_USER.totalPoints,
          availablePoints: MOCK_CURRENT_USER.availablePoints,
          continuousCheckinDays: MOCK_CURRENT_USER.continuousCheckinDays,
        },
      });
    }
  },

  /** 退出登录（清理服务端会话，可选） 方法：POST 路径：/auth/logout */
  async logout() {
    try {
      await request("/auth/logout", { method: "POST" });
    } catch (err) {
      console.warn("[AuthAPI.logout] 后端接口未就绪，仅清理本地会话：", err.message);
    } finally {
      clearSession();
    }
  },
};

/* ============================================================
 * 2. 图书浏览与搜索模块  BookAPI
 * ============================================================ */
const BookAPI = {
  /** 获取图书分类列表 方法：GET 路径：/categories 响应：CategoryItem[] */
  async listCategories() {
    try {
      return await request("/categories");
    } catch (err) {
      console.warn("[BookAPI.listCategories] 使用模拟数据：", err.message);
      return mockDelay(MOCK_CATEGORIES);
    }
  },

  /**
   * 分类浏览 / 关键词搜索图书列表
   * 方法：GET 路径：/books
   * Query：{ keyword?, categoryId?, sort?: "default"|"sales"|"price_asc"|"price_desc", page?, pageSize? }
   * 响应：{ list: BookItem[], total: number }
   * 对应用例：4.2.2 Browse and Search Books
   */
  async list(params = {}) {
    try {
      const qs = new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
      ).toString();
      return await request(`/books?${qs}`);
    } catch (err) {
      console.warn("[BookAPI.list] 使用模拟数据：", err.message);
      let list = [...MOCK_BOOKS];
      if (params.categoryId) {
        list = list.filter((b) => String(b.categoryId) === String(params.categoryId));
      }
      if (params.keyword) {
        const kw = params.keyword.trim().toLowerCase();
        list = list.filter(
          (b) => b.bookName.toLowerCase().includes(kw) || b.author.toLowerCase().includes(kw)
        );
      }
      if (params.sort === "sales") list.sort((a, b) => b.salesCount - a.salesCount);
      if (params.sort === "price_asc") list.sort((a, b) => a.price - b.price);
      if (params.sort === "price_desc") list.sort((a, b) => b.price - a.price);
      return mockDelay({ list, total: list.length });
    }
  },

  /**
   * 首页推荐图书（调用推荐算法模块）
   * 方法：GET 路径：/books/recommended
   * Query：{ userId?: number, limit?: number }
   * 响应：BookItem[]
   */
  async recommended(params = {}) {
    try {
      return await request(`/books/recommended?limit=${params.limit || 10}`);
    } catch (err) {
      console.warn("[BookAPI.recommended] 使用模拟数据：", err.message);
      return mockDelay(MOCK_BOOKS.slice(0, params.limit || 10));
    }
  },

  /**
   * 图书详情
   * 方法：GET 路径：/books/{bookItemId}
   * 响应：BookItem（含 description、embedding 相似推荐等扩展信息）
   */
  async detail(bookItemId) {
    try {
      return await request(`/books/${bookItemId}`);
    } catch (err) {
      console.warn("[BookAPI.detail] 使用模拟数据：", err.message);
      const book = MOCK_BOOKS.find((b) => String(b.bookItemId) === String(bookItemId)) || MOCK_BOOKS[0];
      return mockDelay(book);
    }
  },

  /**
   * 相似图书推荐（基于 embedding 相似度，用于详情页/搜索页兜底推荐）
   * 方法：GET 路径：/books/{bookItemId}/similar
   * 响应：BookItem[]
   */
  async similar(bookItemId) {
    try {
      return await request(`/books/${bookItemId}/similar`);
    } catch (err) {
      console.warn("[BookAPI.similar] 使用模拟数据：", err.message);
      return mockDelay(MOCK_BOOKS.filter((b) => String(b.bookItemId) !== String(bookItemId)).slice(0, 5));
    }
  },
};

/* ============================================================
 * 2.5 店铺模块  StoreAPI
 * 场景：图书详情页点击“进入书店” → 查看该书店主页及全部在架图书
 * ============================================================ */
const StoreAPI = {
  /**
   * 店铺主页信息
   * 方法：GET 路径：/stores/{storeId}
   * 响应：{ storeId, storeName, createdTime, bookCount, salesCount }
   */
  async detail(storeId) {
    try {
      return await request(`/stores/${storeId}`);
    } catch (err) {
      console.warn("[StoreAPI.detail] 使用模拟数据：", err.message);
      const profile =
        MOCK_STORE_PROFILES.find((s) => String(s.storeId) === String(storeId)) || MOCK_STORE_PROFILES[0];
      const books = MOCK_BOOKS.filter((b) => String(b.storeId) === String(profile.storeId));
      return mockDelay({
        ...profile,
        bookCount: books.length,
        salesCount: books.reduce((sum, b) => sum + b.salesCount, 0),
      });
    }
  },

  /**
   * 店铺内全部在架图书
   * 方法：GET 路径：/stores/{storeId}/books
   * Query：{ sort?: "default"|"sales"|"price_asc"|"price_desc", page?, pageSize? }
   * 响应：{ list: BookItem[], total: number }
   */
  async books(storeId, params = {}) {
    try {
      const qs = new URLSearchParams(params).toString();
      return await request(`/stores/${storeId}/books?${qs}`);
    } catch (err) {
      console.warn("[StoreAPI.books] 使用模拟数据：", err.message);
      let list = MOCK_BOOKS.filter((b) => String(b.storeId) === String(storeId));
      if (params.sort === "sales") list = [...list].sort((a, b) => b.salesCount - a.salesCount);
      if (params.sort === "price_asc") list = [...list].sort((a, b) => a.price - b.price);
      if (params.sort === "price_desc") list = [...list].sort((a, b) => b.price - a.price);
      return mockDelay({ list, total: list.length });
    }
  },

  /**
   * 书店管理员维护本店基本信息（店铺名称）
   * 方法：PUT 路径：/stores/{storeId}
   * 请求体：{ storeName?: string }
   * 场景：后台“店铺信息设置”页保存
   */
  async updateProfile(storeId, payload) {
    try {
      return await request(`/stores/${storeId}`, { method: "PUT", body: payload });
    } catch (err) {
      console.warn("[StoreAPI.updateProfile] 使用模拟数据更新：", err.message);
      const profile = MOCK_STORE_PROFILES.find((s) => String(s.storeId) === String(storeId));
      if (profile) {
        Object.assign(profile, payload);
        persistMockStoreProfiles();
      }
      return mockDelay({ ok: true });
    }
  },
};

/* ============================================================
 * 3. 购物车模块  CartAPI
 * ============================================================ */
const CartAPI = {
  /** 获取当前用户购物车 方法：GET 路径：/cart 响应：CartItem[] */
  async list() {
    try {
      return await request("/cart");
    } catch (err) {
      console.warn("[CartAPI.list] 使用本地模拟购物车：", err.message);
      return mockDelay(readLocalCart());
    }
  },

  /**
   * 加入购物车
   * 方法：POST 路径：/cart
   * 请求体：{ bookItemId: number, quantity: number }
   * 对应用例：4.2.3 Add Book to Cart
   */
  async add(bookItemId, quantity = 1) {
    try {
      return await request("/cart", { method: "POST", body: { bookItemId, quantity } });
    } catch (err) {
      console.warn("[CartAPI.add] 写入本地模拟购物车：", err.message);
      const cart = readLocalCart();
      const book = MOCK_BOOKS.find((b) => String(b.bookItemId) === String(bookItemId));
      const existing = cart.find((c) => String(c.bookItemId) === String(bookItemId));
      if (existing) existing.quantity += quantity;
      else cart.push({ bookItemId, quantity, book });
      writeLocalCart(cart);
      return mockDelay({ ok: true });
    }
  },

  /**
   * 修改购物车商品数量
   * 方法：PUT 路径：/cart/{cartItemId}
   * 请求体：{ quantity: number }
   */
  async updateQuantity(bookItemId, quantity) {
    try {
      return await request(`/cart/${bookItemId}`, { method: "PUT", body: { quantity } });
    } catch (err) {
      const cart = readLocalCart();
      const item = cart.find((c) => String(c.bookItemId) === String(bookItemId));
      if (item) item.quantity = quantity;
      writeLocalCart(cart);
      return mockDelay({ ok: true });
    }
  },

  /** 删除购物车商品 方法：DELETE 路径：/cart/{cartItemId} */
  async remove(bookItemId) {
    try {
      return await request(`/cart/${bookItemId}`, { method: "DELETE" });
    } catch (err) {
      writeLocalCart(readLocalCart().filter((c) => String(c.bookItemId) !== String(bookItemId)));
      return mockDelay({ ok: true });
    }
  },
};

function readLocalCart() {
  const raw = localStorage.getItem(STORAGE_KEYS.CART);
  return raw ? JSON.parse(raw) : [];
}
function writeLocalCart(cart) {
  localStorage.setItem(STORAGE_KEYS.CART, JSON.stringify(cart));
  document.dispatchEvent(new CustomEvent("cart:updated"));
}

/* ============================================================
 * 4. 订单与支付模块  OrderAPI
 * ============================================================ */
const OrderAPI = {
  /**
   * 提交订单（下单）
   * 方法：POST 路径：/orders
   * 请求体：{ cartItemIds: number[], couponId?: number, addressId?: number }
   * 响应：{ orderId, orderNo, totalAmount, discountAmount, actualAmount }
   * 对应用例：4.2.4 Submit Order and Payment（下单部分）
   */
  async create(payload) {
    try {
      return await request("/orders", { method: "POST", body: payload });
    } catch (err) {
      console.warn("[OrderAPI.create] 使用模拟订单创建：", err.message);
      return mockDelay({
        orderId: Date.now(),
        orderNo: `NO${Date.now()}`,
        totalAmount: payload.totalAmount || 0,
        discountAmount: payload.discountAmount || 0,
        actualAmount: payload.actualAmount || 0,
      });
    }
  },

  /**
   * 发起支付
   * 方法：POST 路径：/orders/{orderId}/pay
   * 请求体：{ paymentMethod: "alipay"|"wechat"|"card" }
   * 响应：{ paymentStatus: "success"|"fail", paymentNo?: string }
   * 对应用例：4.2.4 Submit Order and Payment（支付部分）
   */
  async pay(orderId, paymentMethod) {
    try {
      return await request(`/orders/${orderId}/pay`, { method: "POST", body: { paymentMethod } });
    } catch (err) {
      console.warn("[OrderAPI.pay] 使用模拟支付结果：", err.message);
      return mockDelay({ paymentStatus: "success", paymentNo: `PAY${Date.now()}` });
    }
  },

  /**
   * 查询当前用户订单列表
   * 方法：GET 路径：/orders
   * Query：{ status?: string, page?, pageSize? }
   * 响应：{ list: Order[], total: number }
   * 对应用例：4.2.5 Query Orders
   */
  async list(params = {}) {
    try {
      const qs = new URLSearchParams(params).toString();
      return await request(`/orders?${qs}`);
    } catch (err) {
      console.warn("[OrderAPI.list] 使用模拟数据：", err.message);
      let list = [...MOCK_ORDERS];
      if (params.status && params.status !== "all") {
        list = list.filter((o) => o.orderStatus === params.status);
      }
      return mockDelay({ list, total: list.length });
    }
  },

  /** 订单详情 方法：GET 路径：/orders/{orderId} 响应：Order（含 items 明细） */
  async detail(orderId) {
    try {
      return await request(`/orders/${orderId}`);
    } catch (err) {
      console.warn("[OrderAPI.detail] 使用模拟数据：", err.message);
      const order = MOCK_ORDERS.find((o) => String(o.orderId) === String(orderId)) || MOCK_ORDERS[0];
      return mockDelay(order);
    }
  },

  /** 取消订单 方法：POST 路径：/orders/{orderId}/cancel */
  async cancel(orderId) {
    try {
      return await request(`/orders/${orderId}/cancel`, { method: "POST" });
    } catch (err) {
      setMockOrderStatus(orderId, "cancelled");
      return mockDelay({ ok: true });
    }
  },

  /**
   * 申请退款
   * 方法：POST 路径：/orders/{orderId}/refund
   * 请求体：{ reason: string }
   */
  async requestRefund(orderId, reason) {
    try {
      return await request(`/orders/${orderId}/refund`, { method: "POST", body: { reason } });
    } catch (err) {
      setMockOrderStatus(orderId, "refunding");
      return mockDelay({ ok: true });
    }
  },
};

/** 同步修改 MOCK_ORDERS 中对应订单的状态与展示文案，保证 mock 模式下写操作后重新查询能看到最新状态 */
function setMockOrderStatus(orderId, orderStatus) {
  const order = MOCK_ORDERS.find((o) => String(o.orderId) === String(orderId));
  if (order) {
    order.orderStatus = orderStatus;
    order.statusLabel = ORDER_STATUS_LABELS[orderStatus] || orderStatus;
  }
}

/* ============================================================
 * 5. 促销活动模块  PromotionAPI（用户端）
 * ============================================================ */
const PromotionAPI = {
  /** 当前可参与的活动列表 方法：GET 路径：/promotions/activities 响应：Activity[] */
  async listActivities() {
    try {
      return await request("/promotions/activities");
    } catch (err) {
      console.warn("[PromotionAPI.listActivities] 使用模拟数据：", err.message);
      return mockDelay(MOCK_ACTIVITIES);
    }
  },

  /**
   * 每日签到
   * 方法：POST 路径：/promotions/checkin
   * 响应：{ continuousDays: number, rewardPoints: number, rewardCoupon?: object }
   * 对应用例：4.2.6 Promotion Activities（签到部分）
   */
  async checkin() {
    try {
      return await request("/promotions/checkin", { method: "POST" });
    } catch (err) {
      console.warn("[PromotionAPI.checkin] 使用模拟签到结果：", err.message);
      return mockDelay({ continuousDays: MOCK_CURRENT_USER.continuousCheckinDays + 1, rewardPoints: 10 });
    }
  },

  /** 参与指定活动（答题/小游戏等） 方法：POST 路径：/promotions/activities/{activityId}/join */
  async joinActivity(activityId) {
    try {
      return await request(`/promotions/activities/${activityId}/join`, { method: "POST" });
    } catch (err) {
      return mockDelay({ ok: true, rewardCouponName: "5元无门槛代金券" });
    }
  },

  /** 我的代金券列表 方法：GET 路径：/promotions/coupons/my Query：{status?: "unused"|"used"|"expired"} */
  async myCoupons(status = "unused") {
    try {
      return await request(`/promotions/coupons/my?status=${status}`);
    } catch (err) {
      console.warn("[PromotionAPI.myCoupons] 使用模拟数据：", err.message);
      return mockDelay(MOCK_COUPONS);
    }
  },

  /** 积分兑换奖品列表 方法：GET 路径：/promotions/rewards 响应：Reward[] */
  async listRewards() {
    try {
      return await request("/promotions/rewards");
    } catch (err) {
      console.warn("[PromotionAPI.listRewards] 使用模拟数据：", err.message);
      return mockDelay(MOCK_REWARDS);
    }
  },

  /** 兑换奖品 方法：POST 路径：/promotions/rewards/{rewardId}/redeem */
  async redeemReward(rewardId) {
    try {
      return await request(`/promotions/rewards/${rewardId}/redeem`, { method: "POST" });
    } catch (err) {
      return mockDelay({ ok: true });
    }
  },

  /** 高等级用户领取周代金券 方法：POST 路径：/promotions/weekly-coupon/claim */
  async claimWeeklyCoupon() {
    try {
      return await request("/promotions/weekly-coupon/claim", { method: "POST" });
    } catch (err) {
      return mockDelay({ ok: true });
    }
  },
};

/* ============================================================
 * 6. 用户中心模块  UserAPI
 * ============================================================ */
const UserAPI = {
  /** 获取当前登录用户信息（含积分/等级） 方法：GET 路径：/users/me */
  async me() {
    try {
      return await request("/users/me");
    } catch (err) {
      console.warn("[UserAPI.me] 使用模拟数据：", err.message);
      return mockDelay(MOCK_CURRENT_USER);
    }
  },

  /** 更新个人资料 方法：PUT 路径：/users/me 请求体：{ nickname?, phone?, email? } */
  async updateProfile(payload) {
    try {
      return await request("/users/me", { method: "PUT", body: payload });
    } catch (err) {
      return mockDelay({ ok: true });
    }
  },
};

/* ============================================================
 * 7. 后台管理模块  AdminAPI（书店管理员 / 后台管理员共用，权限由后端按 token 校验）
 * ============================================================ */
const AdminAPI = {
  /* ---- 7.1 图书管理 4.3.1 Book Management ---- */
  books: {
    /** 后台图书列表 方法：GET 路径：/admin/books Query：{ keyword?, status?, page?, pageSize? } */
    async list(params = {}) {
      try {
        return await request(`/admin/books?${new URLSearchParams(params)}`);
      } catch (err) {
        console.warn("[AdminAPI.books.list] 使用模拟数据：", err.message);
        let list = MOCK_BOOKS;
        if (params.keyword) {
          const kw = String(params.keyword).trim().toLowerCase();
          list = list.filter(
            (b) => b.bookName.toLowerCase().includes(kw) || b.author.toLowerCase().includes(kw) || b.isbn.includes(kw)
          );
        }
        return mockDelay({ list, total: list.length });
      }
    },
    /** 新增图书 方法：POST 路径：/admin/books 请求体：BookInfo 表 + BookItem 表字段（名称/作者/出版社/ISBN/简介/分类/价格/库存等） */
    async create(payload) {
      try {
        return await request("/admin/books", { method: "POST", body: payload });
      } catch (err) {
        const category = MOCK_CATEGORIES.find((c) => String(c.categoryId) === String(payload.categoryId));
        const newBook = {
          bookItemId: Date.now(),
          bookInfoId: Date.now(),
          bookName: payload.bookName,
          author: payload.author,
          publisher: payload.publisher || "",
          isbn: payload.isbn || "",
          categoryId: payload.categoryId,
          categoryName: category ? category.categoryName : "",
          description: payload.description || "",
          price: payload.price,
          originPrice: payload.price,
          stock: payload.stock,
          salesCount: 0,
          storeId: 0,
          storeName: getCurrentUser()?.storeName || "本店",
          cover: "📘",
          publishDate: new Date().toISOString().slice(0, 10),
        };
        MOCK_BOOKS.unshift(newBook);
        return mockDelay({ ok: true, bookItemId: newBook.bookItemId });
      }
    },
    /** 修改图书 方法：PUT 路径：/admin/books/{bookItemId} */
    async update(bookItemId, payload) {
      try {
        return await request(`/admin/books/${bookItemId}`, { method: "PUT", body: payload });
      } catch (err) {
        const book = MOCK_BOOKS.find((b) => String(b.bookItemId) === String(bookItemId));
        if (book) {
          Object.assign(book, payload);
          if (payload.categoryId) {
            const category = MOCK_CATEGORIES.find((c) => String(c.categoryId) === String(payload.categoryId));
            if (category) book.categoryName = category.categoryName;
          }
        }
        return mockDelay({ ok: true });
      }
    },
    /** 下架/删除图书 方法：DELETE 路径：/admin/books/{bookItemId} */
    async remove(bookItemId) {
      try {
        return await request(`/admin/books/${bookItemId}`, { method: "DELETE" });
      } catch (err) {
        const idx = MOCK_BOOKS.findIndex((b) => String(b.bookItemId) === String(bookItemId));
        if (idx !== -1) MOCK_BOOKS.splice(idx, 1);
        return mockDelay({ ok: true });
      }
    },
    /** 后台管理员强制下架违规图书 方法：POST 路径：/admin/books/{bookItemId}/force-takedown */
    async forceTakedown(bookItemId, reason) {
      try {
        return await request(`/admin/books/${bookItemId}/force-takedown`, { method: "POST", body: { reason } });
      } catch (err) {
        const idx = MOCK_BOOKS.findIndex((b) => String(b.bookItemId) === String(bookItemId));
        if (idx !== -1) MOCK_BOOKS.splice(idx, 1);
        return mockDelay({ ok: true });
      }
    },
  },

  /* ---- 7.2 订单管理 4.3.2 Order Management ---- */
  orders: {
    /** 后台订单列表 方法：GET 路径：/admin/orders Query：{ status?, keyword?, page?, pageSize? } */
    async list(params = {}) {
      try {
        return await request(`/admin/orders?${new URLSearchParams(params)}`);
      } catch (err) {
        console.warn("[AdminAPI.orders.list] 使用模拟数据：", err.message);
        let list = MOCK_ORDERS;
        if (params.keyword) {
          const kw = String(params.keyword).trim().toLowerCase();
          list = list.filter((o) => o.orderNo.toLowerCase().includes(kw));
        }
        return mockDelay({ list, total: list.length });
      }
    },
    /** 更新订单状态 方法：PUT 路径：/admin/orders/{orderId}/status 请求体：{ status: string } */
    async updateStatus(orderId, status) {
      try {
        return await request(`/admin/orders/${orderId}/status`, { method: "PUT", body: { status } });
      } catch (err) {
        setMockOrderStatus(orderId, status);
        return mockDelay({ ok: true });
      }
    },
    /** 处理退款申请 方法：POST 路径：/admin/orders/{orderId}/refund/approve 或 /reject */
    async handleRefund(orderId, approve) {
      try {
        return await request(`/admin/orders/${orderId}/refund/${approve ? "approve" : "reject"}`, { method: "POST" });
      } catch (err) {
        setMockOrderStatus(orderId, approve ? "refunded" : "completed");
        return mockDelay({ ok: true });
      }
    },
  },

  /* ---- 7.3 用户管理 4.3.3 User Management ---- */
  users: {
    /** 用户列表（书店管理员只能查看购买过本店图书的用户） 方法：GET 路径：/admin/users */
    async list(params = {}) {
      try {
        return await request(`/admin/users?${new URLSearchParams(params)}`);
      } catch (err) {
        console.warn("[AdminAPI.users.list] 使用模拟数据：", err.message);
        let list = MOCK_ADMIN_USERS;
        if (params.keyword) {
          const kw = String(params.keyword).trim().toLowerCase();
          list = list.filter((u) => u.userName.toLowerCase().includes(kw) || u.nickname.toLowerCase().includes(kw));
        }
        return mockDelay({ list, total: list.length });
      }
    },
    /** 书店管理员将用户加入本店黑名单 方法：POST 路径：/admin/users/{userId}/blacklist 请求体：{ reason: string } */
    async addToStoreBlacklist(userId, reason) {
      try {
        return await request(`/admin/users/${userId}/blacklist`, { method: "POST", body: { reason } });
      } catch (err) {
        return mockDelay({ ok: true });
      }
    },
    /** 后台管理员封禁/解封用户 方法：PUT 路径：/admin/users/{userId}/status 请求体：{ status: "active"|"banned" } */
    async setStatus(userId, status) {
      try {
        return await request(`/admin/users/${userId}/status`, { method: "PUT", body: { status } });
      } catch (err) {
        const user = MOCK_ADMIN_USERS.find((u) => String(u.userId) === String(userId));
        if (user) user.status = status;
        return mockDelay({ ok: true });
      }
    },
  },

  /* ---- 7.4 店铺管理（仅后台管理员）全平台店铺管理 ---- */
  stores: {
    /** 店铺列表 方法：GET 路径：/admin/stores */
    async list(params = {}) {
      try {
        return await request(`/admin/stores?${new URLSearchParams(params)}`);
      } catch (err) {
        console.warn("[AdminAPI.stores.list] 使用模拟数据：", err.message);
        return mockDelay({ list: MOCK_STORES, total: MOCK_STORES.length });
      }
    },
    /** 开放/封禁店铺 方法：PUT 路径：/admin/stores/{storeId}/status 请求体：{ status: "active"|"banned" } */
    async setStatus(storeId, status) {
      try {
        return await request(`/admin/stores/${storeId}/status`, { method: "PUT", body: { status } });
      } catch (err) {
        const store = MOCK_STORES.find((s) => String(s.storeId) === String(storeId));
        if (store) store.status = status;
        return mockDelay({ ok: true });
      }
    },
  },

  /* ---- 7.5 促销活动管理 4.3.5 Promotion Activity Management ---- */
  promotions: {
    /** 活动列表（后台视角） 方法：GET 路径：/admin/promotions/activities */
    async listActivities() {
      try {
        return await request("/admin/promotions/activities");
      } catch (err) {
        console.warn("[AdminAPI.promotions.listActivities] 使用模拟数据：", err.message);
        return mockDelay(MOCK_ACTIVITIES);
      }
    },
    /** 后台管理员新增/修改活动类型与内容 方法：POST /admin/promotions/activities 或 PUT /admin/promotions/activities/{id} */
    async saveActivity(activity) {
      try {
        const method = activity.activityId ? "PUT" : "POST";
        const path = activity.activityId ? `/admin/promotions/activities/${activity.activityId}` : "/admin/promotions/activities";
        return await request(path, { method, body: activity });
      } catch (err) {
        return mockDelay({ ok: true });
      }
    },
    /** 书店管理员设置是否参与活动及参与书目/店铺券额度 方法：POST 路径：/admin/promotions/activities/{activityId}/store-participation */
    async setStoreParticipation(activityId, payload) {
      try {
        return await request(`/admin/promotions/activities/${activityId}/store-participation`, {
          method: "POST",
          body: payload,
        });
      } catch (err) {
        return mockDelay({ ok: true });
      }
    },
    /** 后台管理员设置平台代金券额度与发放数量 方法：POST 路径：/admin/promotions/coupons */
    async savePlatformCoupon(payload) {
      try {
        return await request("/admin/promotions/coupons", { method: "POST", body: payload });
      } catch (err) {
        return mockDelay({ ok: true });
      }
    },
    /** 调整积分兑换奖品种类与数量 方法：PUT 路径：/admin/promotions/rewards/{rewardId} */
    async saveReward(reward) {
      try {
        const method = reward.rewardId ? "PUT" : "POST";
        const path = reward.rewardId ? `/admin/promotions/rewards/${reward.rewardId}` : "/admin/promotions/rewards";
        return await request(path, { method, body: reward });
      } catch (err) {
        return mockDelay({ ok: true });
      }
    },
  },

  /* ---- 7.6 数据统计与分析 4.3.4 Data Analysis ---- */
  statistics: {
    /**
     * 销售与经营数据统计
     * 方法：GET 路径：/admin/statistics/overview
     * Query：{ range?: "7d"|"30d"|"90d", storeId?: number }（书店管理员固定为本店，后台管理员可查全平台或指定店铺）
     * 响应：{ kpi: {...}, salesTrend: [{label, value}], hotBooks: [{bookName, salesCount}] }
     */
    async overview(params = {}) {
      try {
        return await request(`/admin/statistics/overview?${new URLSearchParams(params)}`);
      } catch (err) {
        console.warn("[AdminAPI.statistics.overview] 使用模拟数据：", err.message);
        return mockDelay(MOCK_STATS);
      }
    },
    /** 风控分析：疑似异常刷单店铺 方法：GET 路径：/admin/statistics/risk-stores（仅后台管理员） */
    async riskStores() {
      try {
        return await request("/admin/statistics/risk-stores");
      } catch (err) {
        return mockDelay([
          { storeId: 105, storeName: "速销书城", riskScore: 87, reason: "短时间内同一账号集群重复下单" },
          { storeId: 118, storeName: "特惠图书", riskScore: 62, reason: "退款率显著高于平台均值" },
        ]);
      }
    },
  },
};
