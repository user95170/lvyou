import api from './http';

export function getScenicSpots(params) {
  return api.get('/scenic-spots', { params });
}

export function getHotels(params) {
  return api.get('/hotels', { params });
}

export function getFoods(params) {
  return api.get('/foods', { params });
}

export function createRating(payload) {
  return api.post('/ratings', payload);
}

export function createBehavior(payload) {
  return api.post('/behaviors', payload);
}
