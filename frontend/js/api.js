const API_BASE_URL = "/api";

const STORAGE_KEYS = {
  TOKEN: "ebs_token",
  USER: "ebs_user",
};

function buildQuery(params = {}) {
  return new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  ).toString();
}

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
    throw new Error((payload && payload.message) || `Request failed (HTTP ${res.status})`);
  }
  return payload && payload.data !== undefined ? payload.data : payload;
}

const AuthAPI = {
  registerUser(payload) {
    return request("/auth/register/user", { method: "POST", body: payload });
  },
  registerSeller(payload) {
    return request("/auth/register/seller", { method: "POST", body: payload });
  },
  login(payload) {
    return request("/auth/login", { method: "POST", body: payload });
  },
  async logout() {
    try {
      await request("/auth/logout", { method: "POST" });
    } finally {
      clearSession();
    }
  },
};

const BookAPI = {
  listCategories() {
    return request("/categories");
  },
  list(params = {}) {
    const qs = buildQuery(params);
    return request(`/books${qs ? `?${qs}` : ""}`);
  },
  recommended(params = {}) {
    const qs = buildQuery({ limit: params.limit || 10, type: params.type });
    return request(`/books/recommended${qs ? `?${qs}` : ""}`);
  },
  detail(bookItemId) {
    return request(`/books/${bookItemId}`);
  },
  similar(bookItemId) {
    return request(`/books/${bookItemId}/similar`);
  },
};

const StoreAPI = {
  detail(storeId) {
    return request(`/stores/${storeId}`);
  },
  books(storeId, params = {}) {
    const qs = buildQuery(params);
    return request(`/stores/${storeId}/books${qs ? `?${qs}` : ""}`);
  },
  updateProfile(storeId, payload) {
    return request(`/stores/${storeId}`, { method: "PUT", body: payload });
  },
};

const CartAPI = {
  list() {
    return request("/cart");
  },
  add(bookItemId, quantity = 1) {
    return request("/cart", { method: "POST", body: { bookItemId, quantity } });
  },
  updateQuantity(bookItemId, quantity) {
    return request(`/cart/${bookItemId}`, { method: "PUT", body: { quantity } });
  },
  remove(bookItemId) {
    return request(`/cart/${bookItemId}`, { method: "DELETE" });
  },
};

const AddressAPI = {
  list() {
    return request("/addresses");
  },
  create(payload) {
    return request("/addresses", { method: "POST", body: payload });
  },
  update(addressId, payload) {
    return request(`/addresses/${addressId}`, { method: "PUT", body: payload });
  },
  remove(addressId) {
    return request(`/addresses/${addressId}`, { method: "DELETE" });
  },
};

const OrderAPI = {
  create(payload) {
    return request("/orders", { method: "POST", body: payload });
  },
  pay(orderId, paymentMethod) {
    return request(`/orders/${orderId}/pay`, { method: "POST", body: { paymentMethod } });
  },
  list(params = {}) {
    const qs = buildQuery(params);
    return request(`/orders${qs ? `?${qs}` : ""}`);
  },
  detail(orderId) {
    return request(`/orders/${orderId}`);
  },
  cancel(orderId) {
    return request(`/orders/${orderId}/cancel`, { method: "POST" });
  },
  requestRefund(orderId, reason) {
    return request(`/orders/${orderId}/refund`, { method: "POST", body: { reason } });
  },
  submitReview(orderId, payload) {
    return request(`/orders/${orderId}/reviews`, { method: "POST", body: payload });
  },
};

const PromotionAPI = {
  listActivities() {
    return request("/promotions/activities");
  },
  checkin() {
    return request("/promotions/checkin", { method: "POST" });
  },
  joinActivity(activityId) {
    return request(`/promotions/activities/${activityId}/join`, { method: "POST" });
  },
  myCoupons(status = "unused") {
    return request(`/promotions/coupons/my?${buildQuery({ status })}`);
  },
  listRewards() {
    return request("/promotions/rewards");
  },
  redeemReward(rewardId) {
    return request(`/promotions/rewards/${rewardId}/redeem`, { method: "POST" });
  },
  claimWeeklyCoupon() {
    return request("/promotions/weekly-coupon/claim", { method: "POST" });
  },
};

