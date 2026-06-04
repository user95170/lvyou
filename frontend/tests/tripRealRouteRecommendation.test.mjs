import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyTripRealRouteOrder,
  buildTripRealRouteCandidates,
  createTripRealRouteSignature,
  isTripRealRouteStale,
  selectBestTripRealRouteEvaluation,
} from '../src/utils/tripRealRouteRecommendation.mjs';

function createItem(overrides = {}) {
  return {
    localKey: overrides.localKey || `item-${Math.random().toString(36).slice(2, 8)}`,
    item_type: overrides.item_type || 'scenic_spot',
    ref_id: overrides.ref_id ?? null,
    title_snapshot: overrides.title_snapshot || '测试条目',
    longitude: overrides.longitude ?? null,
    latitude: overrides.latitude ?? null,
    start_time: overrides.start_time || '',
    end_time: overrides.end_time || '',
    transport_mode: overrides.transport_mode || '',
    note: overrides.note || '',
    ...overrides,
  };
}

test('buildTripRealRouteCandidates keeps current/reverse order, deduplicates, and truncates to six candidates', () => {
  const items = [
    createItem({
      localKey: 'c',
      title_snapshot: 'C',
      longitude: 10,
      latitude: 0,
    }),
    createItem({
      localKey: 'a',
      title_snapshot: 'A',
      longitude: 0,
      latitude: 0,
    }),
    createItem({
      localKey: 'd',
      title_snapshot: 'D',
      longitude: 10,
      latitude: 1,
    }),
    createItem({
      localKey: 'b',
      title_snapshot: 'B',
      longitude: 0,
      latitude: 1,
    }),
  ];

  const result = buildTripRealRouteCandidates(items);

  assert.equal(result.routeableCount, 4);
  assert.equal(result.candidates.length, 6);
  assert.deepEqual(result.candidates[0].orderKeys, ['c', 'a', 'd', 'b']);
  assert.deepEqual(result.candidates[1].orderKeys, ['b', 'd', 'a', 'c']);
  assert.equal(
    new Set(result.candidates.map((candidate) => candidate.orderKeys.join('|'))).size,
    result.candidates.length
  );
  assert.ok(
    result.candidates.every(
      (candidate) =>
        candidate.payload.mode === 'drive' && candidate.payload.api_version === 'v5'
    )
  );
});

test('selectBestTripRealRouteEvaluation prefers shorter duration and then shorter distance', () => {
  const evaluations = [
    {
      candidate: { orderKeys: ['a', 'b', 'c'] },
      option: { duration_min: 26, distance_km: 8.2 },
    },
    {
      candidate: { orderKeys: ['a', 'c', 'b'] },
      option: { duration_min: 24, distance_km: 8.9 },
    },
    {
      candidate: { orderKeys: ['b', 'a', 'c'] },
      option: { duration_min: 24, distance_km: 8.1 },
    },
    {
      candidate: { orderKeys: ['c', 'a', 'b'] },
      option: { duration_min: null, distance_km: 6.5 },
    },
  ];

  const best = selectBestTripRealRouteEvaluation(evaluations);

  assert.deepEqual(best.candidate.orderKeys, ['b', 'a', 'c']);
  assert.equal(best.option.duration_min, 24);
  assert.equal(best.option.distance_km, 8.1);
});

test('applyTripRealRouteOrder appends non-routeable items to the end while preserving their relative order and fields', () => {
  const items = [
    createItem({
      localKey: 'custom-breakfast',
      item_type: 'custom',
      title_snapshot: '早餐',
      note: '保留备注',
    }),
    createItem({
      localKey: 'museum',
      item_type: 'scenic_spot',
      title_snapshot: '博物馆',
      longitude: 111.7,
      latitude: 40.8,
    }),
    createItem({
      localKey: 'hotel',
      item_type: 'hotel',
      title_snapshot: '酒店',
      longitude: 111.8,
      latitude: 40.82,
      start_time: '21:00',
    }),
    createItem({
      localKey: 'custom-note',
      item_type: 'custom',
      title_snapshot: '拍照休息',
      note: '不要丢',
    }),
  ];

  const reorderedItems = applyTripRealRouteOrder(items, ['hotel', 'museum']);

  assert.deepEqual(
    reorderedItems.map((item) => item.localKey),
    ['hotel', 'museum', 'custom-breakfast', 'custom-note']
  );
  assert.equal(reorderedItems[0].start_time, '21:00');
  assert.equal(reorderedItems[2].note, '保留备注');
  assert.equal(reorderedItems[3].note, '不要丢');
});

test('createTripRealRouteSignature ignores time and note changes but detects route-affecting changes', () => {
  const baseItems = [
    createItem({
      localKey: 'spot-1',
      item_type: 'scenic_spot',
      ref_id: 12,
      longitude: 111.7,
      latitude: 40.8,
      start_time: '09:00',
      note: '初始备注',
    }),
    createItem({
      localKey: 'custom-1',
      item_type: 'custom',
      title_snapshot: '自由活动',
      note: '午休',
    }),
  ];

  const baselineSignature = createTripRealRouteSignature(baseItems);

  const timeOnlyChangedItems = [
    {
      ...baseItems[0],
      start_time: '10:30',
      note: '更新时间备注',
    },
    baseItems[1],
  ];
  assert.equal(isTripRealRouteStale(timeOnlyChangedItems, baselineSignature), false);

  const reorderedItems = [baseItems[1], baseItems[0]];
  assert.equal(isTripRealRouteStale(reorderedItems, baselineSignature), true);

  const resourceChangedItems = [
    {
      ...baseItems[0],
      ref_id: 99,
      longitude: 112.01,
    },
    baseItems[1],
  ];
  assert.equal(isTripRealRouteStale(resourceChangedItems, baselineSignature), true);
});
