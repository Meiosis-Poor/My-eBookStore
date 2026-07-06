/**
 * auth.js — 登录页 / 注册页公共逻辑
 * 依赖：api.js、common.js
 * 对应用例：4.2.1 User Register / Seller Register / User Login
 *
 * 说明：账号类型切换（普通用户 / 书店管理员 / 后台管理员）通过 data-role
 * 属性驱动；后台管理员账号按需求文档由平台统一开通，不开放自助注册入口，
 * 因此注册页仅提供“普通用户”“书店管理员”两种类型，登录页提供全部三种。
 */

const PASSWORD_RULE = /^(?=.*[A-Za-z])(?=.*\d).{6,20}$/; // 至少6位，需同时包含字母和数字

function initRoleSwitch(scopeSelector, onChange) {
  const scope = document.querySelector(scopeSelector);
  if (!scope) return;
  const buttons = scope.querySelectorAll("[data-role]");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange(btn.dataset.role);
    });
  });
}

function setFieldError(groupEl, message) {
  if (!groupEl) return;
  groupEl.classList.add("has-error");
  const errEl = groupEl.querySelector(".form-error");
  if (errEl) errEl.textContent = message;
}
function clearFieldError(groupEl) {
  if (!groupEl) return;
  groupEl.classList.remove("has-error");
}

function redirectAfterLogin(user) {
  const redirect = qs("redirect");
  if (user.userType === "seller" || user.userType === "platform_admin") {
    window.location.href = "admin/dashboard.html";
  } else {
    window.location.href = redirect ? decodeURIComponent(redirect) : "index.html";
  }
}

/* ---------------- 登录页 ---------------- */
function initLoginPage() {
  const form = document.getElementById("loginForm");
  if (!form) return;

  let currentRole = "customer";
  initRoleSwitch("#loginRoleSwitch", (role) => (currentRole = role));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const userNameGroup = document.getElementById("loginUserNameGroup");
    const passwordGroup = document.getElementById("loginPasswordGroup");
    clearFieldError(userNameGroup);
    clearFieldError(passwordGroup);

    const userName = form.userName.value.trim();
    const password = form.password.value;

    if (!userName) return setFieldError(userNameGroup, "请输入用户名");
    if (!password) return setFieldError(passwordGroup, "请输入密码");

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = "登录中...";

    try {
      /**
       * 接口对接位置：AuthAPI.login()
       * 请求：POST /api/auth/login { userName, password, role }
       * 响应：{ token, user }
       * 备选事件流 E-1~E-4（用户名或密码错误 / 账号类型不匹配 / 账号已封禁 / 系统异常）
       * 应由后端在响应中通过 message 字段返回具体错误提示，前端 catch 后展示。
       */
      const result = await AuthAPI.login({ userName, password, role: currentRole });
      const user = result.user || { userName, nickname: userName, userType: currentRole, level: 1, availablePoints: 0 };
      setSession(result.token || "mock-token", user);
      showToast("登录成功", "success");
      setTimeout(() => redirectAfterLogin(user), 500);
    } catch (err) {
      showToast(err.message || "登录失败，请稍后重试！", "danger");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "登录";
    }
  });
}

/* ---------------- 注册页 ---------------- */
function initRegisterPage() {
  const form = document.getElementById("registerForm");
  if (!form) return;

  let currentRole = "customer";
  const storeNameGroup = document.getElementById("storeNameGroup");
  initRoleSwitch("#registerRoleSwitch", (role) => {
    currentRole = role;
    storeNameGroup.classList.toggle("hidden", role !== "seller");
    storeNameGroup.querySelector("input").required = role === "seller";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const groups = {
      userName: document.getElementById("regUserNameGroup"),
      storeName: document.getElementById("storeNameGroup"),
      password: document.getElementById("regPasswordGroup"),
      confirmPassword: document.getElementById("regConfirmPasswordGroup"),
    };
    Object.values(groups).forEach(clearFieldError);

    const userName = form.userName.value.trim();
    const storeName = form.storeName ? form.storeName.value.trim() : "";
    const password = form.password.value;
    const confirmPassword = form.confirmPassword.value;
    const nickname = form.nickname.value.trim() || userName;

    let hasError = false;
    if (userName.length < 3) {
      setFieldError(groups.userName, "用户名至少 3 个字符");
      hasError = true;
    }
    if (currentRole === "seller" && !storeName) {
      setFieldError(groups.storeName, "请输入店铺名称");
      hasError = true;
    }
    if (!PASSWORD_RULE.test(password)) {
      setFieldError(groups.password, "密码格式不正确！需 6-20 位且同时包含字母和数字");
      hasError = true;
    }
    if (confirmPassword !== password) {
      setFieldError(groups.confirmPassword, "两次输入的密码不一致");
      hasError = true;
    }
    if (hasError) return;

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = "提交中...";

    try {
      if (currentRole === "seller") {
        /**
         * 接口对接位置：AuthAPI.registerSeller()
         * 请求：POST /api/auth/register/seller { userName, password, storeName, phone?, email? }
         * 备选事件流：E-1 用户名已存在 / E-2 店铺名已存在 / E-3 密码不合规 / E-4 保存失败
         */
        await AuthAPI.registerSeller({ userName, password, storeName, nickname });
      } else {
        /**
         * 接口对接位置：AuthAPI.registerUser()
         * 请求：POST /api/auth/register/user { userName, password, nickname, phone?, email? }
         * 备选事件流：E-1 用户名已存在 / E-2 密码不合规 / E-3 保存失败
         */
        await AuthAPI.registerUser({ userName, password, nickname });
      }
      showToast("注册成功", "success");
      setTimeout(() => (window.location.href = "login.html"), 700);
    } catch (err) {
      showToast(err.message || "注册失败，请稍后重试！", "danger");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "注册";
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initLoginPage();
  initRegisterPage();
});
