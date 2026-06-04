import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyDayRouteRecommendation,
  buildDayRouteRecommendation,
} from '../src/utils/tripRouteRecommendation.mjs';

function createItem(overrides = {}) {
  return {
    localKey: overrides.localKey || `item-${Math.random().toString(36).slice(2, 8)}`,
    title_snapshot: overrides.title_snapshot || '测试条目',
    longitude: overrides.longitude ?? null,
    latitude: overrides.latitude ?? null,
    ...overrides,
  };
}

test('buildDayRouteRecommendation creates a stable greedy order for routeable items', () => {
  const items = [
    createItem({
      localKey: 'a',
      title_snapshot: 'A',
      longitude: 111.7,
      latitude: 40.8,
    }),
    createItem({
      localKey: 'c',
      title_snapshot: 'C',
      longitude: 112.2,
      latitude: 41.2,
    }),
    createItem({
      localKey: 'b',
      title_snapshot: 'B',
      longitude: 111.72,
      latitude: 40.82,
    }),
  ];

  const recommendation = buildDayRouteRecommendation(items);

  assert.equal(recommendation.routeableCount, 3);
  assert.equal(recommendation.canApply, true);
  assert.deepEqual(recommendation.recommendedOrderKeys, ['a', 'b', 'c']);
});

test('applyDayRouteRecommendation moves non-routeable items to the end while keeping their relative order', () => {
  const items = [
    createItem({
      localKey: 'route-1',
      title_snapshot: '可路由 1',
      longitude: 111.7,
      latitude: 40.8,
    }),
    createItem({
      localKey: 'custom-1',
      title_snapshot: '自定义 1',
    }),
    createItem({
      localKey: 'route-2',
      title_snapshot: '可路由 2',
      longitude: 111.72,
      latitude: 40.82,
    }),
    createItem({
      localKey: 'custom-2',
      title_snapshot: '自定义 2',
    }),
  ];

  const recommendedItems = applyDayRouteRecommendation(items);

  assert.deepEqual(
    recommendedItems.map((item) => item.localKey),
    ['route-1', 'route-2', 'custom-1', 'custom-2']
  );
});

test('buildDayRouteRecommendation reports already optimal order when nothing should change', () => {
  const items = [
    createItem({
      localKey: 'route-1',
      title_snapshot: '可路由 1',
      longitude: 111.7,
      latitude: 40.8,
    }),
    createItem({
      localKey: 'route-2',
      title_snapshot: '可路由 2',
      longitude: 111.72,
      latitude: 40.82,
    }),
    createItem({
      localKey: 'custom-1',
      title_snapshot: '自定义 1',
    }),
  ];

  const recommendation = buildDayRouteRecommendation(items);

  assert.equal(recommendation.canApply, false);
  assert.equal(recommendation.isAlreadyOptimal, true);
  assert.equal(recommendation.reason, '当前顺序已最佳');
});
