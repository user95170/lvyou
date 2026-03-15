<template>
  <div class="page">
    <h2>????</h2>

    <section class="block">
      <h3>?????</h3>
      <div
        v-if="pendingSpots.length > 0"
        class="pending-hint"
        data-testid="route-pending-hint"
      >
        <p>??????? {{ pendingSpots.length }} ??????????</p>
        <button type="button" class="btn-clear" @click="clearPending">???????</button>
      </div>
      <div class="filters">
        <label>
          ??
          <input
            v-model="city"
            data-testid="route-city-input"
            type="text"
            placeholder="??????????"
          />
        </label>
        <button
          type="button"
          data-testid="route-load-scenic"
          @click="loadScenic"
          :disabled="loadingScenic"
        >
          {{ loadingScenic ? '???...' : '????' }}
        </button>
      </div>
      <p class="hint">???????????????</p>

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
              <div class="sub">{{ spot.city }} ? {{ spot.type || '??' }}</div>
              <div class="desc">{{ spot.description?.slice(0, 60) || spot.tags || '???????????' }}</div>
            </div>
          </label>
        </li>
      </ul>
    </section>

    <section class="block">
      <h3>????</h3>
      <div class="filters">
        <label>
          ????
          <select v-model="optimizeMode">
            <option value="greedy">??</option>
            <option value="2opt">2-opt</option>
            <option value="balanced">??</option>
          </select>
        </label>
        <button type="button" data-testid="route-plan-btn" @click="doPlan" :disabled="planning">
          {{ planning ? '???...' : '????' }}
        </button>
      </div>
      <p class="hint">???? 2-opt ?????????</p>

      <div v-if="planError" class="error">{{ planError }}</div>
      <div v-if="route.length" class="route" data-testid="route-result">
        <p class="hint">????????????{{ algorithmUsed }}??</p>
        <ol>
          <li v-for="(spot, idx) in route" :key="spot.id">
            <strong>? {{ idx + 1 }} ??</strong>{{ spot.name }}?{{ spot.city }}?
          </li>
        </ol>
        <p v-if="totalDistance != null" class="meta">??????{{ totalDistance }} km</p>
      </div>
    </section>

    <section class="block">
      <h3>?????AMap?</h3>
      <div class="filters">
        <label>
          ????
          <input v-model="optOriginLng" type="number" step="0.000001" placeholder="116.4343" />
        </label>
        <label>
          ????
          <input v-model="optOriginLat" type="number" step="0.000001" placeholder="39.9091" />
        </label>
        <label>
          ????
          <input v-model="optDestLng" type="number" step="0.000001" placeholder="116.4344" />
        </label>
        <label>
          ????
          <input v-model="optDestLat" type="number" step="0.000001" placeholder="39.9082" />
        </label>
        <label>
          ??
          <select v-model="optMode">
            <option value="drive">drive</option>
            <option value="transit">transit</option>
            <option value="walk">walk</option>
          </select>
        </label>
        <label>
          API ??
          <select v-model="optApiVersion">
            <option value="v5">v5</option>
            <option value="v3">v3</option>
          </select>
        </label>
      </div>

      <div class="filters" v-if="optMode === 'drive'">
        <label>
          ????
          <input v-model="optDriveStrategy" type="text" placeholder="?? 32(v5) / 10(v3)" />
        </label>
        <div>
          <div style="font-size: 14px">?????? 16 ??</div>
          <div
            v-for="(wp, i) in optWaypoints"
            :key="i"
            style="display:flex;gap:6px;margin:4px 0;align-items:center;"
          >
            <input
              v-model="optWaypoints[i]"
              type="text"
              placeholder="lng,lat ?? 116.401,39.901"
              style="flex:1"
            />
            <button type="button" @click="removeWaypoint(i)" style="background:#ef4444">??</button>
          </div>
          <button type="button" @click="addWaypoint">+ ?????</button>
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
          ????
          <input v-model="optTransitStrategy" type="text" placeholder="0..8" />
        </label>
        <label>
          AlternativeRoute
          <input v-model.number="optAlternativeRoute" type="number" min="1" max="10" placeholder="1..10" />
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
          {{ optLoading ? '???...' : '??????' }}
        </button>
        <button type="button" @click="resetRouteOptions" style="background:#6b7280">??</button>
      </div>
      <div v-if="optError" class="error">{{ optError }}</div>
      <ul v-if="optResult.length" class="card-list">
        <li v-for="(o, idx) in optResult" :key="idx" class="card">
          <div class="card-inner">
            <div>
              <div class="title">{{ o.label || ('??' + (idx + 1)) }}</div>
              <div class="sub">?? {{ o.duration_min ?? '-' }} ?? ? ?? {{ o.distance_km ?? '-' }} km</div>
            </div>
          </div>
        </li>
      </ul>
    </section>

    <section class="block">
      <h3>????????</h3>
      <div class="filters">
        <button type="button" @click="loadMetrics" :disabled="metricsLoading">
          {{ metricsLoading ? '???...' : '????' }}
        </button>
      </div>
      <div v-if="metricsError" class="error">{{ metricsError }}</div>
      <div v-if="summary" style="margin-top: 8px">
        <p class="hint">
          ????? {{ summary.amap_success_total || 0 }} ? ?? {{ summary.amap_fail_total || 0 }} ? ??? {{ summary.amap_success_rate ?? 0 }}
        </p>
        <p class="hint">???{{ summary.source_breakdown }}</p>
        <p class="hint">???Distance {{ summary.fallback_amap_distance || 0 }} ? Haversine {{ summary.fallback_haversine || 0 }}</p>
        <p class="hint">???hit {{ summary.amap_cache_hit || 0 }} / miss {{ summary.amap_cache_miss || 0 }} ? ???? {{ summary.amap_rate_limited_skips || 0 }}</p>
        <p class="hint">citycode ???{{ summary.infer_citycode_used || 0 }}</p>
        <div v-if="summary.top_fail_infocode && summary.top_fail_infocode.length">
          <div class="title" style="margin-top: 8px">Top ?? infocode</div>
          <ul>
            <li v-for="(it, i) in summary.top_fail_infocode" :key="i">{{ it[0] }}?{{ it[1] }}</li>
          </ul>
        </div>
        <div v-if="summary.top_fail_modes && summary.top_fail_modes.length">
          <div class="title" style="margin-top: 8px">Top ????</div>
          <ul>
            <li v-for="(it, i) in summary.top_fail_modes" :key="i">{{ it[0] }}?{{ it[1] }}</li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { getScenicSpots } from '../api/resources';
