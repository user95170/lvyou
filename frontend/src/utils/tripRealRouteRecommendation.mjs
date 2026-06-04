export const MAX_REAL_ROUTE_POINTS = 18;
export const MAX_REAL_ROUTE_CANDIDATES = 6;

function toNumericMetric(value) {
  if (value === '' || value == null) {
    return Number.POSITIVE_INFINITY;
  }
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : Number.POSITIVE_INFINITY;
}

export function normalizeCoordinate(value) {
  if (value === '' || value == null) {
    return null;
  }
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
}

export function hasRouteableCoordinates(item) {
  return (
    item != null &&
    normalizeCoordinate(item.longitude) != null &&
    normalizeCoordinate(item.latitude) != null
  );
}

function toRouteableEntry(item, index) {
  return {
    localKey: item?.localKey || `trip-item-${index + 1}`,
    title: item?.title_snapshot || `条目 ${index + 1}`,
    longitude: normalizeCoordinate(item?.longitude),
    latitude: normalizeCoordinate(item?.latitude),
    originalIndex: index,
    originalItem: item,
  };
}

function haversineDistanceKm(a, b) {
  const radiusKm = 6371;
  const lat1 = (a.latitude * Math.PI) / 180;
  const lat2 = (b.latitude * Math.PI) / 180;
  const deltaLat = ((b.latitude - a.latitude) * Math.PI) / 180;
  const deltaLng = ((b.longitude - a.longitude) * Math.PI) / 180;

  const haversine =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2;

  return 2 * radiusKm * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

function buildNearestNeighborOrder(entries, startEntry) {
  if (entries.length <= 1) {
    return [...entries];
  }

  const remaining = entries
    .filter((entry) => entry.localKey !== startEntry.localKey)
    .map((entry) => ({ ...entry }));
  const ordered = [{ ...startEntry }];

  while (remaining.length > 0) {
    const current = ordered[ordered.length - 1];
    let bestIndex = 0;
    let bestDistance = Number.POSITIVE_INFINITY;

    remaining.forEach((candidate, index) => {
      const distance = haversineDistanceKm(current, candidate);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = index;
      }
    });

    ordered.push(remaining.splice(bestIndex, 1)[0]);
  }

  return ordered;
}

function toCandidate(entries, candidateIndex) {
  const orderedEntries = entries.map((entry) => ({ ...entry }));
  const orderKeys = orderedEntries.map((entry) => entry.localKey);
  const summaryTitles = orderedEntries.map((entry) => entry.title);
  const waypoints = orderedEntries
    .slice(1, -1)
    .map((entry) => ({ lng: entry.longitude, lat: entry.latitude }));
  const payload = {
    mode: 'drive',
    api_version: 'v5',
    origin: {
      lng: orderedEntries[0].longitude,
      lat: orderedEntries[0].latitude,
    },
    destination: {
      lng: orderedEntries[orderedEntries.length - 1].longitude,
      lat: orderedEntries[orderedEntries.length - 1].latitude,
    },
  };
  if (waypoints.length > 0) {
    payload.waypoints = waypoints;
  }

  return {
    id: `candidate-${candidateIndex + 1}-${orderKeys.join('__')}`,
    orderKeys,
    orderedEntries,
    orderedItems: orderedEntries.map((entry) => entry.originalItem),
    summaryTitles,
    summaryText: summaryTitles.join(' -> '),
    payload,
  };
}

export function buildTripRealRouteCandidates(
  items = [],
  { maxCandidates = MAX_REAL_ROUTE_CANDIDATES, maxRouteablePoints = MAX_REAL_ROUTE_POINTS } = {}
) {
  const routeableEntries = items
    .map((item, index) => toRouteableEntry(item, index))
    .filter(hasRouteableCoordinates);

  const routeableCount = routeableEntries.length;
  const totalCount = items.length;
  const skippedCount = totalCount - routeableCount;

  if (routeableCount < 2) {
    return {
      totalCount,
      routeableCount,
      skippedCount,
      candidates: [],
      reason:
        routeableCount === 0
          ? '当前 Day 暂无可参与真实路线重算的条目'
          : '至少需要 2 个可路由条目才能开始真实路线重算',
    };
  }

  if (routeableCount > maxRouteablePoints) {
    return {
      totalCount,
      routeableCount,
      skippedCount,
      candidates: [],
      reason: `当前 Day 可路由条目数超过 ${maxRouteablePoints} 个，超出当前路线能力上限`,
    };
  }

  const generatedOrders = [
    routeableEntries,
    [...routeableEntries].reverse(),
    ...routeableEntries.map((entry) => buildNearestNeighborOrder(routeableEntries, entry)),
  ];

  const seenKeys = new Set();
  const candidates = [];

  generatedOrders.forEach((orderedEntries) => {
    if (candidates.length >= maxCandidates) {
      return;
    }

    const orderKeys = orderedEntries.map((entry) => entry.localKey).join('|');
    if (seenKeys.has(orderKeys)) {
      return;
    }

    seenKeys.add(orderKeys);
    candidates.push(toCandidate(orderedEntries, candidates.length));
  });

  return {
    totalCount,
    routeableCount,
    skippedCount,
    candidates,
    reason: '',
  };
}

