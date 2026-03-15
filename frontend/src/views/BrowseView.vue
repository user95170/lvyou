<template>
  <div class="page">
    <h2>?????</h2>

    <div
      v-if="isColdStartMode"
      class="cold-start-tip"
      data-testid="browse-cold-start-tip"
    >
      <p class="cold-start-text">
        ?????????????????????????????????????
      </p>
    </div>

    <div class="filters">
      <label>
        ??
        <select v-model="type" data-testid="browse-type">
          <option value="scenic">??</option>
          <option value="hotel">??</option>
          <option value="food">??</option>
        </select>
      </label>
      <label>
        ??
        <input
          v-model="city"
          data-testid="browse-city"
          type="text"
          placeholder="???????"
        />
      </label>
      <button
        type="button"
        data-testid="browse-search"
        @click="fetchList"
        :disabled="loading"
      >
        {{ loading ? '???...' : '??' }}
      </button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <ul v-else class="card-list">
      <li v-for="item in items" :key="item.id" class="card" data-testid="browse-card">
        <h4>{{ item.name }}</h4>
        <p class="sub">
          <span>{{ item.city }}</span>
          <span v-if="type === 'scenic'"> ? ?? {{ item.rating_avg ?? '??' }}</span>
          <span v-else-if="type === 'hotel'"> ? ?? {{ item.avg_price ?? '??' }}</span>
          <span v-else> ? {{ item.cuisine_type || '???' }}</span>
        </p>
        <p class="desc">
          {{ item.description?.slice(0, 60) || item.tags || '??????????' }}
        </p>
        <div class="actions">
          <button type="button" data-testid="browse-rate-btn" @click="rateItem(item)">
            ???
          </button>
          <button
            v-if="type === 'scenic'"
            type="button"
            class="secondary"
            data-testid="browse-similar-btn"
            @click="loadSimilar(item)"
            :disabled="similarLoadingId === item.id"
          >
            {{ similarLoadingId === item.id ? '??????...' : '??????' }}
          </button>
        </div>
        <div
          v-if="type === 'scenic' && similarFor === item.id && similarItems.length"
          class="similar-block"
        >
          <p class="similar-title">??????</p>
          <ul class="similar-list" data-testid="browse-similar-list">
            <li v-for="s in similarItems" :key="s.id" class="similar-item">
              {{ s.name }} ? ?? {{ s.rating_avg ?? '??' }}
            </li>
          </ul>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { getCurrentUser } from '../utils/user';
import { getScenicSpots, getHotels, getFoods, createRating } from '../api/resources';
import { getSimilarScenicSpots } from '../api/recommend';
import { toast } from '../utils/toast';

const route = useRoute();
const isColdStartMode = route.query.mode === 'cold_start';

const type = ref('scenic');
const city = ref('');
const items = ref([]);
const loading = ref(false);
const error = ref('');

const similarFor = ref(null);
const similarItems = ref([]);
const similarLoadingId = ref(null);

function currentUserId() {
  const u = getCurrentUser();
  return u?.id ?? null;
}

async function fetchList() {
  loading.value = true;
  error.value = '';
  similarFor.value = null;
  similarItems.value = [];
  similarLoadingId.value = null;
  try {
    const params = { page: 1, page_size: 20 };
    if (city.value) params.city = city.value;

    let resp;
    if (type.value === 'scenic') {
      resp = await getScenicSpots(params);
    } else if (type.value === 'hotel') {
      resp = await getHotels(params);
    } else {
      resp = await getFoods(params);
    }

    items.value = resp.data.items || [];
  } catch (e) {
    error.value = e.response?.data?.error || '??????';
  } finally {
    loading.value = false;
  }
}

async function rateItem(item) {
  const uid = currentUserId();
  if (!uid) {
    toast.warning('?????????');
    return;
  }

  try {
    const payload = {
      user_id: uid,
      target_type:
        type.value === 'scenic'
          ? 'scenic_spot'
          : type.value === 'hotel'
          ? 'hotel'
          : 'food_place',
      target_id: item.id,
      score: 5,
      comment: '????',
    };
    await createRating(payload);
    toast.success('????????????????????');
  } catch (e) {
    toast.error(e.response?.data?.error || '????');
  }
}

async function loadSimilar(item) {
  if (!item || similarLoadingId.value) return;

  if (similarFor.value === item.id) {
    similarFor.value = null;
    similarItems.value = [];
    return;
  }

  similarLoadingId.value = item.id;
  similarItems.value = [];
  try {
    const resp = await getSimilarScenicSpots(item.id, { limit: 6 });
    const items = resp.data?.items || [];
    similarItems.value = items;
    similarFor.value = item.id;
    if (!items.length) {
      toast.info('????????');
    }
  } catch (e) {
    similarItems.value = [];
    similarFor.value = item.id;
    toast.error(e.response?.data?.error || '????????');
  } finally {
    similarLoadingId.value = null;
  }
}

onMounted(() => {
  fetchList();
});
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cold-start-tip {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
}

.cold-start-text {
  font-size: 13px;
  color: #1d4ed8;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
  background: #ffffff;
  padding: 12px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

label {
  display: flex;
  flex-direction: column;
  font-size: 14px;
}

input,
select {
  margin-top: 4px;
  padding: 6px 8px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
}

.card-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.card {
  background: #ffffff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.sub {
  font-size: 13px;
  color: #4b5563;
}

.desc {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}

button {
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 4px;
  border: none;
  background: #10b981;
  color: #ffffff;
}

.secondary {
  background: #e5e7eb;
  color: #374151;
}

.similar-block {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed #e5e7eb;
}

.similar-title {
  font-size: 13px;
  color: #4b5563;
  margin-bottom: 4px;
}

.similar-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.similar-item {
  font-size: 13px;
  color: #6b7280;
}

.error {
  color: #b91c1c;
  font-size: 13px;
}
</style>

