<template>
  <div class="page">
    <section class="block">
      <h2>行程规划</h2>
      <h3>选择景点</h3>

      <div
        v-if="pendingSpots.length > 0"
        class="pending-hint"
        data-testid="route-pending-hint"
      >
        <p>你有 {{ pendingSpots.length }} 个待规划景点，已经自动加入当前候选列表。</p>
        <button type="button" class="btn-clear" @click="clearPending">清空待规划</button>
      </div>

      <div class="filters">
        <label>
          城市
          <input
            v-model="city"
            data-testid="route-city-input"
            type="text"
            placeholder="输入城市后加载景点"
          />
        </label>
        <button
          type="button"
          data-testid="route-load-scenic"
          @click="loadScenic"
          :disabled="loadingScenic"
        >
          {{ loadingScenic ? '加载中...' : '加载景点' }}
        </button>
      </div>

      <p class="hint">至少选择 2 个景点后才能生成路线。</p>

      <div v-if="scenicError" class="error">{{ scenicError }}</div>

      <ul v-else class="card-list">
        <li v-for="spot in scenicList" :key="spot.id" class="card">
          <label class="card-inner">
            <input
              v-model="selectedIds"
              data-testid="route-spot-checkbox"
              :value="spot.id"
              type="checkbox"
            />
            <div>
              <div class="title">{{ spot.name }}</div>
              <div class="sub">{{ spot.city }} · {{ spot.type || '未分类' }}</div>
              <div class="desc">
                {{ spot.description?.slice(0, 60) || spot.tags || '暂无更多介绍' }}
              </div>
            </div>
          </label>
        </li>
      </ul>
    </section>

    <section class="block">
      <h3>生成路线</h3>

      <div class="filters">
        <label>
          优化模式
          <select v-model="optimizeMode">
            <option value="greedy">greedy</option>
            <option value="2opt">2-opt</option>
            <option value="balanced">balanced</option>
          </select>
        </label>
        <button type="button" data-testid="route-plan-btn" @click="doPlan" :disabled="planning">
          {{ planning ? '规划中...' : '开始规划' }}
        </button>
      </div>

      <div class="filters location-row">
        <label class="inline">
          <input type="checkbox" v-model="useMyLocation" />
          从我的当前位置出发
        </label>
        <button
          type="button"
          class="secondary"
          data-testid="route-locate-btn"
          @click="locateMe"
          :disabled="locating"
        >
          {{ locating ? '定位中...' : '获取我的位置' }}
        </button>
        <span v-if="userLocation" class="hint">
          已获取位置：{{ userLocation.lng.toFixed(5) }}, {{ userLocation.lat.toFixed(5) }}
        </span>
      </div>

      <p class="hint">`2-opt` 通常能得到更短的路线，`balanced` 会兼顾距离和热度；勾选定位后将以你的位置为起点。</p>

      <div v-if="planError" class="error">{{ planError }}</div>

      <div v-if="route.length" class="route" data-testid="route-result">
        <p class="hint">当前结果使用算法：{{ algorithmUsed || optimizeMode }}</p>
        <ol>
          <li v-for="(spot, idx) in route" :key="`${spot.id}-${idx}`">
            <strong>第 {{ idx + 1 }} 站：</strong>{{ spot.name }}（{{ spot.city || '未知城市' }}）
          </li>
        </ol>
        <p v-if="totalDistance != null" class="meta">估算总路程：{{ totalDistance }} km</p>
      </div>
    </section>

    <section
      v-if="route.length"
      class="block"
      data-testid="route-map-section"
    >
      <div class="section-header">
        <div>
          <h3>路线地图</h3>
          <p class="hint">按当前规划顺序展示可上图点位与连线预览。</p>
        </div>
        <span class="map-summary">可上图 {{ routeMapPoints.length }}/{{ route.length }}</span>
      </div>

      <AmapMapPanel
        :points="routeMapPoints"
        test-id-prefix="route-map"
        empty-message="当前路线结果暂无可上图点位"
        config-error-message="未配置高德地图 Key，暂时无法显示路线地图。"
      />
    </section>

    <section
      v-if="route.length"
      class="block save-block"
      data-testid="route-save-section"
    >
      <h3>保存为行程</h3>

      <div v-if="currentUser?.id">
        <div class="field-grid">
          <label>
            行程标题
            <input
              v-model="saveTitle"
              data-testid="route-save-title-input"
              type="text"
              placeholder="请输入行程标题"
            />
          </label>

          <label>
            出发日期
            <input
              v-model="saveStartDate"
              data-testid="route-save-date-input"
              type="date"
            />
          </label>
        </div>

        <p class="hint">保存后会跳转到行程详情页，可继续调整顺序、时间和备注。</p>

        <button
          type="button"
          data-testid="route-save-btn"
          @click="saveRouteAsTrip"
          :disabled="savingTrip"
        >
          {{ savingTrip ? '保存中...' : '保存行程' }}
        </button>
      </div>

      <div v-else class="save-login-hint" data-testid="route-login-hint">
        <p>登录后可将本次路线保存到“我的行程”。</p>
        <router-link to="/login" class="link-button">前往登录</router-link>
      </div>
    </section>

    <section class="block">
      <h3>路线方案（AMap）</h3>

      <div class="filters">
        <label>
          起点经度
          <input v-model="optOriginLng" type="number" step="0.000001" placeholder="116.4343" />
        </label>
        <label>
          起点纬度
          <input v-model="optOriginLat" type="number" step="0.000001" placeholder="39.9091" />
        </label>
        <label>
          终点经度
          <input v-model="optDestLng" type="number" step="0.000001" placeholder="116.4344" />
        </label>
        <label>
          终点纬度
          <input v-model="optDestLat" type="number" step="0.000001" placeholder="39.9082" />
        </label>
        <label>
          模式
          <select v-model="optMode">
            <option value="drive">drive</option>
            <option value="transit">transit</option>
            <option value="walk">walk</option>
          </select>
        </label>
        <label>
          API 版本
          <select v-model="optApiVersion">
            <option value="v5">v5</option>
            <option value="v3">v3</option>
          </select>
        </label>
      </div>

      <div class="filters" v-if="optMode === 'drive'">
        <label>
          驾车策略
          <input v-model="optDriveStrategy" type="text" placeholder="例如 32(v5) / 10(v3)" />
        </label>

        <div class="waypoint-editor">
          <div class="sub-title">途经点（最多 16 个）</div>
          <div
            v-for="(waypoint, index) in optWaypoints"
            :key="index"
            class="waypoint-row"
          >
            <input
              v-model="optWaypoints[index]"
              type="text"
              placeholder="lng,lat 例如 116.401,39.901"
            />
            <button type="button" class="danger" @click="removeWaypoint(index)">删除</button>
          </div>
          <button type="button" @click="addWaypoint">+ 添加途经点</button>
        </div>
      </div>

      <div class="filters" v-if="optMode === 'transit'">
        <label>
          city1
          <input v-model="optCity1" type="text" placeholder="010" />
        </label>
        <label>
          city2
          <input v-model="optCity2" type="text" placeholder="010" />
        </label>
        <label>
          ad1
          <input v-model="optAd1" type="text" placeholder="110105" />
        </label>
        <label>
          ad2
          <input v-model="optAd2" type="text" placeholder="110108" />
        </label>
        <label>
          公交策略
          <input v-model="optTransitStrategy" type="text" placeholder="0..8" />
        </label>
        <label>
          AlternativeRoute
          <input v-model.number="optAlternativeRoute" type="number" min="1" max="10" />
        </label>
        <label>
          multiexport
          <select v-model.number="optMultiexport">
            <option :value="0">0</option>
            <option :value="1">1</option>
          </select>
        </label>
        <label>
          nightflag
          <select v-model.number="optNightflag">
            <option :value="0">0</option>
            <option :value="1">1</option>
          </select>
        </label>
      </div>

      <div class="filters">
        <button type="button" @click="doRouteOptions" :disabled="optLoading">
          {{ optLoading ? '计算中...' : '获取方案' }}
        </button>
        <button type="button" class="secondary" @click="resetRouteOptions">重置</button>
      </div>

      <div v-if="optError" class="error">{{ optError }}</div>

      <ul v-if="optResult.length" class="card-list">
        <li v-for="(option, index) in optResult" :key="index" class="card">
          <div class="card-inner">
            <div>
              <div class="title">{{ option.label || `方案 ${index + 1}` }}</div>
              <div class="sub">
                耗时 {{ option.duration_min ?? '-' }} 分钟 · 距离 {{ option.distance_km ?? '-' }} km
              </div>
            </div>
          </div>
        </li>
      </ul>
    </section>

    <section class="block">
      <h3>路线运行指标</h3>

      <div class="filters">
        <button type="button" @click="loadMetrics" :disabled="metricsLoading">
          {{ metricsLoading ? '加载中...' : '刷新指标' }}
        </button>
      </div>

      <div v-if="metricsError" class="error">{{ metricsError }}</div>

      <div v-if="summary" class="metrics-summary">
        <p class="hint">
          AMap 成功 {{ summary.amap_success_total || 0 }} 次，失败 {{ summary.amap_fail_total || 0 }} 次，成功率 {{ summary.amap_success_rate ?? 0 }}
        </p>
        <p class="hint">来源分布：{{ summary.source_breakdown }}</p>
        <p class="hint">
          回退统计：Distance API {{ summary.fallback_amap_distance || 0 }} 次，Haversine {{ summary.fallback_haversine || 0 }} 次
        </p>
        <p class="hint">
          缓存命中 {{ summary.amap_cache_hit || 0 }} / 未命中 {{ summary.amap_cache_miss || 0 }}，限流跳过 {{ summary.amap_rate_limited_skips || 0 }}
        </p>
        <p class="hint">citycode 推断使用 {{ summary.infer_citycode_used || 0 }} 次</p>

        <div v-if="summary.top_fail_infocode?.length">
          <div class="title extra-title">Top 失败 infocode</div>
          <ul>
            <li v-for="(item, index) in summary.top_fail_infocode" :key="index">
              {{ item[0] }}：{{ item[1] }}
            </li>
          </ul>
        </div>

        <div v-if="summary.top_fail_modes?.length">
          <div class="title extra-title">Top 失败模式</div>
          <ul>
            <li v-for="(item, index) in summary.top_fail_modes" :key="index">
              {{ item[0] }}：{{ item[1] }}
            </li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import AmapMapPanel from '../components/AmapMapPanel.vue';
