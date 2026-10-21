import assert from "node:assert/strict";
import { test } from "node:test";
import { coordinates, googleMapUrls } from "./location.js";

test("reads saved coordinates and legacy formats, including zero coordinates", () => {
  assert.deepEqual(coordinates({ latitud: -12.0412699, longitud: -77.0421754 }), { lat: -12.0412699, lng: -77.0421754 });
  assert.deepEqual(coordinates('{"lat":0,"lng":0}'), { lat: 0, lng: 0 });
  assert.deepEqual(coordinates("-12.04, -77.04"), { lat: -12.04, lng: -77.04 });
  assert.deepEqual(coordinates({ latitude: "-12", longitude: "-77" }), { lat: -12, lng: -77 });
});

test("does not invent a location when coordinates are missing or invalid", () => {
  for (const value of [null, {}, [], { lat: null, lng: null }, { lat: "", lng: "" }, { lat: 91, lng: 0 }, { lat: 0, lng: 181 }, "Sin ubicación", { lat: "invalid", lng: 0 }]) {
    assert.equal(coordinates(value), null);
  }
});

test("uses the same coordinates for the Google map and its external link", () => {
  const urls = googleMapUrls({ lat: -12.04, lng: -77.04 });
  assert.equal(new URL(urls.embed).hostname, "maps.google.com");
  assert.equal(new URL(urls.embed).searchParams.get("q"), "-12.04,-77.04");
  assert.equal(new URL(urls.open).searchParams.get("query"), "-12.04,-77.04");
});

test("rejects booleans and containers instead of converting them to coordinates", () => {
  for (const value of [{ lat: false, lng: true }, { lat: [], lng: [] }, { lat: [12], lng: [77] }]) {
    assert.equal(coordinates(value), null);
  }
});
