<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>我的行程</h2>
        <p class="hint">统一查看和管理你保存的单日路线与多日行程草案。</p>
      </div>
      <div v-if="currentUser" class="page-header-actions">
        <router-link
          to="/trips/new"
          class="link-button secondary"
          data-testid="trip-new-entry-btn"
        >
          新建空白行程
        </router-link>
        <button type="button" @click="loadTrips" :disabled="loading">
          {{ loading ? '加载中...' : '刷新列表' }}
        </button>
      </div>
    </div>

    <div v-if="!currentUser" class="empty-state">
      <p>请先登录后查看已保存行程。</p>
      <router-link to="/login" class="link-button">前往登录</router-link>
    </div>

    <div v-else-if="loading && trips.length === 0" class="hint">正在加载你的行程...</div>

    <div v-else-if="error" class="error">{{ error }}</div>

    <div
      v-else-if="trips.length === 0"
      class="empty-state"
      data-testid="trip-empty"
    >
      <p>你还没有保存过行程，可以先去路线规划页保存单日路线，或在“我的偏好”里保存 Agent 生成的多日草案。</p>
      <div class="empty-actions">
        <router-link to="/route" class="link-button">去规划路线</router-link>
        <router-link to="/profile" class="link-button secondary">去生成草案</router-link>
      </div>
    </div>

    <ul v-else class="trip-list" data-testid="trip-list">
      <li
        v-for="trip in trips"
        :key="trip.id"
        class="trip-card"
        data-testid="trip-card"
      >
        <div class="trip-card-main">
          <div class="trip-title" data-testid="trip-card-title">{{ trip.title }}</div>
          <div class="trip-meta">
            <span>城市：{{ trip.origin_city || '未设置' }}</span>
            <span>日期：{{ formatDateRange(trip) }}</span>
            <span>天数：{{ trip.days || 0 }}</span>
            <span>项目数：{{ trip.item_count ?? 0 }}</span>
          </div>
          <div class="trip-meta subtle">
            <span>来源：{{ trip.created_by || 'unknown' }}</span>
            <span>更新：{{ formatDateTime(trip.updated_at) }}</span>
          </div>
        </div>

        <div class="trip-actions">
          <button
            type="button"
            data-testid="trip-view-btn"
            @click="goToDetail(trip.id)"
          >
            查看详情
          </button>
          <button
            type="button"
            class="danger"
            data-testid="trip-delete-btn"
            @click="handleDelete(trip.id)"
          >
            删除
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { deleteTrip, listTrips } from '../api/trips';
import { toast } from '../utils/toast';
import { getCurrentUser } from '../utils/user';

const router = useRouter();
const currentUser = getCurrentUser();

const trips = ref([]);
const loading = ref(false);
const error = ref('');

function formatDateTime(value) {
  if (!value) return '未知';
  return String(value).replace('T', ' ').slice(0, 16);
}

function formatDateRange(trip) {
  const startDate = trip?.start_date;
  const endDate = trip?.end_date;
  if (!startDate) {
    return '未设置';
  }
  if (endDate && endDate !== startDate) {
    return `${startDate} ~ ${endDate}`;
  }
  return startDate;
}

async function loadTrips() {
  if (!currentUser?.id) {
    trips.value = [];
    return;
  }

  loading.value = true;
  error.value = '';
  try {
    const resp = await listTrips(currentUser.id);
    trips.value = resp.data.items || [];
  } catch (e) {
    const msg = e.response?.data?.error || '加载行程列表失败';
    error.value = msg;
    toast.error(msg);
  } finally {
    loading.value = false;
  }
}

function goToDetail(tripId) {
  router.push(`/trips/${tripId}`);
}

async function handleDelete(tripId) {
  if (!currentUser?.id) {
    return;
  }

  if (!confirm('确定要删除这个行程吗？')) {
    return;
  }

  try {
    await deleteTrip(tripId, currentUser.id);
    toast.success('行程已删除');
    await loadTrips();
  } catch (e) {
    const msg = e.response?.data?.error || '删除行程失败';
    toast.error(msg);
  }
}

onMounted(() => {
  loadTrips();
});
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

.page-header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.page-header-actions .link-button {
  margin-top: 0;
}

.hint {
  color: #6b7280;
  font-size: 14px;
}

.error {
  color: #b91c1c;
  font-size: 14px;
}

.empty-state {
  padding: 24px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
}

.link-button {
  display: inline-flex;
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  background: #2563eb;
  color: #ffffff;
  text-decoration: none;
}

.link-button.secondary {
  background: #6b7280;
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.empty-actions .link-button {
  margin-top: 0;
}

.trip-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 12px;
}

.trip-card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
}

.trip-card-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trip-title {
  font-size: 18px;
  font-weight: 600;
}

.trip-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 14px;
  color: #374151;
}

.trip-meta.subtle {
  color: #6b7280;
}

.trip-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 120px;
}

button {
  padding: 8px 12px;
  border-radius: 6px;
  border: none;
  background: #2563eb;
  color: #ffffff;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

button.danger {
  background: #dc2626;
}

@media (max-width: 768px) {
  .page-header-actions,
  .trip-card {
    flex-direction: column;
  }

  .trip-actions {
    min-width: auto;
    flex-direction: row;
  }
}
</style>
