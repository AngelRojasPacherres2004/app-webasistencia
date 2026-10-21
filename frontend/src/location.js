const pair = (lat, lng) => {
  if (![lat, lng].every((value) => typeof value === "number" || typeof value === "string")) return null;
  if (lat == null || lng == null || String(lat).trim() === "" || String(lng).trim() === "") return null;
  const latitude = Number(lat);
  const longitude = Number(lng);
  return Number.isFinite(latitude) && Number.isFinite(longitude) && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180
    ? { lat: latitude, lng: longitude } : null;
};

export function coordinates(value) {
  if (typeof value === "string") {
    try { return coordinates(JSON.parse(value)); } catch { /* Older marks may store a coordinate pair as text. */ }
    const match = value.trim().match(/^\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?$/);
    return match ? pair(match[1], match[2]) : null;
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return pair(value.latitud ?? value.latitude ?? value.lat, value.longitud ?? value.longitude ?? value.lng ?? value.lon);
}

export function googleMapUrls(point) {
  const q = encodeURIComponent(`${point.lat},${point.lng}`);
  return {
    embed: `https://maps.google.com/maps?q=${q}&z=17&hl=es&output=embed`,
    open: `https://www.google.com/maps/search/?api=1&query=${q}`,
  };
}
