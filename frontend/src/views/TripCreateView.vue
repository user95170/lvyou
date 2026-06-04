<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>新建空白行程</h2>
        <p class="hint">直接创建 1 到 10 天的空草稿，保存后再去详情页慢慢补充内容。</p>
      </div>
      <router-link to="/trips" class="link-button secondary">返回列表</router-link>
    </div>

    <div
      v-if="!currentUser"
      class="empty-state"
      data-testid="trip-new-login-hint"
    >
      <p>请先登录后再创建空白行程。</p>
      <router-link to="/login" class="link-button">前往登录</router-link>
    </div>

    <form
      v-else
      class="detail-form"
      data-testid="trip-new-form"
      @submit.prevent="handleSubmit"
    >
      <section class="block">
        <div class="field-grid">
          <label>
            行程标题
            <input
              v-model="form.title"
              data-testid="trip-new-title-input"
              type="text"
              required
              placeholder="例如：呼伦贝尔 4 天行程"
            />
          </label>

          <label>
            出发城市
            <input
              v-model="form.origin_city"
              data-testid="trip-new-origin-city-input"
              type="text"
              required
              placeholder="例如：呼伦贝尔"
            />
          </label>

          <label>
            出发日期
            <input
              v-model="form.start_date"
              data-testid="trip-new-date-input"
              type="date"
            />
          </label>

          <label>
            预算等级
            <select
              v-model="form.budget_level"
              data-testid="trip-new-budget-level-select"
            >
              <option :value="null">未设置</option>
              <option :value="1">低</option>
              <option :value="2">中</option>
              <option :value="3">高</option>
            </select>
          </label>

          <label>
            出游风格
            <select
              v-model="form.travel_style"
              data-testid="trip-new-travel-style-select"
            >
              <option value="">未设置</option>
              <option value="relax">轻松</option>
              <option value="adventure">探索</option>
              <option value="family">亲子</option>
              <option value="culture">人文</option>
              <option value="photography">摄影</option>
            </select>
          </label>

          <label>
            天数
            <input
              v-model.number="form.days"
              data-testid="trip-new-days-input"
              type="number"
              min="1"
              max="10"
              required
            />
          </label>
        </div>

        <div class="summary">
          <span>将创建 {{ normalizedDays }} 天空草稿</span>
          <span>结束日期：{{ previewEndDate }}</span>
          <span>来源：manual_draft</span>
        </div>
      </section>

      <div class="page-actions">
        <button
          type="submit"
          data-testid="trip-new-submit-btn"
          :disabled="submitting"
        >
          {{ submitting ? '创建中...' : '创建空白行程' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { createTrip } from '../api/trips';
import { toast } from '../utils/toast';
import { getCurrentUser } from '../utils/user';

const MAX_TRIP_DAYS = 10;

const router = useRouter();
const currentUser = getCurrentUser();
const submitting = ref(false);

const form = reactive({
  title: '',
  origin_city: '',
  start_date: '',
  budget_level: null,
  travel_style: '',
  days: 1,
});

const normalizedDays = computed(() => {
  const numericValue = Number(form.days);
  if (!Number.isInteger(numericValue)) {
    return 1;
  }
  return Math.min(MAX_TRIP_DAYS, Math.max(1, numericValue));
});

const previewEndDate = computed(() => {
  if (!form.start_date) {
    return '未设置';
  }
  return formatDateByOffset(form.start_date, normalizedDays.value - 1) || '未设置';
});

function formatDateByOffset(startDate, offset) {
  if (!startDate) {
    return '';
  }

  const baseDate = new Date(`${startDate}T00:00:00`);
  if (Number.isNaN(baseDate.getTime())) {
    return '';
  }

  baseDate.setDate(baseDate.getDate() + offset);
  const year = baseDate.getFullYear();
  const month = String(baseDate.getMonth() + 1).padStart(2, '0');
  const day = String(baseDate.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function normalizeText(value) {
  if (value == null) {
    return '';
  }
  return String(value).trim();
}

function normalizeBudgetLevel(value) {
  if (value === '' || value == null) {
    return null;
  }

  const numericValue = Number(value);
  return Number.isInteger(numericValue) ? numericValue : null;
}

function buildPayload() {
  return {
    user_id: currentUser.id,
    title: normalizeText(form.title),
    start_date: normalizeText(form.start_date) || null,
    origin_city: normalizeText(form.origin_city),
    budget_level: normalizeBudgetLevel(form.budget_level),
    travel_style: normalizeText(form.travel_style) || null,
    created_by: 'manual_draft',
    trip_days: Array.from({ length: normalizedDays.value }, (_, index) => ({
      day_index: index + 1,
      note: null,
      items: [],
    })),
  };
}

function validateForm() {
  if (!currentUser?.id) {
    return false;
  }
  if (!normalizeText(form.title)) {
    toast.error('请输入行程标题');
    return false;
  }
  if (!normalizeText(form.origin_city)) {
    toast.error('请输入出发城市');
    return false;
  }
  if (!Number.isInteger(Number(form.days)) || Number(form.days) < 1 || Number(form.days) > MAX_TRIP_DAYS) {
    toast.error(`天数需要在 1 到 ${MAX_TRIP_DAYS} 之间`);
    return false;
  }
  return true;
}

async function handleSubmit() {
  if (!validateForm()) {
    return;
  }

  submitting.value = true;
  try {
    const resp = await createTrip(buildPayload());
    const tripId = resp.data?.trip?.id;
    toast.success('空白行程已创建');
    if (tripId) {
      router.push(`/trips/${tripId}`);
    } else {
      router.push('/trips');
    }
  } catch (e) {
    const message = e.response?.data?.error || '创建空白行程失败';
    toast.error(message);
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.detail-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.block {
  padding: 16px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.summary span {
  padding: 6px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
}

.page-actions {
  display: flex;
  gap: 12px;
}

.hint {
  color: #6b7280;
  font-size: 14px;
  margin: 4px 0 0;
}

.empty-state {
  padding: 24px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
}

input,
select {
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  background: #ffffff;
}

button,
.link-button {
  padding: 8px 12px;
  border-radius: 6px;
  border: none;
  background: #2563eb;
  color: #ffffff;
  cursor: pointer;
  text-decoration: none;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.link-button.secondary {
  background: #6b7280;
}

@media (max-width: 768px) {
  .page-header,
  .page-actions {
    flex-direction: column;
  }
}
</style>