import { getScenicSpots } from '../api/resources';
import { planRoute, routeMetrics, routeOptions } from '../api/route';
import { createTrip } from '../api/trips';
import { toast } from '../utils/toast';
import { getPendingSpots, clearPendingSpots } from '../utils/trip';
import { getCurrentUser } from '../utils/user';

const router = useRouter();
const currentUser = getCurrentUser();

const city = ref('');
const scenicList = ref([]);
const selectedIds = ref([]);

const loadingScenic = ref(false);
const planning = ref(false);

const scenicError = ref('');
const planError = ref('');

const route = ref([]);
const totalDistance = ref(null);
const pendingSpots = ref([]);
const optimizeMode = ref('2opt');
const algorithmUsed = ref('');

const saveTitle = ref('');
const saveStartDate = ref('');
const savingTrip = ref(false);

const useMyLocation = ref(false);
const userLocation = ref(null);
const locating = ref(false);

const optOriginLng = ref('');
const optOriginLat = ref('');
const optDestLng = ref('');
const optDestLat = ref('');
const optMode = ref('drive');
const optApiVersion = ref('v5');
const optDriveStrategy = ref('');
const optWaypoints = ref([]);

const optCity1 = ref('');
const optCity2 = ref('');
const optAd1 = ref('');
const optAd2 = ref('');
const optTransitStrategy = ref('');
const optAlternativeRoute = ref(null);
const optMultiexport = ref(null);
const optNightflag = ref(null);

