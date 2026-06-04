function normalizeCoordinate(value) {
  if (value === '' || value == null) {
    return null;
  }
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
}

function hasRouteableCoordinates(item) {
  return (
    item != null &&
    normalizeCoordinate(item.longitude) != null &&
    normalizeCoordinate(item.latitude) != null
  );
}

function toRecommendationEntry(item, index) {
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

function buildGreedyRouteableOrder(entries) {
  if (entries.length <= 1) {
    return [...entries];
  }

  const remaining = entries.slice(1);
  const ordered = [entries[0]];

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

function sameOrder(a, b) {
  if (a.length !== b.length) {
    return false;
  }
  return a.every((value, index) => value === b[index]);
}

export function buildDayRouteRecommendation(items = []) {
  const entries = items.map((item, index) => toRecommendationEntry(item, index));
  const routeableEntries = entries.filter(hasRouteableCoordinates);
  const nonRouteableEntries = entries.filter((entry) => !hasRouteableCoordinates(entry));
  const currentOrderKeys = entries.map((entry) => entry.localKey);

  if (routeableEntries.length < 2) {
    return {
      totalCount: entries.length,
      routeableCount: routeableEntries.length,
      skippedCount: nonRouteableEntries.length,
      currentOrderKeys,
      recommendedOrderKeys: currentOrderKeys,
      recommendedItems: entries.map((entry) => entry.originalItem),
      recommendedRouteableItems: routeableEntries.map((entry) => entry.originalItem),
      isAlreadyOptimal: true,
      canApply: false,
      reason:
        routeableEntries.length === 0
          ? '当前 Day 暂无可路由条目'
          : '至少需要 2 个可路由条目才能生成路线建议',
    };
  }

  const orderedRouteableEntries = buildGreedyRouteableOrder(routeableEntries);
  const recommendedEntries = [...orderedRouteableEntries, ...nonRouteableEntries];
  const recommendedOrderKeys = recommendedEntries.map((entry) => entry.localKey);
  const isAlreadyOptimal = sameOrder(currentOrderKeys, recommendedOrderKeys);

  return {
    totalCount: entries.length,
    routeableCount: routeableEntries.length,
    skippedCount: nonRouteableEntries.length,
    currentOrderKeys,
    recommendedOrderKeys,
    recommendedItems: recommendedEntries.map((entry) => entry.originalItem),
    recommendedRouteableItems: orderedRouteableEntries.map((entry) => entry.originalItem),
    isAlreadyOptimal,
    canApply: !isAlreadyOptimal,
    reason: isAlreadyOptimal ? '当前顺序已最佳' : '',
  };
}

export function applyDayRouteRecommendation(items = []) {
  return buildDayRouteRecommendation(items).recommendedItems;
}
