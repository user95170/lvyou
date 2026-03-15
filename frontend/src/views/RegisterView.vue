<template>
  <div class="page">
    <h2>用户注册</h2>
    <form class="form" data-testid="register-form" @submit.prevent="handleSubmit">
      <label>
        用户名
        <input v-model="form.username" data-testid="register-username" type="text" required minlength="3" />
      </label>
      <label>
        密码
        <input v-model="form.password" data-testid="register-password" type="password" required minlength="6" />
      </label>
      <label>
        邮箱（可选）
        <input v-model="form.email" data-testid="register-email" type="email" placeholder="you@example.com" />
      </label>
      <button type="submit" data-testid="register-submit" :disabled="submitting">
        {{ submitting ? '注册中...' : '注册' }}
      </button>
      <p v-if="error" class="error" data-testid="register-error">{{ error }}</p>
      <p v-if="success" class="success" data-testid="register-success">{{ success }}</p>
      <p class="hint">
        已有账号？<router-link to="/login">去登录</router-link>
      </p>
    </form>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { register } from '../api/auth';

const router = useRouter();

const form = reactive({
  username: '',
  password: '',
  email: '',
});

const submitting = ref(false);
const error = ref('');
const success = ref('');

async function handleSubmit() {
  error.value = '';
  success.value = '';
  submitting.value = true;
  try {
    const payload = {
      username: form.username,
      password: form.password,
    };
    if (form.email) {
      payload.email = form.email;
    }

    await register(payload);
    success.value = '注册成功，请前往登录页登录';
    setTimeout(() => {
      router.push('/login');
    }, 800);
  } catch (e) {
    error.value = e.response?.data?.error || '注册失败，请检查输入或稍后再试';
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.page {
  max-width: 420px;
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
  background: #059669;
  color: #ffffff;
}

button:disabled {
  opacity: 0.7;
}

.error {
  margin-top: 4px;
  color: #b91c1c;
  font-size: 13px;
}

.success {
  margin-top: 4px;
  color: #047857;
  font-size: 13px;
}

.hint {
  margin-top: 8px;
  font-size: 13px;
}
</style>
