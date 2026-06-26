import api from './http';

export function fetchPersonalizedMap(payload) {
  return api.post('/map/personalized', payload);
}
