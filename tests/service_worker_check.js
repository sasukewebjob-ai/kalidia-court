const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

(async () => {
    const handlers = {};
    const deleted = [];
    const writes = [];
    const cachedPage = { body: 'saved app' };
    const ctx = {
        self: { addEventListener: (type, fn) => handlers[type] = fn, clients: { claim: async () => {} } },
        caches: {
            keys: async () => ['kalidia-court-v11', 'kalidia-court-v12', 'other-app-v1'],
            delete: async key => deleted.push(key),
            match: async () => cachedPage,
            open: async () => ({ put: async (...args) => writes.push(args) }),
        },
        fetch: async () => ({ ok: false, status: 503 }),
    };
    vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname, '..', 'service-worker.js'), 'utf8'), ctx);
    let pending;
    handlers.activate({ waitUntil: promise => pending = promise });
    await pending;
    assert.deepEqual(deleted, ['kalidia-court-v11']);
    console.log('PASS: update preserves other apps and current cache');
    handlers.fetch({ request: { method: 'GET', mode: 'navigate' }, respondWith: promise => pending = promise });
    assert.equal(await pending, cachedPage);
    assert.equal(writes.length, 0);
    console.log('PASS: HTTP failure uses cached app without caching error page');
    ctx.fetch = async () => { throw new Error('offline'); };
    handlers.fetch({ request: { method: 'GET', mode: 'navigate' }, respondWith: promise => pending = promise });
    assert.equal(await pending, cachedPage);
    console.log('PASS: offline navigation uses cached app');
})().catch(error => { console.error(error); process.exitCode = 1; });
