import http from 'k6/http';
import { check, sleep } from 'k6';

function parseIntEnv(name, fallback) {
  const raw = __ENV[name];
  if (!raw) {
    return fallback;
  }
  const parsed = parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseFloatEnv(name, fallback) {
  const raw = __ENV[name];
  if (!raw) {
    return fallback;
  }
  const parsed = parseFloat(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeBaseUrl(url) {
  return (url || 'http://localhost').replace(/\/+$/, '');
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function parseStages(rawStages) {
  if (!rawStages) {
    return null;
  }

  const stages = rawStages
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const parts = entry.split(':').map((part) => part.trim());
      if (parts.length !== 2) {
        return null;
      }
      const target = parseInt(parts[1], 10);
      if (!Number.isFinite(target)) {
        return null;
      }
      return { duration: parts[0], target };
    })
    .filter(Boolean);

  return stages.length > 0 ? stages : null;
}

const tierDefaults = {
  bronze: { vus: 50, duration: '2m', shortenRatio: 0.2 },
  silver: { vus: 200, duration: '3m', shortenRatio: 0.2 },
  gold: { vus: 500, duration: '4m', shortenRatio: 0.15 },
};

const tierName = (__ENV.TIER || 'bronze').toLowerCase();
const selectedTier = tierDefaults[tierName] || tierDefaults.bronze;

const baseUrl = normalizeBaseUrl(__ENV.BASE_URL || 'http://localhost');
const vus = parseIntEnv('VUS', selectedTier.vus);
const duration = __ENV.DURATION || selectedTier.duration;
const shortenRatio = clamp(
  parseFloatEnv('SHORTEN_RATIO', selectedTier.shortenRatio),
  0,
  1,
);
const listRatio = clamp(parseFloatEnv('LIST_RATIO', 0.25), 0, 1);
const healthcheckEvery = Math.max(parseIntEnv('HEALTHCHECK_EVERY', 25), 0);
const thinkTime = Math.max(parseFloatEnv('THINK_TIME_SECONDS', 0.05), 0);
const stages = parseStages(__ENV.STAGES);

const idWindowSize = Math.max(parseIntEnv('ID_WINDOW_SIZE', 200), 1);

const optionsBase = {
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<3000'],
    checks: ['rate>0.95'],
  },
};

export const options = stages
  ? {
      ...optionsBase,
      stages,
    }
  : {
      ...optionsBase,
      vus,
      duration,
    };

const vuState = {
  createdIds: [],
};

function rememberUrlId(id) {
  vuState.createdIds.push(id);
  if (vuState.createdIds.length > idWindowSize) {
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
  const response = http.get(`${baseUrl}/health`, {
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
  const response = http.post(`${baseUrl}/urls`, JSON.stringify(payload), {
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
  const response = http.get(`${baseUrl}/urls?page=1&per_page=20`, {
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
  const response = http.get(`${baseUrl}/urls/${urlId}`, {
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
  const response = http.get(`${baseUrl}/health`, {
    tags: { endpoint: '/health', operation: 'setup' },
  });

  const healthy = check(response, {
    'setup health status is 200': (r) => r.status === 200,
  });

  if (!healthy) {
    throw new Error(`Target is not healthy at ${baseUrl}/health`);
  }

  return { baseUrl };
}

export default function () {
  if (healthcheckEvery > 0 && __ITER % healthcheckEvery === 0) {
    healthCheck();
  }

  const draw = Math.random();

  if (draw < shortenRatio) {
    createUrl();
    sleep(thinkTime);
    return;
  }

  if (draw < shortenRatio + listRatio) {
    listUrls();
    sleep(thinkTime);
    return;
  }

  const existingId = randomExistingId();
  if (existingId === null) {
    createUrl();
  } else {
    getUrlById(existingId);
  }

  sleep(thinkTime);
}
