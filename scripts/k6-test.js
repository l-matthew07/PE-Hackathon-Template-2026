import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = (__ENV.BASE_URL || 'http://localhost').replace(/\/+$/, '');
const THINK_TIME_SECONDS = 0.05;
const CREATE_RATIO = 0.2;
const LIST_RATIO = 0.25;
const ID_WINDOW_SIZE = 200;
const HEALTHCHECK_EVERY = 25;

export const options = {
  vus: 50,
  duration: '2m',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<3000'],
    checks: ['rate>0.95'],
  },
};

const vuState = {
  createdIds: [],
};

function rememberUrlId(id) {
  vuState.createdIds.push(id);
  if (vuState.createdIds.length > ID_WINDOW_SIZE) {
    vuState.createdIds.shift();
  }
}

function randomExistingId() {
  if (vuState.createdIds.length === 0) {
    return null;
  }
  const index = Math.floor(Math.random() * vuState.createdIds.length);
  return vuState.createdIds[index];
}

function makeCreatePayload() {
  const suffix = `${Date.now()}-${__VU}-${__ITER}-${Math.floor(Math.random() * 100000)}`;
  return {
    original_url: `https://example.com/quest/${suffix}`,
    title: `k6-${suffix}`,
  };
}

function healthCheck() {
  const response = http.get(`${BASE_URL}/health`, {
    tags: { endpoint: '/health', operation: 'health' },
  });

  check(response, {
    'health status is 200': (r) => r.status === 200,
    'health payload is ok': (r) => {
      try {
        return JSON.parse(r.body).status === 'ok';
      } catch (_) {
        return false;
      }
    },
  });
}

function createUrl() {
  const payload = makeCreatePayload();
  const response = http.post(`${BASE_URL}/urls`, JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: '/urls', operation: 'create' },
  });

  let body;
  try {
    body = response.json();
  } catch (_) {
    body = null;
  }

  const passed = check(response, {
    'create status is 201': (r) => r.status === 201,
    'create response has id': () => body && Number.isInteger(body.id),
    'create response has short_code': () => body && typeof body.short_code === 'string',
  });

  if (passed && body && Number.isInteger(body.id)) {
    rememberUrlId(body.id);
  }
}

function listUrls() {
  const response = http.get(`${BASE_URL}/urls?page=1&per_page=20`, {
    tags: { endpoint: '/urls', operation: 'list' },
  });

  let body;
  try {
    body = response.json();
  } catch (_) {
    body = null;
  }

  check(response, {
    'list status is 200': (r) => r.status === 200,
    'list response has data array': () => body && Array.isArray(body.data),
  });

  if (body && Array.isArray(body.data)) {
    for (const url of body.data) {
      if (url && Number.isInteger(url.id)) {
        rememberUrlId(url.id);
      }
    }
  }
}

function getUrlById(urlId) {
  const response = http.get(`${BASE_URL}/urls/${urlId}`, {
    tags: { endpoint: '/urls/:id', operation: 'get' },
  });

  let body;
  try {
    body = response.json();
  } catch (_) {
    body = null;
  }

  check(response, {
    'get status is 200': (r) => r.status === 200,
    'get response id matches': () => body && body.id === urlId,
    'get response has original_url': () => body && typeof body.original_url === 'string',
  });
}

export function setup() {
  const response = http.get(`${BASE_URL}/health`, {
    tags: { endpoint: '/health', operation: 'setup' },
  });

  const healthy = check(response, {
    'setup health status is 200': (r) => r.status === 200,
  });

  if (!healthy) {
    throw new Error(`Target is not healthy at ${BASE_URL}/health`);
  }
}

export default function () {
  if (__ITER % HEALTHCHECK_EVERY === 0) {
    healthCheck();
  }

  const draw = Math.random();

  if (draw < CREATE_RATIO) {
    createUrl();
    sleep(THINK_TIME_SECONDS);
    return;
  }

  if (draw < CREATE_RATIO + LIST_RATIO) {
    listUrls();
    sleep(THINK_TIME_SECONDS);
    return;
  }

  const existingId = randomExistingId();
  if (existingId === null) {
    createUrl();
  } else {
    getUrlById(existingId);
  }

  sleep(THINK_TIME_SECONDS);
}
