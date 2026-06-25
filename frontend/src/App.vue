<template>
  <div class="app-root">
    <header class="app-header">
      <h1>内蒙古智慧旅游系统</h1>
      <nav class="app-nav">
        <router-link to="/" data-testid="nav-home">推荐</router-link>
        <router-link to="/browse" data-testid="nav-browse">目的地浏览</router-link>
        <router-link to="/route" data-testid="nav-route">行程规划</router-link>
        <router-link to="/trips" data-testid="nav-trips">我的行程</router-link>
        <router-link to="/profile" data-testid="nav-profile">我的偏好</router-link>
        <router-link to="/monitor" data-testid="nav-monitor">监控</router-link>
        <router-link to="/login" data-testid="nav-login">登录</router-link>
        <router-link to="/register" data-testid="nav-register">注册</router-link>
      </nav>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
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

.app-main {
  flex: 1;
  padding: 16px 24px;
  background: #f3f4f6;
}
</style>
