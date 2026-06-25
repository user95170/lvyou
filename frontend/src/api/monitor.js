import api from './http';

export function getMonitorOverview() {
  return api.get('/monitor/overview');
}
