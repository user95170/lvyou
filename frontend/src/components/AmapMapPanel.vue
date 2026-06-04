<template>
  <div class="map-shell">
    <div
      v-if="errorState === 'config'"
      class="map-state map-state-error"
      :data-testid="`${testIdPrefix}-config-error`"
    >
      {{ configErrorMessage }}
    </div>
    <div
      v-else-if="errorState === 'load'"
      class="map-state map-state-error"
      :data-testid="`${testIdPrefix}-load-error`"
    >
      {{ loadErrorMessage }}
    </div>
    <div
      v-else-if="normalizedPoints.length === 0"
      class="map-state"
      :data-testid="`${testIdPrefix}-empty`"
    >
      {{ emptyMessage }}
    </div>
    <div
      v-else-if="loading"
      class="map-state"
      :data-testid="`${testIdPrefix}-loading`"
    >
      地图加载中...
    </div>
    <div
      v-show="normalizedPoints.length > 0 && errorState === ''"
      ref="mapContainer"
      class="map-canvas"
      :style="canvasStyle"
      :data-testid="`${testIdPrefix}-canvas`"
    ></div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { loadAmapSdk } from '../utils/amap';

const props = defineProps({
  points: {
    type: Array,
    default: () => [],
  },
  height: {
    type: [Number, String],
    default: 320,
  },
  emptyMessage: {
    type: String,
    default: '当前暂无可上图点位',
  },
  configErrorMessage: {
    type: String,
    default: '未配置高德地图 Key，暂无法显示地图。',
  },
  loadErrorMessage: {
    type: String,
    default: '地图加载失败，请稍后重试。',
  },
  testIdPrefix: {
    type: String,
    default: 'amap-map',
  },
});

const mapContainer = ref(null);
const mapInstance = ref(null);
const overlays = ref([]);
const loading = ref(false);
const errorState = ref('');
let syncToken = 0;

const canvasStyle = computed(() => ({
  height: typeof props.height === 'number' ? `${props.height}px` : props.height,
}));

const normalizedPoints = computed(() =>
  (Array.isArray(props.points) ? props.points : [])
    .map((point, index) => {
      const longitude =
        point?.longitude === '' || point?.longitude == null ? NaN : Number(point?.longitude);
      const latitude =
        point?.latitude === '' || point?.latitude == null ? NaN : Number(point?.latitude);
      if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
        return null;
      }
      return {
        id: point?.id ?? `point-${index + 1}`,
        order: point?.order ?? index + 1,
        title: point?.title || `第 ${index + 1} 站`,
        longitude,
        latitude,
      };
    })
    .filter(Boolean)
);

function clearOverlays() {
  if (!mapInstance.value) {
    overlays.value = [];
    return;
  }

  if (typeof mapInstance.value.clearMap === 'function') {
    mapInstance.value.clearMap();
  } else if (typeof mapInstance.value.remove === 'function' && overlays.value.length) {
    mapInstance.value.remove(overlays.value);
  }
  overlays.value = [];
}

function buildMarkerContent(order) {
  return [
    '<div style="display:flex;align-items:center;justify-content:center;',
    'width:28px;height:28px;border-radius:999px;background:#2563eb;color:#fff;',
    'font-weight:700;font-size:13px;box-shadow:0 4px 10px rgba(37,99,235,0.28);">',
    String(order),
    '</div>',
  ].join('');
}

async function ensureMap() {
  if (!mapContainer.value) {
    return null;
  }

  const AMap = await loadAmapSdk();
  if (!mapInstance.value) {
    mapInstance.value = new AMap.Map(mapContainer.value, {
      zoom: 11,
      resizeEnable: true,
      viewMode: '2D',
      center: [normalizedPoints.value[0].longitude, normalizedPoints.value[0].latitude],
    });
  }
  return AMap;
}

async function syncMap() {
  const currentToken = syncToken + 1;
  syncToken = currentToken;

  if (normalizedPoints.value.length === 0) {
    errorState.value = '';
    clearOverlays();
    return;
  }

  loading.value = true;
  try {
    const AMap = await ensureMap();
    if (!AMap || currentToken !== syncToken) {
      return;
    }

    errorState.value = '';
    clearOverlays();

    const nextOverlays = normalizedPoints.value.map((point) =>
      new AMap.Marker({
        position: [point.longitude, point.latitude],
        title: `${point.order}. ${point.title}`,
        content: buildMarkerContent(point.order),
        anchor: 'bottom-center',
      })
    );

    if (normalizedPoints.value.length > 1) {
      nextOverlays.push(
        new AMap.Polyline({
          path: normalizedPoints.value.map((point) => [point.longitude, point.latitude]),
          strokeColor: '#2563eb',
          strokeWeight: 4,
          strokeOpacity: 0.85,
          strokeStyle: 'solid',
        })
      );
    }

    overlays.value = nextOverlays;
    if (typeof mapInstance.value.add === 'function') {
      mapInstance.value.add(nextOverlays);
    }

    await nextTick();
    if (typeof mapInstance.value.setFitView === 'function') {
      mapInstance.value.setFitView(nextOverlays);
    }
  } catch (error) {
    errorState.value =
      error?.message === 'AMap key is not configured' ? 'config' : 'load';
  } finally {
    if (currentToken === syncToken) {
      loading.value = false;
    }
  }
}

watch(
  normalizedPoints,
  () => {
    if (!mapContainer.value) {
      return;
    }
    void syncMap();
  },
  { deep: true }
);

onMounted(() => {
  void syncMap();
});

onBeforeUnmount(() => {
  clearOverlays();
  if (typeof mapInstance.value?.destroy === 'function') {
    mapInstance.value.destroy();
  }
  mapInstance.value = null;
});
</script>

<style scoped>
.map-shell {
  margin-top: 12px;
}

.map-canvas,
.map-state {
  border-radius: 10px;
  border: 1px solid #dbeafe;
}

.map-canvas {
  width: 100%;
  min-height: 240px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.18), transparent 36%),
    linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%);
}

.map-state {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  color: #475569;
  background: linear-gradient(180deg, #f8fafc 0%, #eff6ff 100%);
  text-align: center;
}

.map-state-error {
  border-color: #fecaca;
  background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%);
  color: #b91c1c;
}
</style>
