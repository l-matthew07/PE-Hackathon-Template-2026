import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = (__ENV.BASE_URL || 'http://localhost').replace(/\/+$/, '');
const VUS = Number(__ENV.VUS || 50);
const DURATION = __ENV.DURATION || '2m';
const THINK_TIME_SECONDS = 0.05;
const SHORTEN_RATIO = Math.min(Math.max(Number(__ENV.SHORTEN_RATIO || 0.2), 0), 1);
const SHORT_CODE_WINDOW_SIZE = 300;
const REDIRECT_STATUS_CODES = new Set([301, 302, 307, 308]);

export const options = {
  vus: VUS,
  duration: DURATION,
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<3000'],
    checks: ['rate>0.95'],
  },
};

const vuState = {
  shortTargets: [],
};

function rememberShortTarget(target) {
  vuState.shortTargets.push(target);
  if (vuState.shortTargets.length > SHORT_CODE_WINDOW_SIZE) {
    vuState.shortTargets.shift();
  }
}

function randomExistingTarget() {
  if (vuState.shortTargets.length === 0) {
    return null;
  }
  const index = Math.floor(Math.random() * vuState.shortTargets.length);
  return vuState.shortTargets[index];
}

function makeShortenPayload() {
  const suffix = `${Date.now()}-${__VU}-${__ITER}-${Math.floor(Math.random() * 100000)}`;
  return {
    original_url: `https://example.com/shortener/${suffix}`,
    title: `k6-${suffix}`,
  };
}

function shortenUrl() {
  const payload = makeShortenPayload();
  const response = http.post(`${BASE_URL}/urls`, JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: '/urls', operation: 'shorten' },
  });

  let body;
  try {
    body = response.json();
  } catch (_) {
    body = null;
  }

  const passed = check(response, {
    'shorten status is 201': (r) => r.status === 201,
    'shorten response has short_code': () => body && typeof body.short_code === 'string' && body.short_code.length > 0,
    'shorten response has original_url': () => body && typeof body.original_url === 'string',
  });

  if (!passed || !body) {
    return;
  }

  const shortPath = `/${body.short_code}`;
  const shortUrl = typeof body.short_url === 'string' && body.short_url.length > 0
    ? body.short_url
    : `${BASE_URL}${shortPath}`;

  rememberShortTarget({
    short_code: body.short_code,
    short_url: shortUrl,
    short_path: shortPath,
  });
}

function resolveShortUrl() {
  const target = randomExistingTarget();
  if (!target) {
    shortenUrl();
    return;
  }

  const resolveUrl = target.short_url.startsWith('http')
    ? target.short_url
    : `${BASE_URL}${target.short_path}`;

  const response = http.get(resolveUrl, {
    redirects: 0,
    tags: { endpoint: '/:short_code', operation: 'resolve' },
  });

  check(response, {
    'resolve status is redirect': (r) => REDIRECT_STATUS_CODES.has(r.status),
    'resolve has location header': (r) => !!r.headers.Location,
  });
}

export function setup() {
  const payload = {
    original_url: 'https://example.com/k6/setup',
    title: 'k6-setup',
  };
  const response = http.post(`${BASE_URL}/urls`, JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: '/urls', operation: 'setup' },
  });

  let body;
  try {
    body = response.json();
  } catch (_) {
    body = null;
  }

  const ready = check(response, {
    'setup shorten status is 201': (r) => r.status === 201,
    'setup shorten response has short_code': () => body && typeof body.short_code === 'string' && body.short_code.length > 0,
  });

  if (!ready || !body) {
    throw new Error(`Target did not create short URL at ${BASE_URL}/urls`);
  }

  return {
    short_code: body.short_code,
    short_url: body.short_url || `${BASE_URL}/${body.short_code}`,
    short_path: `/${body.short_code}`,
  };
}

export default function (setupData) {
  if (setupData && vuState.shortTargets.length === 0) {
    rememberShortTarget(setupData);
  }

  const draw = Math.random();

  if (draw < SHORTEN_RATIO) {
    shortenUrl();
    sleep(THINK_TIME_SECONDS);
    return;
  }

  resolveShortUrl();

  sleep(THINK_TIME_SECONDS);
}
