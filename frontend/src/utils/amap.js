const AMAP_SCRIPT_ID = 'amap-js-sdk';

let amapPromise = null;

function getWindowOverride(name) {
  if (typeof window === 'undefined') {
    return undefined;
  }
  if (!Object.prototype.hasOwnProperty.call(window, name)) {
    return undefined;
  }
  return window[name];
}

export function getAmapJsKey() {
  const override = getWindowOverride('__AMAP_JS_KEY_OVERRIDE__');
  if (override !== undefined) {
    return String(override || '').trim();
  }
  return String(import.meta.env.VITE_AMAP_JS_KEY || '').trim();
}

export function getAmapSecurityJsCode() {
  const override = getWindowOverride('__AMAP_SECURITY_JSCODE_OVERRIDE__');
  if (override !== undefined) {
    return String(override || '').trim();
  }
  return String(import.meta.env.VITE_AMAP_SECURITY_JSCODE || '').trim();
}

function createAmapScript(key) {
  const script = document.createElement('script');
  script.id = AMAP_SCRIPT_ID;
  script.async = true;
  script.defer = true;
  script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}`;
  return script;
}

export async function loadAmapSdk() {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    throw new Error('AMap SDK can only be loaded in the browser');
  }

  if (window.AMap?.Map) {
    return window.AMap;
  }

  if (amapPromise) {
    return amapPromise;
  }

  const key = getAmapJsKey();
  if (!key) {
    throw new Error('AMap key is not configured');
  }

  const securityJsCode = getAmapSecurityJsCode();
  if (securityJsCode) {
    window._AMapSecurityConfig = {
      ...(window._AMapSecurityConfig || {}),
      securityJsCode,
    };
  }

  amapPromise = new Promise((resolve, reject) => {
    const existingScript = document.getElementById(AMAP_SCRIPT_ID);
    const script = existingScript || createAmapScript(key);

    const cleanup = () => {
      script.removeEventListener('load', handleLoad);
      script.removeEventListener('error', handleError);
    };

    const handleLoad = () => {
      cleanup();
      if (window.AMap?.Map) {
        resolve(window.AMap);
        return;
      }
      reject(new Error('AMap SDK loaded but window.AMap is unavailable'));
    };

    const handleError = () => {
      cleanup();
      reject(new Error('Failed to load AMap SDK'));
    };

    script.addEventListener('load', handleLoad);
    script.addEventListener('error', handleError);

    if (!existingScript) {
      document.head.appendChild(script);
      return;
    }

    if (window.AMap?.Map) {
      cleanup();
      resolve(window.AMap);
    }
  });

  try {
    return await amapPromise;
  } catch (error) {
    amapPromise = null;
    throw error;
  }
}
