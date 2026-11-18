// Deterministic hardware-seeded device fingerprinting utility
// Generates and persists DEV-XXXXXXXXXXXX in localStorage

let cachedDeviceId = null;

export async function getDeviceId() {
  if (cachedDeviceId) return cachedDeviceId;

  if (typeof window === 'undefined') {
    return 'DEV-SERVER-NODE';
  }

  try {
    let seed = localStorage.getItem('pusher_hw_seed');
    if (!seed) {
      seed = 'seed_' + Math.random().toString(36).substring(2) + Date.now().toString(36);
      localStorage.setItem('pusher_hw_seed', seed);
    }

    const platform = navigator.platform || 'web-platform';
    const screenDim = `${window.screen?.width || 1920}x${window.screen?.height || 1080}`;
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    const hardwareConcurrency = navigator.hardwareConcurrency || 4;

    const rawSignature = `${seed}::${platform}::${screenDim}::${timeZone}::${hardwareConcurrency}`;
    const encoder = new TextEncoder();
    const data = encoder.encode(rawSignature);

    if (window.crypto && window.crypto.subtle) {
      const hashBuffer = await window.crypto.subtle.digest('SHA-256', data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hashHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
      cachedDeviceId = `DEV-${hashHex.substring(0, 12).toUpperCase()}`;
    } else {
      // Fallback simple checksum if WebCrypto unavailable
      let hash = 0;
      for (let i = 0; i < rawSignature.length; i++) {
        hash = (hash << 5) - hash + rawSignature.charCodeAt(i);
        hash |= 0;
      }
      cachedDeviceId = `DEV-${Math.abs(hash).toString(16).padStart(12, '0').substring(0, 12).toUpperCase()}`;
    }
  } catch {
    cachedDeviceId = 'DEV-LOCAL-USER';
  }

  return cachedDeviceId;
}

export function getCachedDeviceIdSync() {
  return cachedDeviceId || 'DEV-INITIALIZING';
}
