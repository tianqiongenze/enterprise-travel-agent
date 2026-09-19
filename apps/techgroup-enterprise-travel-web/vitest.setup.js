/**
 * Node >= 22 ships an experimental global localStorage shim without full
 * Storage methods, which shadows jsdom's implementation. Replace it with a
 * complete in-memory Storage for deterministic tests.
 */
class InMemoryStorage {
  constructor() {
    this._map = new Map();
  }

  getItem(key) {
    return this._map.has(String(key)) ? this._map.get(String(key)) : null;
  }

  setItem(key, value) {
    this._map.set(String(key), String(value));
  }

  removeItem(key) {
    this._map.delete(String(key));
  }

  clear() {
    this._map.clear();
  }

  key(index) {
    return [...this._map.keys()][index] ?? null;
  }

  get length() {
    return this._map.size;
  }
}

globalThis.localStorage = new InMemoryStorage();
