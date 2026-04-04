import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = ((__ENV.BASE_URL || "http://localhost").trim()).replace(/\/$/, "");
const VUS = Number.parseInt(__ENV.VUS || "50", 10);
const DURATION = __ENV.DURATION || "2m";
const SHORTEN_RATIO = clampRatio(__ENV.SHORTEN_RATIO, 0.2);
const RESOLVE_RATIO = clampRatio(__ENV.RESOLVE_RATIO, 0.65);
const STAGES = parseStages(__ENV.STAGES || "");
const SHORT_POOL_SIZE = Number.parseInt(__ENV.SHORT_POOL_SIZE || "0", 10) || Math.min(Math.max(VUS * 2, 120), 1200);

const tier = resolveTier(__ENV.TIER || "", VUS);

export const options = {
  vus: STAGES.length > 0 ? undefined : VUS,
  duration: STAGES.length > 0 ? undefined : DURATION,
  stages: STAGES.length > 0 ? STAGES : undefined,
  thresholds: buildThresholds(tier),
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "max"],
};

export function setup() {
  const shortCodes = [];
  const params = {
    headers: { "Content-Type": "application/json" },
    tags: { endpoint: "POST /shorten", phase: "setup" },
  };

  for (let i = 0; i < SHORT_POOL_SIZE; i += 1) {
    const payload = JSON.stringify({
      url: `https://example.com/seed/${Date.now()}-${i}`,
      title: "k6-seed",
    });

    const response = http.post(`${BASE_URL}/shorten`, payload, params);
    if (response.status !== 201) {
      continue;
    }

    const body = safeJson(response.body);
    if (body && typeof body.short_code === "string" && body.short_code.length > 0) {
      shortCodes.push(body.short_code);
    }
  }

  return { shortCodes };
}

export default function (data) {
  const endpointRoll = Math.random();
  const readRatio = Math.max(0, 1 - SHORTEN_RATIO - RESOLVE_RATIO);

  if (endpointRoll < SHORTEN_RATIO) {
    createShortUrl();
  } else if (endpointRoll < SHORTEN_RATIO + RESOLVE_RATIO) {
    resolveShortUrl(data && Array.isArray(data.shortCodes) ? data.shortCodes : []);
  } else if (endpointRoll < SHORTEN_RATIO + RESOLVE_RATIO + readRatio / 3) {
    listUsers();
  } else if (endpointRoll < SHORTEN_RATIO + RESOLVE_RATIO + (2 * readRatio) / 3) {
    listUrls();
  } else {
    listEvents();
  }

  sleep(0.2 + Math.random() * 0.8);
}

function createShortUrl() {
  const payload = JSON.stringify({
    url: `https://loadtest.example.com/${__VU}-${__ITER}-${Date.now()}`,
    title: "quest-load",
  });
  const response = http.post(`${BASE_URL}/shorten`, payload, {
    headers: { "Content-Type": "application/json" },
    tags: { endpoint: "POST /shorten" },
  });

  check(response, {
    "POST /shorten is 201": (res) => res.status === 201,
  });
}

function resolveShortUrl(shortCodes) {
  if (!shortCodes || shortCodes.length === 0) {
    createShortUrl();
    return;
  }

  const index = Math.floor(Math.random() * shortCodes.length);
  const shortCode = shortCodes[index];
  const response = http.get(`${BASE_URL}/${shortCode}`, {
    redirects: 0,
    tags: { endpoint: "GET /:short_code" },
  });

  check(response, {
    "GET /:short_code is 302": (res) => res.status === 302,
  });
}

function listUsers() {
  const response = http.get(`${BASE_URL}/users?page=1&per_page=20`, {
    tags: { endpoint: "GET /users" },
  });

  check(response, {
    "GET /users is 200": (res) => res.status === 200,
  });
}

function listUrls() {
  const response = http.get(`${BASE_URL}/urls?page=1&per_page=20`, {
    tags: { endpoint: "GET /urls" },
  });

  check(response, {
    "GET /urls is 200": (res) => res.status === 200,
  });
}

function listEvents() {
  const response = http.get(`${BASE_URL}/events?page=1&per_page=20`, {
    tags: { endpoint: "GET /events" },
  });

  check(response, {
    "GET /events is 200": (res) => res.status === 200,
  });
}

export function handleSummary(data) {
  const p95 = metricValue(data, "http_req_duration", "p(95)");
  const failed = metricValue(data, "http_req_failed", "rate") * 100;
  const reqs = metricValue(data, "http_reqs", "count");

  const summary = [
    "",
    "=== Scalability Quest Summary ===",
    `tier: ${tier}`,
    `target: ${BASE_URL}`,
    `vus: ${VUS}`,
    `duration: ${DURATION}`,
    `requests: ${Math.round(reqs)}`,
    `p95 latency: ${formatMs(p95)}`,
    `error rate: ${failed.toFixed(2)}%`,
    "",
    "Bronze: record baseline p95 + error rate.",
    "Silver: pass if p95 < 3000ms.",
    "Gold: pass if error rate < 5%.",
    "",
  ].join("\n");

  return {
    stdout: summary,
  };
}

function buildThresholds(currentTier) {
  const thresholds = {
    http_req_failed: ["rate<0.10"],
    http_req_duration: ["p(95)<5000"],
  };

  if (currentTier === "silver") {
    thresholds.http_req_duration = ["p(95)<3000"];
    thresholds.http_req_failed = ["rate<0.07"];
  }

  if (currentTier === "gold") {
    thresholds.http_req_duration = ["p(95)<3500"];
    thresholds.http_req_failed = ["rate<0.05"];
  }

  return thresholds;
}

function resolveTier(rawTier, vus) {
  const normalized = String(rawTier || "").trim().toLowerCase();
  if (["bronze", "silver", "gold"].includes(normalized)) {
    return normalized;
  }

  if (vus >= 500) {
    return "gold";
  }

  if (vus >= 200) {
    return "silver";
  }

  return "bronze";
}

function parseStages(rawStages) {
  if (!rawStages || !rawStages.trim()) {
    return [];
  }

  return rawStages
    .split(",")
    .map((segment) => segment.trim())
    .filter(Boolean)
    .map((segment) => {
      const [duration, target] = segment.split(":").map((part) => part.trim());
      return {
        duration,
        target: Number.parseInt(target, 10),
      };
    })
    .filter((stage) => stage.duration && Number.isFinite(stage.target));
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function clampRatio(value, fallback) {
  const numeric = Number.parseFloat(value);
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  if (numeric < 0) {
    return 0;
  }
  if (numeric > 0.95) {
    return 0.95;
  }
  return numeric;
}

function metricValue(data, metricName, statName) {
  if (!data || !data.metrics || !data.metrics[metricName]) {
    return 0;
  }

  const metric = data.metrics[metricName];
  if (metric.values && Object.prototype.hasOwnProperty.call(metric.values, statName)) {
    return metric.values[statName];
  }

  return 0;
}

function formatMs(value) {
  if (!Number.isFinite(value)) {
    return "n/a";
  }

  return `${value.toFixed(2)} ms`;
}