const optLoading = ref(false);
const optError = ref('');
const optResult = ref([]);

const metricsLoading = ref(false);
const metricsError = ref('');
const summary = ref(null);

function normalizeCoordinate(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
}

const routeMapPoints = computed(() =>
  route.value
    .map((spot, index) => {
      const longitude = normalizeCoordinate(spot?.longitude);
      const latitude = normalizeCoordinate(spot?.latitude);
      if (longitude == null || latitude == null) {
        return null;
      }
      return {
        id: spot?.id ?? `route-point-${index + 1}`,
        order: index + 1,
        title: spot?.name || `第 ${index + 1} 站`,
        longitude,
        latitude,
      };
    })
    .filter(Boolean)
);

function mergeUniqueSpots(...groups) {
  const merged = [];
  const seen = new Set();

  groups.flat().forEach((spot) => {
    if (!spot || seen.has(spot.id)) {
      return;
    }
    seen.add(spot.id);
    merged.push(spot);
  });

  return merged;
}

function refreshDefaultSaveTitle(plannedRoute = route.value) {
  const fallbackCity = city.value.trim() || plannedRoute?.[0]?.city || '';
  saveTitle.value = fallbackCity ? `${fallbackCity}一日游路线` : '一日游路线';
}

function getTripOriginCity(plannedRoute = route.value) {
  return city.value.trim() || plannedRoute?.[0]?.city || '';
}

