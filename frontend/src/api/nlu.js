import api from './http';

export function parseNlu(text) {
  return api.post('/nlu/parse', { text });
}