function normalizeRouteOptionResponse(response) {
  if (!response) {
    return null;
  }

  if (Array.isArray(response.options)) {
    return response.options[0] || null;
  }

  if (Array.isArray(response.data?.options)) {
    return response.data.options[0] || null;
  }

  return null;
}

export function selectBestTripRealRouteEvaluation(evaluations = []) {
  let bestEvaluation = null;

  evaluations.forEach((evaluation) => {
    if (!evaluation?.candidate || !evaluation.option) {
      return;
    }

    const duration = toNumericMetric(evaluation.option.duration_min);
    const distance = toNumericMetric(evaluation.option.distance_km);

    if (!bestEvaluation) {
      bestEvaluation = {
        ...evaluation,
        normalizedDuration: duration,
        normalizedDistance: distance,
      };
      return;
    }

    if (duration < bestEvaluation.normalizedDuration) {
      bestEvaluation = {
        ...evaluation,
        normalizedDuration: duration,
        normalizedDistance: distance,
      };
      return;
    }

    if (
      duration === bestEvaluation.normalizedDuration &&
      distance < bestEvaluation.normalizedDistance
    ) {
      bestEvaluation = {
        ...evaluation,
        normalizedDuration: duration,
        normalizedDistance: distance,
      };
    }
  });

  return bestEvaluation;
}

export async function evaluateTripRealRoute(
  items = [],
  requestRouteOptions,
  options = {}
) {
  const candidateSet = buildTripRealRouteCandidates(items, options);

  if (!candidateSet.candidates.length) {
    return {
      ...candidateSet,
      evaluations: [],
      bestEvaluation: null,
      status: 'empty',
      error: '',
    };
  }

  const evaluations = [];
  let lastError = null;

  for (const candidate of candidateSet.candidates) {
    try {
      const response = await requestRouteOptions(candidate.payload, candidate);
      const option = normalizeRouteOptionResponse(response);
      if (!option) {
        evaluations.push({ candidate, option: null });
        continue;
      }

      evaluations.push({ candidate, option });
    } catch (error) {
      lastError = error;
      evaluations.push({ candidate, option: null, error });
    }
  }

  const bestEvaluation = selectBestTripRealRouteEvaluation(evaluations);
  if (bestEvaluation) {
    return {
      ...candidateSet,
      evaluations,
      bestEvaluation,
      status: 'success',
      error: '',
    };
  }

  if (lastError) {
    return {
      ...candidateSet,
      evaluations,
      bestEvaluation: null,
      status: 'error',
      error: lastError?.response?.data?.error || lastError?.message || '真实路线重算失败',
    };
  }

  return {
    ...candidateSet,
    evaluations,
    bestEvaluation: null,
    status: 'empty',
    error: '',
    reason: '当前 Day 暂无可用的真实路线方案',
  };
}

export function applyTripRealRouteOrder(items = [], orderedRouteableKeys = []) {
  const routeableItems = items.filter(hasRouteableCoordinates);
  const nonRouteableItems = items.filter((item) => !hasRouteableCoordinates(item));
  const routeableMap = new Map(routeableItems.map((item) => [item.localKey, item]));
  const orderedRouteableItems = orderedRouteableKeys
    .map((key) => routeableMap.get(key))
    .filter(Boolean);
  const orderedKeySet = new Set(orderedRouteableKeys);
  const remainingRouteableItems = routeableItems.filter((item) => !orderedKeySet.has(item.localKey));

  return [
    ...orderedRouteableItems,
    ...remainingRouteableItems,
    ...nonRouteableItems,
  ];
}

export function createTripRealRouteSignature(items = []) {
  return items
    .map((item, index) => {
      const longitude = normalizeCoordinate(item?.longitude);
      const latitude = normalizeCoordinate(item?.latitude);
      return [
        item?.localKey || `trip-item-${index + 1}`,
        String(item?.item_type || ''),
        item?.ref_id == null ? 'null' : String(item.ref_id),
        longitude == null ? 'null' : String(longitude),
        latitude == null ? 'null' : String(latitude),
      ].join(':');
    })
    .join('|');
}

export function isTripRealRouteStale(items = [], baselineSignature = '') {
  if (!baselineSignature) {
    return false;
  }
  return createTripRealRouteSignature(items) !== baselineSignature;
}