function addWaypoint() {
  if (optWaypoints.value.length >= 16) {
    toast.error('途经点最多 16 个');
    return;
  }
  optWaypoints.value.push('');
}

function removeWaypoint(index) {
  optWaypoints.value.splice(index, 1);
}

function resetRouteOptions() {
  optOriginLng.value = '';
  optOriginLat.value = '';
  optDestLng.value = '';
  optDestLat.value = '';
  optMode.value = 'drive';
  optApiVersion.value = 'v5';
  optDriveStrategy.value = '';
  optWaypoints.value = [];
  optCity1.value = '';
  optCity2.value = '';
  optAd1.value = '';
  optAd2.value = '';
  optTransitStrategy.value = '';
  optAlternativeRoute.value = null;
  optMultiexport.value = null;
  optNightflag.value = null;
  optResult.value = [];
  optError.value = '';
}

async function doRouteOptions() {
  optError.value = '';
  optResult.value = [];

  const nums = [optOriginLng.value, optOriginLat.value, optDestLng.value, optDestLat.value].map((value) =>
    parseFloat(String(value))
  );
  if (nums.some((value) => Number.isNaN(value))) {
    optError.value = '请输入完整且合法的起终点坐标';
    return;
  }

  const payload = {
    origin: { lng: parseFloat(optOriginLng.value), lat: parseFloat(optOriginLat.value) },
    destination: { lng: parseFloat(optDestLng.value), lat: parseFloat(optDestLat.value) },
    mode: optMode.value,
    api_version: optApiVersion.value,
  };

  if (optMode.value === 'drive') {
    if (optDriveStrategy.value) {
      payload.drive_strategy = String(optDriveStrategy.value);
    }
    if (optWaypoints.value.length) {
      payload.waypoints = optWaypoints.value.slice();
    }
  } else if (optMode.value === 'transit') {
    if (optCity1.value) payload.city1 = String(optCity1.value);
    if (optCity2.value) payload.city2 = String(optCity2.value);
    if (optAd1.value) payload.ad1 = String(optAd1.value);
    if (optAd2.value) payload.ad2 = String(optAd2.value);
    if (optTransitStrategy.value) payload.transit_strategy = String(optTransitStrategy.value);
    if (optAlternativeRoute.value != null) payload.alternative_route = Number(optAlternativeRoute.value);
    if (optMultiexport.value != null) payload.multiexport = Number(optMultiexport.value);
    if (optNightflag.value != null) payload.nightflag = Number(optNightflag.value);
  }

  optLoading.value = true;
  try {
    const resp = await routeOptions(payload);
    optResult.value = resp.data.options || [];
    if (!optResult.value.length) {
      toast.error('未返回可用路线方案');
    }
  } catch (e) {
    const msg = e.response?.data?.error || '获取路线方案失败';
    optError.value = msg;
    toast.error(msg);
  } finally {
    optLoading.value = false;
  }
}

