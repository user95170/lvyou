<template>
  <div class="page">
    <h2>用户登录</h2>
    <form class="form" data-testid="login-form" @submit.prevent="handleSubmit">
      <label>
        用户名
        <input v-model="form.username" data-testid="login-username" type="text" required minlength="3" />
      </label>
      <label>
        密码
        <input v-model="form.password" data-testid="login-password" type="password" required minlength="6" />
      </label>
      <button type="submit" data-testid="login-submit" :disabled="submitting">
        {{ submitting ? '登录中...' : '登录' }}
      </button>
      <p v-if="error" class="error" data-testid="login-error">{{ error }}</p>
      <p class="hint">
        还没有账号？<router-link to="/register">去注册</router-link>
      </p>
    </form>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { login } from '../api/auth';
import { setCurrentUser, setToken } from '../utils/user';

const router = useRouter();

const form = reactive({
  username: '',
  password: '',
});

const submitting = ref(false);
const error = ref('');

async function handleSubmit() {
  error.value = '';
  submitting.value = true;
  try {
    const resp = await login({ ...form });
    const data = resp.data;
    if (data && data.user) {
      setCurrentUser(data.user);
      if (data.token) {
        setToken(data.token);
      }
      router.push('/');
    } else {
      error.value = '登录成功但未返回用户信息';
    }
  } catch (e) {
    error.value = e.response?.data?.error || '登录失败，请检查用户名和密码';
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.page {
  max-width: 400px;
  margin: 40px auto;
  padding: 24px;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

label {
  display: flex;
  flex-direction: column;
  font-size: 14px;
}

input {
  margin-top: 4px;
  padding: 6px 8px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
}

button {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 4px;
  border: none;
  background: #2563eb;
  color: #ffffff;
}

button:disabled {
  opacity: 0.7;
}

.error {
  margin-top: 8px;
  color: #b91c1c;
  font-size: 13px;
}

.hint {
  margin-top: 8px;
  font-size: 13px;
}
</style>
