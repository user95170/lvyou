import api from './http';

export function chatAgent(payload) {
  return api.post('/agent/chat', payload);
}