async function loadMetrics() {
  metricsError.value = '';
  summary.value = null;
  metricsLoading.value = true;
  try {
    const resp = await routeMetrics();
    summary.value = resp.data?.summary || null;
  } catch (e) {
    metricsError.value = e.response?.data?.error || '加载指标失败';
  } finally {
    metricsLoading.value = false;
  }
}

async function loadScenic() {
  loadingScenic.value = true;
  scenicError.value = '';
  scenicList.value = [];
  selectedIds.value = pendingSpots.value.map((spot) => spot.id);

  try {
    const params = { page: 1, page_size: 30 };
    if (city.value) {
      params.city = city.value;
    }
    const resp = await getScenicSpots(params);
    scenicList.value = mergeUniqueSpots(pendingSpots.value, resp.data.items || []);
  } catch (e) {
    const errorMsg = e.response?.data?.error || '加载景点失败';
    scenicError.value = errorMsg;
    toast.error(errorMsg);
  } finally {
    loadingScenic.value = false;
  }
}

function locateMe() {
  if (typeof navigator === 'undefined' || !navigator.geolocation) {
    toast.error('当前浏览器不支持定位');
    return;
  }
  locating.value = true;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      userLocation.value = {
        lng: pos.coords.longitude,
        lat: pos.coords.latitude,
      };
      useMyLocation.value = true;
      locating.value = false;
      toast.success('已获取你的当前位置');
    },
    (err) => {
      locating.value = false;
      toast.error(err?.message || '定位失败，请检查浏览器定位权限');
    },
    { enableHighAccuracy: true, timeout: 8000 }
  );
}

async function doPlan() {
  planError.value = '';
  route.value = [];
  totalDistance.value = null;
  algorithmUsed.value = '';

  if (selectedIds.value.length < 2) {
    planError.value = '请至少勾选两个景点再规划路线';
    return;
  }

  if (useMyLocation.value && !userLocation.value) {
    planError.value = '请先点击“获取我的位置”，或取消勾选从当前位置出发';
    return;
  }

  planning.value = true;
  try {
    const payload = {
      spot_ids: selectedIds.value,
      optimize: optimizeMode.value,
    };
    if (useMyLocation.value && userLocation.value) {
      payload.start_location = {
        lng: userLocation.value.lng,
        lat: userLocation.value.lat,
      };
    }
    const resp = await planRoute(payload);
    route.value = resp.data.route || [];
    totalDistance.value = resp.data.meta?.total_distance_km ?? null;
    algorithmUsed.value = resp.data.meta?.algorithm || optimizeMode.value;
    refreshDefaultSaveTitle(route.value);
  } catch (e) {
    const errorMsg = e.response?.data?.error || '路线规划失败';
    planError.value = errorMsg;
    toast.error(errorMsg);
  } finally {
    planning.value = false;
  }
}

