<template>
  <div class="app-root">
    <header class="app-header">
      <h1>内蒙古智慧旅游系统</h1>
      <nav class="app-nav">
        <router-link to="/" data-testid="nav-home">推荐</router-link>
        <router-link to="/browse" data-testid="nav-browse">目的地浏览</router-link>
        <router-link to="/map" data-testid="nav-map">电子地图</router-link>
        <router-link to="/route" data-testid="nav-route">行程规划</router-link>
        <router-link to="/trips" data-testid="nav-trips">我的行程</router-link>
        <router-link to="/profile" data-testid="nav-profile">我的偏好</router-link>
        <router-link to="/monitor" data-testid="nav-monitor">监控</router-link>
        <template v-if="user">
          <span class="nav-user" data-testid="nav-username">你好，{{ user.username }}</span>
          <button type="button" class="nav-logout" data-testid="nav-logout" @click="handleLogout">
            退出
          </button>
        </template>
        <template v-else>
          <router-link to="/login" data-testid="nav-login">登录</router-link>
          <router-link to="/register" data-testid="nav-register">注册</router-link>
        </template>
      </nav>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';
import { authUser, clearCurrentUser } from './utils/user';
import { toast } from './utils/toast';

const router = useRouter();
const user = authUser;

function handleLogout() {
  clearCurrentUser();
  toast.success('已退出登录');
  router.push('/login');
}
</script>

<style scoped>
.app-root {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
}

.app-nav a {
  margin-left: 16px;
}

.nav-user {
  margin-left: 16px;
  font-size: 14px;
  color: #374151;
}

.nav-logout {
  margin-left: 12px;
  padding: 4px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #ffffff;
  color: #b91c1c;
  cursor: pointer;
  font-size: 13px;
}

.nav-logout:hover {
  background: #fef2f2;
}

.app-main {
  flex: 1;
  padding: 16px 24px;
  background: #f3f4f6;
}
</style>