import { planRoute, routeOptions, routeMetrics } from '../api/route';
import { getPendingSpots, clearPendingSpots } from '../utils/trip';
import { toast } from '../utils/toast';

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

// Route Options (AMap)
const optOriginLng = ref('');
const optOriginLat = ref('');
const optDestLng = ref('');
const optDestLat = ref('');
const optMode = ref('drive');
const optApiVersion = ref('v5');
const optDriveStrategy = ref('');
const optWaypoints = ref([]); // array of "lng,lat" strings

// transit extras
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

function addWaypoint() {
  if (optWaypoints.value.length >= 16) {
    toast.error('????? 16 ?');
    return;
  }
  optWaypoints.value.push('');
}

function removeWaypoint(i) {
  optWaypoints.value.splice(i, 1);
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
  const nums = [optOriginLng.value, optOriginLat.value, optDestLng.value, optDestLat.value].map((v) =>
    parseFloat(String(v))
  );
  if (nums.some((v) => Number.isNaN(v))) {
    optError.value = '????????????';
    return;
  }

  const payload = {
    origin: { lng: parseFloat(optOriginLng.value), lat: parseFloat(optOriginLat.value) },
    destination: { lng: parseFloat(optDestLng.value), lat: parseFloat(optDestLat.value) },
    mode: optMode.value,
    api_version: optApiVersion.value,
  };

  if (optMode.value === 'drive') {
    if (optDriveStrategy.value) payload.drive_strategy = String(optDriveStrategy.value);
    if (optWaypoints.value.length) payload.waypoints = optWaypoints.value.slice();
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
      toast.error('???????');
    }
  } catch (e) {
    const msg = e.response?.data?.error || '????????';
    optError.value = msg;
    toast.error(msg);
  } finally {
    optLoading.value = false;
  }
}

const metricsLoading = ref(false);
const metricsError = ref('');
const summary = ref(null);

async function loadMetrics() {
  metricsError.value = '';
  summary.value = null;
  metricsLoading.value = true;
  try {
    const resp = await routeMetrics();
    summary.value = resp.data?.summary || null;
  } catch (e) {
    metricsError.value = e.response?.data?.error || '??????';
  } finally {
    metricsLoading.value = false;
  }
}

async function loadScenic() {
  loadingScenic.value = true;
  scenicError.value = '';
  scenicList.value = [];
  selectedIds.value = [];
  try {
    const params = { page: 1, page_size: 30 };
    if (city.value) params.city = city.value;
    const resp = await getScenicSpots(params);
    scenicList.value = resp.data.items || [];
  } catch (e) {
    const errorMsg = e.response?.data?.error || '????????';
    scenicError.value = errorMsg;
    toast.error(errorMsg);
  } finally {
    loadingScenic.value = false;
  }
}

async function doPlan() {
  planError.value = '';
  route.value = [];
  totalDistance.value = null;
  algorithmUsed.value = '';

  if (selectedIds.value.length < 2) {
    planError.value = '???????????????';
    return;
  }

  planning.value = true;
  try {
    const payload = {
      spot_ids: selectedIds.value,
      optimize: optimizeMode.value,
    };
    const resp = await planRoute(payload);
    route.value = resp.data.route || [];
    totalDistance.value = resp.data.meta?.total_distance_km ?? null;
    algorithmUsed.value = resp.data.meta?.algorithm || optimizeMode.value;
  } catch (e) {
    const errorMsg = e.response?.data?.error || '??????';
    planError.value = errorMsg;
    toast.error(errorMsg);
  } finally {
    planning.value = false;
  }
}

function loadPendingSpots() {
  pendingSpots.value = getPendingSpots();
  if (pendingSpots.value.length > 0) {
    scenicList.value = [...pendingSpots.value, ...scenicList.value];
    selectedIds.value = pendingSpots.value.map((s) => s.id);
  }
}

function clearPending() {
  if (!confirm('????????????')) {
    return;
  }
  clearPendingSpots();
  pendingSpots.value = [];
  if (city.value) {
    loadScenic();
  }
  toast.success('????????');
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

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
}

label {
  font-size: 14px;
}

input[type='text'], select {
  margin-top: 4px;
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
  padding: 8px 12px;
  border-radius: 4px;
  border: none;
  background: #2563eb;
  color: #ffffff;
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
  margin: 0 0 8px 0;
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
  cursor: pointer;
}

.btn-clear:hover {
  background: #dc2626;
  color: #ffffff;
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
</style>

