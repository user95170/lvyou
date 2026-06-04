import api from './http';

export function listTrips(userId) {
  return api.get('/trips', {
    params: { user_id: userId },
  });
}

export function getTrip(tripId, userId) {
  return api.get(`/trips/${tripId}`, {
    params: { user_id: userId },
  });
}

export function createTrip(payload) {
  return api.post('/trips', payload);
}

export function updateTrip(tripId, payload) {
  return api.put(`/trips/${tripId}`, payload);
}

export function deleteTrip(tripId, userId) {
  return api.delete(`/trips/${tripId}`, {
    params: { user_id: userId },
  });
}