const UserAPI = {
  me() {
    return request("/users/me");
  },
  updateProfile(payload) {
    return request("/users/me", { method: "PUT", body: payload });
  },
  points(params = {}) {
    const qs = buildQuery(params);
    return request(`/users/me/points${qs ? `?${qs}` : ""}`);
  },
};

const AdminAPI = {
  books: {
    list(params = {}) {
      const qs = buildQuery(params);
      return request(`/admin/books${qs ? `?${qs}` : ""}`);
    },
    create(payload) {
      return request("/admin/books", { method: "POST", body: payload });
    },
    update(bookItemId, payload) {
      return request(`/admin/books/${bookItemId}`, { method: "PUT", body: payload });
    },
    remove(bookItemId) {
      return request(`/admin/books/${bookItemId}`, { method: "DELETE" });
    },
    forceTakedown(bookItemId, reason) {
      return request(`/admin/books/${bookItemId}/force-takedown`, { method: "POST", body: { reason } });
    },
  },
  orders: {
    list(params = {}) {
      const qs = buildQuery(params);
      return request(`/admin/orders${qs ? `?${qs}` : ""}`);
    },
    updateStatus(orderId, status) {
      return request(`/admin/orders/${orderId}/status`, { method: "PUT", body: { status } });
    },
    handleRefund(orderId, approve) {
      return request(`/admin/orders/${orderId}/refund/${approve ? "approve" : "reject"}`, { method: "POST" });
    },
  },
  users: {
    list(params = {}) {
      const qs = buildQuery(params);
      return request(`/admin/users${qs ? `?${qs}` : ""}`);
    },
    addToStoreBlacklist(userId, reason) {
      return request(`/admin/users/${userId}/blacklist`, { method: "POST", body: { reason } });
    },
    setStatus(userId, status) {
      return request(`/admin/users/${userId}/status`, { method: "PUT", body: { status } });
    },
  },
  stores: {
    list(params = {}) {
      const qs = buildQuery(params);
      return request(`/admin/stores${qs ? `?${qs}` : ""}`);
    },
    setStatus(storeId, status) {
      return request(`/admin/stores/${storeId}/status`, { method: "PUT", body: { status } });
    },
  },
  promotions: {
    listActivities() {
      return request("/admin/promotions/activities");
    },
    saveActivity(activity) {
      const method = activity.activityId ? "PUT" : "POST";
      const path = activity.activityId
        ? `/admin/promotions/activities/${activity.activityId}`
        : "/admin/promotions/activities";
      return request(path, { method, body: activity });
    },
    setStoreParticipation(activityId, payload) {
      return request(`/admin/promotions/activities/${activityId}/store-participation`, {
        method: "POST",
        body: payload,
      });
    },
    savePlatformCoupon(payload) {
      return request("/admin/promotions/coupons", { method: "POST", body: payload });
    },
    saveReward(reward) {
      const method = reward.rewardId ? "PUT" : "POST";
      const path = reward.rewardId ? `/admin/promotions/rewards/${reward.rewardId}` : "/admin/promotions/rewards";
      return request(path, { method, body: reward });
    },
  },
  statistics: {
    overview(params = {}) {
      const qs = buildQuery(params);
      return request(`/admin/statistics/overview${qs ? `?${qs}` : ""}`);
    },
    riskStores() {
      return request("/admin/statistics/risk-stores");
    },
    exportUrl(params = {}) {
      return `${API_BASE_URL}/admin/statistics/export?${buildQuery(params)}`;
    },
  },
  recommendation: {
    settings() {
      return request("/admin/recommendation/settings");
    },
    update(payload) {
      return request("/admin/recommendation/settings", { method: "PUT", body: payload });
    },
  },
};
