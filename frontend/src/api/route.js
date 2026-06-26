import api from './http';

export function planRoute(payload) {
  return api.post('/route/plan', payload);
}

export function planRouteOptions(payload) {
  return api.post('/route/plan-options', payload);
}

export function routeOptions(payload) {
  return api.post('/route/options', payload);
}

export function routeMetrics() {
  return api.get('/route/metrics');
}