async function saveRouteAsTrip() {
  if (!currentUser?.id) {
    return;
  }

  if (!route.value.length) {
    toast.error('请先生成路线');
    return;
  }

  const originCity = getTripOriginCity(route.value);
  if (!originCity) {
    toast.error('无法识别城市，请先输入城市后再保存');
    return;
  }

  const title = (saveTitle.value || '').trim() || `${originCity}一日游路线`;
  const startDate = saveStartDate.value || null;

  const payload = {
    user_id: currentUser.id,
    title,
    start_date: startDate,
    origin_city: originCity,
    created_by: 'route_planner',
    trip_days: [
      {
        day_index: 1,
        date: startDate,
        note: null,
        items: route.value
          .filter((spot) => !spot.is_origin)
          .map((spot, index) => ({
            item_index: index + 1,
            item_type: 'scenic_spot',
            ref_id: spot.id ?? null,
            title_snapshot: spot.name || `景点${index + 1}`,
            city_snapshot: spot.city || originCity,
            address_snapshot: spot.address || null,
            start_time: null,
            end_time: null,
            transport_mode: null,
            note: null,
          })),
      },
    ],
  };

  savingTrip.value = true;
  try {
    const resp = await createTrip(payload);
    const tripId = resp.data?.trip?.id;
    toast.success('行程已保存');
    if (tripId) {
      router.push(`/trips/${tripId}`);
    } else {
      router.push('/trips');
    }
  } catch (e) {
    const msg = e.response?.data?.error || '保存行程失败';
    toast.error(msg);
  } finally {
    savingTrip.value = false;
  }
}

function loadPendingSpots() {
  pendingSpots.value = getPendingSpots();
  if (pendingSpots.value.length > 0) {
    scenicList.value = mergeUniqueSpots(pendingSpots.value, scenicList.value);
    selectedIds.value = Array.from(new Set(pendingSpots.value.map((spot) => spot.id)));
    if (!city.value && pendingSpots.value[0]?.city) {
      city.value = pendingSpots.value[0].city;
    }
  }
}

function clearPending() {
  if (!confirm('确定要清空待规划景点吗？')) {
    return;
  }

  const pendingIds = new Set(pendingSpots.value.map((spot) => spot.id));
  clearPendingSpots();
  scenicList.value = scenicList.value.filter((spot) => !pendingIds.has(spot.id));
  selectedIds.value = selectedIds.value.filter((id) => !pendingIds.has(id));
  pendingSpots.value = [];

  if (city.value) {
    loadScenic();
  }

  toast.success('待规划景点已清空');
}

onMounted(() => {
  loadPendingSpots();
});
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.block {
  background: #ffffff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.filters,
.field-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.map-summary {
  padding: 6px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 600;
}

.field-grid label {
  min-width: min(260px, 100%);
}

label {
  font-size: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

input,
select {
  padding: 6px 8px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
  background: #ffffff;
  font-size: 14px;
}

.card-list {
  list-style: none;
  padding: 0;
  margin: 12px 0 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.card {
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}

.card-inner {
  display: flex;
  gap: 8px;
  padding: 8px;
}

.title {
  font-weight: 600;
}

.sub,
.desc {
  font-size: 13px;
  color: #4b5563;
}

.desc {
  margin-top: 4px;
  color: #6b7280;
}

button,
.link-button {
  padding: 8px 12px;
  border-radius: 4px;
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

button.secondary {
  background: #6b7280;
}

button.danger {
  background: #dc2626;
}

.error {
  margin-top: 8px;
  color: #b91c1c;
  font-size: 13px;
}

.hint {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}

.pending-hint {
  margin-bottom: 12px;
  padding: 12px;
  border-radius: 6px;
  background: #dbeafe;
  border: 1px solid #3b82f6;
}

.pending-hint p {
  margin: 0 0 8px;
  font-size: 14px;
  color: #1e40af;
}

.btn-clear {
  padding: 4px 12px;
  font-size: 13px;
  border-radius: 4px;
  border: 1px solid #dc2626;
  background: #ffffff;
  color: #dc2626;
}

.route {
  margin-top: 12px;
}

.meta {
  margin-top: 8px;
  font-size: 14px;
  color: #059669;
  font-weight: 600;
}

.save-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.save-login-hint {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.waypoint-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.waypoint-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.waypoint-row input {
  flex: 1;
}

.sub-title {
  font-size: 14px;
  color: #374151;
}

.metrics-summary {
  margin-top: 8px;
}

.location-row {
  margin-top: 10px;
}

label.inline {
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.extra-title {
  margin-top: 8px;
}

@media (max-width: 768px) {
  .section-header,
  .waypoint-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
