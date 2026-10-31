// Optional image (for example a logo) the host adds; it shows in the presenter's top-right corner.
// It is shrunk in the browser and kept in this browser's storage, so it reaches the presenter tab
// opened from the host screen on the same computer. Sharing it across devices needs issue #30.

const MAX_SIDE = 600;
const keyFor = (code) => `crowdpulse-image-${code}`;

// Reads an image file and returns a shrunk PNG data URL (keeps transparency for logos).
export function shrinkImage(file) {
  return new Promise((resolve, reject) => {
    if (!file || !file.type.startsWith("image/")) return reject(new Error("Choose an image file (PNG, JPG, SVG or GIF)."));
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth || MAX_SIDE, img.naturalHeight || MAX_SIDE));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round((img.naturalWidth || MAX_SIDE) * scale));
      canvas.height = Math.max(1, Math.round((img.naturalHeight || MAX_SIDE) * scale));
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("That image could not be opened. Try a PNG or JPG."));
    };
    img.src = url;
  });
}

export function loadImage(code) {
  try {
    return localStorage.getItem(keyFor(code));
  } catch {
    return null;
  }
}

// Returns false if the browser would not store it (storage blocked or full).
export function saveImage(code, dataUrl) {
  try {
    if (dataUrl) localStorage.setItem(keyFor(code), dataUrl);
    else localStorage.removeItem(keyFor(code));
    return true;
  } catch {
    return false;
  }
}

// Calls onChange(dataUrl | null) when another tab adds or removes the image.
export function watchImage(code, onChange) {
  window.addEventListener("storage", (event) => {
    if (event.key === keyFor(code)) onChange(event.newValue);
  });
}

// Shows dataUrl in an <img>, or hides it when there is none.
export function showImage(img, dataUrl) {
  img.hidden = !dataUrl;
  if (dataUrl) img.src = dataUrl;
  else img.removeAttribute("src");
}
