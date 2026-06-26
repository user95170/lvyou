import { ref } from 'vue';

const STORAGE_KEY = 'imu_tourism_user';
const TOKEN_KEY = 'imu_tourism_token';

function readUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// 响应式当前用户：供导航栏等组件实时感知登录态变化
export const authUser = ref(readUser());

export function getCurrentUser() {
  return readUser();
}

export function setCurrentUser(user) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  authUser.value = user;
}

export function clearCurrentUser() {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(TOKEN_KEY);
  authUser.value = null;
}

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}
